"""Abandoning a practice: owner-only, idempotent, never reviewed, never counted, never shown as active."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import get_interview_state_machine
from app.home_service import SessionKind, activity_items, session_kind
from app.interview_engine import LEGAL_TRANSITIONS, InterviewStateMachine
from app.repository import MemorySessionRepository
from app.role_progress import eligible_practices
from app.routes_sessions_lifecycle import router
from app.schemas import SessionCreate, SessionStatus
from tests.test_home_service import NOW, build
from tests.test_role_agent import USER_A, USER_B, RoleVerifier
from tests.test_role_progress import profile, session

A = {"Authorization": "Bearer role-a"}
B = {"Authorization": "Bearer role-b"}


@pytest.fixture
def setup():
    repository = MemorySessionRepository()
    engine = InterviewStateMachine(repository, total_time_budget_seconds=1200, phase_time_budget_seconds=180)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_interview_state_machine] = lambda: engine
    with TestClient(app) as client:
        yield client, engine, repository


def create(engine, status: SessionStatus, user=USER_A):
    async def run():
        current = await engine.create_session_state(user, SessionCreate(target_role="Data Analyst"))
        steps = {
            SessionStatus.PREPARING: [engine.begin_preparation],
            SessionStatus.READY: [engine.begin_preparation, engine.mark_ready],
            SessionStatus.ACTIVE: [engine.begin_preparation, engine.mark_ready, engine.start],
            SessionStatus.ASSESSING: [engine.begin_preparation, engine.mark_ready, engine.start, engine.request_close],
            SessionStatus.COMPLETED: [engine.begin_preparation, engine.mark_ready, engine.start, engine.request_close, engine.complete],
        }
        for step in steps.get(status, []):
            current = await step(current.id, user)
        if status == SessionStatus.FAILED:
            current = await engine.fail(current.id, user, reason="test")
        assert current.status == status
        return current

    return asyncio.run(run())


@pytest.mark.parametrize("status", [SessionStatus.CREATED, SessionStatus.PREPARING, SessionStatus.READY, SessionStatus.ACTIVE])
def test_a_draft_or_active_practice_can_be_abandoned(setup, status) -> None:
    client, engine, repository = setup
    current = create(engine, status)
    response = client.post(f"/api/v1/sessions/{current.id}/abandon", headers=A)
    assert response.status_code == 200
    assert response.json()["status"] == "ABANDONED"
    events = [event.event_type for event in repository.events[current.id]]
    assert events[-1] == "SESSION_ABANDONED"


def test_abandoning_twice_is_harmless(setup) -> None:
    client, engine, repository = setup
    current = create(engine, SessionStatus.ACTIVE)
    first = client.post(f"/api/v1/sessions/{current.id}/abandon", headers=A)
    second = client.post(f"/api/v1/sessions/{current.id}/abandon", headers=A)
    assert first.status_code == second.status_code == 200
    assert second.json()["status"] == "ABANDONED"
    assert [e.event_type for e in repository.events[current.id]].count("SESSION_ABANDONED") == 1


@pytest.mark.parametrize("status", [SessionStatus.ASSESSING, SessionStatus.COMPLETED, SessionStatus.FAILED])
def test_a_finished_practice_cannot_be_abandoned(setup, status) -> None:
    client, engine, _ = setup
    current = create(engine, status)
    response = client.post(f"/api/v1/sessions/{current.id}/abandon", headers=A)
    assert response.status_code == 409
    assert asyncio.run(engine.get_state(current.id, USER_A)).status == status


def test_another_persons_session_is_not_found(setup) -> None:
    client, engine, _ = setup
    current = create(engine, SessionStatus.ACTIVE, user=USER_B)
    assert client.post(f"/api/v1/sessions/{current.id}/abandon", headers=A).status_code == 404
    assert client.post(f"/api/v1/sessions/{current.id}/abandon").status_code == 401
    assert asyncio.run(engine.get_state(current.id, USER_B)).status == SessionStatus.ACTIVE


def test_abandoned_is_terminal_and_never_leads_to_a_review() -> None:
    assert LEGAL_TRANSITIONS[SessionStatus.ABANDONED] == frozenset()
    for status in (SessionStatus.ASSESSING, SessionStatus.COMPLETED, SessionStatus.FAILED):
        assert SessionStatus.ABANDONED not in LEGAL_TRANSITIONS[status]
    # The route depends only on the engine: no assessment repository, so no review can be enqueued.
    abandon = next(route for route in router.routes if route.path.endswith("/abandon"))
    names = {dependency.call.__name__ for dependency in abandon.dependant.dependencies}
    assert "get_assessment_pipeline_repository" not in names


def test_abandoned_practice_is_not_active_and_not_counted() -> None:
    role = profile(USER_A)
    abandoned = session(role.id, days_ago=0, status="ABANDONED", available=False)
    assert session_kind(abandoned) == SessionKind.OTHER
    assert eligible_practices([abandoned], frozenset({role.id})) == []
    assert activity_items([abandoned], []) == []


@pytest.mark.asyncio
async def test_home_never_shows_an_abandoned_practice() -> None:
    service, analyst, _, _ = build(lambda a, m: [session(a.id, days_ago=0, status="ABANDONED", available=False)])
    result = await service.home(analyst.user_id, analyst.id, now=NOW)
    assert result.state.value == "FIRST_PRACTICE"
    assert result.active is None and result.other_active is None and result.review is None
    assert result.progress.practice_count == 0 and result.activity == []
