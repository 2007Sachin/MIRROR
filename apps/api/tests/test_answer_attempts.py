"""Try again: attempts are owned, sequenced, never overwrite the transcript, and never grade."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.attempt_models import (
    Aspect,
    AspectChange,
    AttemptCreate,
    ComparisonSource,
    Presence,
    RetryComparisonOutput,
    attempt_view,
)
from app.attempt_service import (
    AttemptNotAllowed,
    AttemptNotFinished,
    AttemptNotFound,
    AttemptService,
    MemoryAttemptRepository,
    checks_comparison,
    model_comparison,
)
from app.copy_guard import find_banned
from app.interviewer_models import PublicTurn
from app.repository import MemorySessionRepository
from app.schemas import SessionCreate, SessionStatus

USER, OTHER = uuid4(), uuid4()
FIRST = "We worked on the pricing report and the team shipped it."
BETTER = "I rebuilt the pricing model myself because the old one ignored discounts, which cut quoting errors by about a third."


class Transcript:
    def __init__(self, turns):
        self.turns = turns

    async def list_public_turns(self, session_id, user_id):
        return list(self.turns)


def turn(session_id, index, speaker, text):
    return PublicTurn(
        id=uuid4(), session_id=session_id, turn_index=index, speaker=speaker, text=text,
        turn_type="PLANNED", phase="ROLE_CORE", created_at=datetime.now(UTC),
    )


class Runner:
    """Stands in for the agent runner: returns a fixed output, or fails."""

    def __init__(self, output=None, fail=False):
        self.output, self.fail, self.calls = output, fail, 0

    async def run(self, name, payload, context=None):
        self.calls += 1
        if self.fail:
            raise TimeoutError("provider timed out")
        return SimpleNamespace(success=self.output is not None, output=self.output)


def setup(status=SessionStatus.COMPLETED, runner=None):
    sessions = MemorySessionRepository()
    session = asyncio.run(sessions.create(USER, SessionCreate(target_role="AR Analyst")))
    session = asyncio.run(sessions.update(session.id, USER, {"status": status}))
    question = turn(session.id, 0, "INTERVIEWER", "Tell me about a result you're proud of.")
    answer = turn(session.id, 1, "CANDIDATE", FIRST)
    transcript = Transcript([question, answer])
    attempts = MemoryAttemptRepository()
    service = AttemptService(sessions, transcript, attempts, runner, model="retry-model")
    return service, session, question, answer, transcript, attempts


# ------------------------------------------------------------------ contract


def test_the_comparison_contract_rejects_numbers_and_repeated_aspects() -> None:
    change = {"aspect": "RESULT", "first": "ABSENT", "latest": "PRESENT"}
    RetryComparisonOutput(changes=[change], summary="Your result is clearer now.", next_suggestion="Add how big it was.")
    with pytest.raises(ValidationError):
        RetryComparisonOutput(changes=[change], summary="Your score went from 62 to 78.", next_suggestion="Keep going.")
    with pytest.raises(ValidationError):
        RetryComparisonOutput(changes=[change], summary="Clearer.", next_suggestion="Now 100% there.")
    with pytest.raises(ValidationError):
        RetryComparisonOutput(changes=[change, change], summary="Clearer now.", next_suggestion="Keep going.")
    with pytest.raises(ValidationError):
        RetryComparisonOutput(changes=[change], summary="Clearer now.", next_suggestion="Keep going.", hidden_reasoning="x")


def test_what_changed_is_derived_only_from_absent_to_present_pairs() -> None:
    output = RetryComparisonOutput(
        changes=[
            AspectChange(aspect=Aspect.OWNERSHIP, first=Presence.ABSENT, latest=Presence.PRESENT),
            AspectChange(aspect=Aspect.RESULT, first=Presence.ABSENT, latest=Presence.ABSENT),
            AspectChange(aspect=Aspect.ACTIONS, first=Presence.PRESENT, latest=Presence.PRESENT),
        ],
        summary="Your second answer makes your role clearer.",
        next_suggestion="Add what happened afterwards.",
    )
    comparison = model_comparison(output, list(Aspect))
    from app.attempt_models import comparison_view
    view = comparison_view(comparison)
    assert view.came_through_more_clearly == [Aspect.OWNERSHIP]
    assert view.still_missing == [Aspect.RESULT]
    assert view.first_present == [Aspect.ACTIONS]
    assert set(view.latest_present) == {Aspect.OWNERSHIP, Aspect.ACTIONS}


def test_unsafe_model_sentences_are_replaced_with_safe_ones() -> None:
    output = RetryComparisonOutput(
        changes=[AspectChange(aspect=Aspect.RESULT, first=Presence.ABSENT, latest=Presence.ABSENT)],
        summary="Your weakness is still the result.",
        next_suggestion="Your performance needs the outcome.",
    )
    comparison = model_comparison(output, list(Aspect))
    assert not find_banned(comparison.summary) and not find_banned(comparison.next_suggestion)


def test_the_fallback_checks_describe_presence_without_numbers() -> None:
    comparison = checks_comparison(FIRST, BETTER)
    pairs = {change.aspect: (change.first, change.latest) for change in comparison.changes}
    assert pairs[Aspect.OWNERSHIP] == (Presence.ABSENT, Presence.PRESENT)
    assert pairs[Aspect.MEASURE] == (Presence.ABSENT, Presence.PRESENT)
    assert comparison.source == ComparisonSource.CHECKS
    assert not any(char.isdigit() for char in comparison.summary + comparison.next_suggestion)
    # The checks cannot see a situation or the steps taken, so they never claim either.
    assert Aspect.SITUATION not in pairs and Aspect.ACTIONS not in pairs


# ------------------------------------------------------------------ the service


def test_an_attempt_keeps_the_original_answer_and_the_question_exactly() -> None:
    service, session, question, answer, transcript, _ = setup()
    record = asyncio.run(service.create(session.id, answer.id, USER, AttemptCreate(answer=BETTER, area_key="impact")))
    assert record.sequence == 1
    assert record.original_answer == FIRST and record.question_text == question.text
    assert record.question_turn_id == question.id and record.original_turn_id == answer.id
    assert transcript.turns[1].text == FIRST  # the transcript is untouched


def test_attempts_are_numbered_in_order_for_each_answer() -> None:
    service, session, _, answer, _, attempts = setup()
    for text in ("first retry", "second retry", "third retry"):
        asyncio.run(service.create(session.id, answer.id, USER, AttemptCreate(answer=text)))
    assert [row.sequence for row in attempts.rows] == [1, 2, 3]
    assert all(row.original_answer == FIRST for row in attempts.rows)


def test_attempts_are_capped_per_answer() -> None:
    service, session, _, answer, _, _ = setup()
    for index in range(10):
        asyncio.run(service.create(session.id, answer.id, USER, AttemptCreate(answer=f"retry {index}")))
    with pytest.raises(AttemptNotAllowed):
        asyncio.run(service.create(session.id, answer.id, USER, AttemptCreate(answer="one more")))


def test_an_unfinished_practice_cannot_be_retried() -> None:
    service, session, _, answer, _, _ = setup(status=SessionStatus.ACTIVE)
    with pytest.raises(AttemptNotFinished):
        asyncio.run(service.create(session.id, answer.id, USER, AttemptCreate(answer=BETTER)))


def test_another_persons_practice_or_a_question_turn_cannot_be_retried() -> None:
    service, session, question, answer, _, _ = setup()
    with pytest.raises(AttemptNotFound):
        asyncio.run(service.create(session.id, answer.id, OTHER, AttemptCreate(answer=BETTER)))
    with pytest.raises(AttemptNotFound):
        asyncio.run(service.create(session.id, question.id, USER, AttemptCreate(answer=BETTER)))
    with pytest.raises(AttemptNotFound):
        asyncio.run(service.create(session.id, uuid4(), USER, AttemptCreate(answer=BETTER)))
    with pytest.raises(AttemptNotFound):
        asyncio.run(service.list_for_session(session.id, OTHER))


def test_one_model_call_per_retry_and_its_result_is_used() -> None:
    output = {
        "changes": [{"aspect": "OWNERSHIP", "first": "ABSENT", "latest": "PRESENT"}],
        "summary": "Your second answer makes your role clearer.",
        "next_suggestion": "Add what happened afterwards.",
    }
    runner = Runner(output)
    service, session, _, answer, _, _ = setup(runner=runner)
    record = asyncio.run(service.create(session.id, answer.id, USER, AttemptCreate(answer=BETTER)))
    assert runner.calls == 1
    assert record.comparison and record.comparison.source == ComparisonSource.MODEL
    assert record.model == "retry-model"


@pytest.mark.parametrize("runner", [Runner(fail=True), Runner(output=None), Runner(output={"changes": [], "summary": "x"})])
def test_a_failed_timed_out_or_invalid_comparison_falls_back_and_still_saves(runner) -> None:
    service, session, _, answer, _, attempts = setup(runner=runner)
    record = asyncio.run(service.create(session.id, answer.id, USER, AttemptCreate(answer=BETTER)))
    assert record.comparison and record.comparison.source == ComparisonSource.CHECKS
    assert record.model is None and len(attempts.rows) == 1


def test_the_candidate_view_hides_model_metadata() -> None:
    service, session, _, answer, _, _ = setup(runner=Runner(fail=True))
    view = attempt_view(asyncio.run(service.create(session.id, answer.id, USER, AttemptCreate(answer=BETTER))))
    dumped = view.model_dump()
    assert "model" not in dumped and "prompt_version" not in dumped and "user_id" not in dumped


# ------------------------------------------------------------------ routes


def test_attempt_routes_are_owner_scoped() -> None:
    from app.auth import get_token_verifier
    from app.dependencies import get_attempt_service
    from app.main import app
    from tests.test_role_agent import USER_A, USER_B, RoleVerifier

    sessions = MemorySessionRepository()
    session = asyncio.run(sessions.create(USER_A, SessionCreate(target_role="AR Analyst")))
    asyncio.run(sessions.update(session.id, USER_A, {"status": SessionStatus.COMPLETED}))
    answer = turn(session.id, 1, "CANDIDATE", FIRST)
    service = AttemptService(
        sessions, Transcript([turn(session.id, 0, "INTERVIEWER", "Tell me about a result."), answer]),
        MemoryAttemptRepository(), None, model="m",
    )
    previous = dict(app.dependency_overrides)  # other suites install their own overrides
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_attempt_service] = lambda: service
    try:
        with TestClient(app) as client:
            url = f"/api/v1/sessions/{session.id}/answers/{answer.id}/attempts"
            created = client.post(url, headers={"Authorization": "Bearer role-a"}, json={"answer": BETTER})
            assert created.status_code == 201 and created.json()["sequence"] == 1
            assert "model" not in created.json()
            assert client.post(url, headers={"Authorization": "Bearer role-b"}, json={"answer": BETTER}).status_code == 404
            listed = client.get(f"/api/v1/sessions/{session.id}/attempts", headers={"Authorization": "Bearer role-a"})
            assert listed.status_code == 200 and len(listed.json()) == 1
            assert client.get(f"/api/v1/sessions/{session.id}/attempts", headers={"Authorization": "Bearer role-b"}).status_code == 404
            assert client.post(url, json={"answer": BETTER}).status_code == 401
            assert client.post(url, headers={"Authorization": "Bearer role-a"}, json={"answer": "   "}).status_code == 422
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    assert USER_B != USER_A


# ------------------------------------------------------------------ review -> practice


@pytest.mark.asyncio
async def test_a_review_names_the_practice_that_works_on_its_growth_area() -> None:
    from app.dashboard_summary import build_latest_review
    from app.report_service import ReportService
    from tests.test_report import RESULT, SESSION, USER as REPORT_USER, FakeReportRepository

    report = await ReportService(FakeReportRepository(result={**RESULT, "root_cause_code": "OUTCOME_EVIDENCE"})).get_report(SESSION, REPORT_USER)
    assert build_latest_review(SESSION, report).practice_focus == "impact"
    report = await ReportService(FakeReportRepository(result={**RESULT, "root_cause_code": "TECHNICAL_DEPTH"})).get_report(SESSION, REPORT_USER)
    assert build_latest_review(SESSION, report).practice_focus == "decisions"


@pytest.mark.asyncio
async def test_a_review_without_a_known_growth_area_recommends_nothing() -> None:
    from app.dashboard_summary import build_latest_review
    from app.report_service import ReportService
    from tests.test_report import RESULT, SESSION, USER as REPORT_USER, FakeReportRepository

    report = await ReportService(FakeReportRepository(result={**RESULT, "root_cause_code": "SOMETHING_NEW"})).get_report(SESSION, REPORT_USER)
    assert build_latest_review(SESSION, report).practice_focus is None


def test_every_growth_area_maps_to_a_real_practice_area() -> None:
    from app.dashboard_summary import PRACTICE_FOCUS_FOR_ROOT_CAUSE, ROOT_CAUSE_TEXT
    from app.practice_modes import PracticeFocus

    assert set(PRACTICE_FOCUS_FOR_ROOT_CAUSE) == set(ROOT_CAUSE_TEXT)
    for focus in PRACTICE_FOCUS_FOR_ROOT_CAUSE.values():
        assert PracticeFocus(focus) != PracticeFocus.FULL
