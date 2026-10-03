"""Review -> story suggestions: grounded, exactly attributed, version-pinned, user-controlled."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import (
    get_interview_state_machine,
    get_onboarding_repository,
    get_practice_story_usage_repository,
    get_role_analysis_service,
    get_story_repository,
    get_story_suggestion_service,
)
from app.main import app
from app.story_suggestions import MemoryReviewFindingSource, MemoryStorySuggestionRepository, StorySuggestionService
from tests.test_practice_story_usage import A, B, Harness, _practice, _role, _story, _versions
from tests.test_role_agent import USER_A, MemoryOnboarding, RoleVerifier
from tests.test_role_agent import make_service as make_role_service


@pytest.fixture
def h():
    harness = Harness()
    harness.findings = MemoryReviewFindingSource()
    harness.suggestions = MemoryStorySuggestionRepository()
    service = StorySuggestionService(
        harness.suggestions, harness.findings, harness.usages, harness.stories, harness.sessions, min_confidence=0.8,
    )
    roles_service, _, _ = make_role_service()
    overrides = {
        get_token_verifier: lambda: RoleVerifier(),
        get_role_analysis_service: lambda: roles_service,
        get_interview_state_machine: lambda: harness.engine,
        get_story_repository: lambda: harness.stories,
        get_practice_story_usage_repository: lambda: harness.usages,
        get_onboarding_repository: lambda: MemoryOnboarding(),
        get_story_suggestion_service: lambda: service,
    }
    app.dependency_overrides.update(overrides)
    with TestClient(app) as client:
        harness.client = client
        yield harness
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def _finish(h, session_id, user=USER_A) -> UUID:
    session_id = UUID(str(session_id))
    asyncio.run(h.sessions.update(session_id, user, {"status": "COMPLETED"}))
    return session_id


def _answered(h, session_id, thread, kind, confidence=0.9, user=USER_A) -> UUID:
    """A candidate answer to plan objective `thread`, with one Skeptic observation about it."""
    turn = h.findings.answer(UUID(str(session_id)), thread)
    h.findings.observe(UUID(str(session_id)), user, turn, kind, confidence)
    return turn


def _review(h, session_id, headers=A):
    return h.client.get(f"/api/v1/sessions/{session_id}/story-suggestions", headers=headers)


def _practised(h, story_title="Fixing delivery delays", **values):
    role = _role(h)
    story = _story(h, story_title, **values)
    session = _practice(h, role, [story["id"]]).json()
    return role, story, session


# ------------------------------------------------------------------ creation


def test_an_ownership_finding_on_a_chosen_story_becomes_a_suggestion(h) -> None:
    role, story, session = _practised(h)
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    _finish(h, session["id"])

    [suggestion] = _review(h, session["id"]).json()
    assert suggestion["story_id"] == story["id"] and suggestion["role_profile_id"] == role
    assert (suggestion["issue_type"], suggestion["story_part"], suggestion["status"]) == ("OWNERSHIP_UNCLEAR", "ownership", "OPEN")
    assert suggestion["story_title"] == "Fixing delivery delays" and suggestion["practised_version"] == 1
    assert set(suggestion) >= {"practised_version", "current_version"} and "summary" not in suggestion  # no Skeptic wording


def test_a_scale_finding_points_at_the_measurable_result(h) -> None:
    _, _, session = _practised(h)
    _answered(h, session["id"], "story-1-2", "UNSUPPORTED_SCALE")
    _finish(h, session["id"])
    assert [(s["issue_type"], s["story_part"]) for s in _review(h, session["id"]).json()] == [("RESULT_UNSUPPORTED", "measurable_result")]


def test_nothing_is_suggested_without_grounded_exact_attribution(h) -> None:
    role, story, session = _practised(h)
    _answered(h, session["id"], "story-1-1", "VAGUENESS")  # names no story part
    _answered(h, session["id"], "story-1-1", "CONTRADICTION")
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT", confidence=0.5)  # below the Skeptic's own bar
    _answered(h, session["id"], "practice-story-1", "OWNERSHIP_DRIFT")  # a question not about a chosen story
    _answered(h, session["id"], None, "OWNERSHIP_DRIFT")  # an answer with no known question
    _answered(h, session["id"], "story-3-1", "OWNERSHIP_DRIFT")  # no story at that position
    _finish(h, session["id"])
    assert _review(h, session["id"]).json() == []

    plain = h.client.post("/api/v1/sessions", headers=A, json={
        "target_role": "Product Manager", "role_profile_id": role, "practice_mode": "QUICK_DRILL", "practice_focus": "story",
    }).json()
    _answered(h, plain["id"], "practice-story-1", "OWNERSHIP_DRIFT")
    _finish(h, plain["id"])
    assert _review(h, plain["id"]).json() == []  # no story was chosen for this practice
    assert h.suggestions.rows == {}


def test_no_suggestion_before_the_review_exists(h) -> None:
    _, _, session = _practised(h)
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    assert _review(h, session["id"]).json() == []  # practice not finished


def test_each_finding_attaches_only_to_the_story_it_was_about(h) -> None:
    role = _role(h)
    first, second = _story(h, "Fixing delivery delays"), _story(h, "Launching the pricing page")
    session = _practice(h, role, [first["id"], second["id"]]).json()
    _answered(h, session["id"], "story-2-2", "OWNERSHIP_DRIFT")  # about the second story
    _answered(h, session["id"], "story-1-3", "UNSUPPORTED_SCALE")  # about the first
    _finish(h, session["id"])
    found = {(s["story_id"], s["issue_type"]) for s in _review(h, session["id"]).json()}
    assert found == {(second["id"], "OWNERSHIP_UNCLEAR"), (first["id"], "RESULT_UNSUPPORTED")}


def test_reading_the_review_again_never_duplicates(h) -> None:
    _, story, session = _practised(h)
    turn = _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    h.findings.observe(UUID(session["id"]), USER_A, turn, "OWNERSHIP_DRIFT")  # a second observation, same answer
    _finish(h, session["id"])
    for _ in range(3):
        assert len(_review(h, session["id"]).json()) == 1
    assert len(h.client.get(f"/api/v1/stories/{story['id']}/suggestions", headers=A).json()) == 1
    assert len(h.suggestions.rows) == 1


# ------------------------------------------------------------------ versions and acceptance


def test_a_suggestion_stays_on_the_version_practised(h) -> None:
    _, story, session = _practised(h)
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    _finish(h, session["id"])
    h.client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"situation": "edited on its own"})  # v2, not from the suggestion

    [suggestion] = _review(h, session["id"]).json()
    assert (suggestion["practised_version"], suggestion["current_version"], suggestion["status"]) == (1, 2, "OPEN")
    assert h.suggestions.rows[UUID(suggestion["id"])][1].story_version_id == UUID(_versions(h, story["id"])[1])


def test_improving_the_part_accepts_the_suggestion_with_the_new_version(h) -> None:
    _, story, session = _practised(h, ownership="We shipped it")
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    _finish(h, session["id"])
    [suggestion] = _review(h, session["id"]).json()
    v1 = h.client.get(f"/api/v1/stories/{story['id']}/versions", headers=A).json()[0]

    saved = h.client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"ownership": "I chose the carrier and rebuilt the rota"}).json()
    accepted = h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/accept", headers=A, json={"saved_version": saved["current_version"]})
    assert accepted.status_code == 200
    assert (accepted.json()["status"], accepted.json()["resolved_version"], accepted.json()["practised_version"]) == ("ACCEPTED", 2, 1)
    versions = h.client.get(f"/api/v1/stories/{story['id']}/versions", headers=A).json()
    assert versions[-1] == v1  # the practised version is untouched
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/dismiss", headers=A).status_code == 409


def test_saving_without_changing_that_part_leaves_it_open(h) -> None:
    _, story, session = _practised(h, ownership="We shipped it")
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    _finish(h, session["id"])
    [suggestion] = _review(h, session["id"]).json()

    unchanged = h.client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"ownership": "We shipped it"}).json()
    assert unchanged["current_version"] == 1  # nothing to save, no version
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/accept", headers=A, json={"saved_version": 2}).status_code == 409
    other = h.client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"outcome": "a different part"}).json()
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/accept", headers=A, json={"saved_version": other["current_version"]}).status_code == 409
    assert _review(h, session["id"]).json()[0]["status"] == "OPEN"


def test_dismissing_leaves_the_story_unchanged(h) -> None:
    _, story, session = _practised(h)
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    _finish(h, session["id"])
    [suggestion] = _review(h, session["id"]).json()
    before = h.client.get(f"/api/v1/stories/{story['id']}", headers=A).json()

    dismissed = h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/dismiss", headers=A)
    assert dismissed.status_code == 200 and dismissed.json()["status"] == "DISMISSED"
    assert h.client.get(f"/api/v1/stories/{story['id']}", headers=A).json() == before
    assert [s["status"] for s in h.client.get(f"/api/v1/stories/{story['id']}/suggestions", headers=A).json()] == ["DISMISSED"]
    assert h.client.get("/api/v1/story-suggestions", headers=A).json() == []
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/accept", headers=A, json={"saved_version": 2}).status_code == 409


# ------------------------------------------------------------------ archive and roles


def test_archived_stories_keep_suggestions_but_cannot_be_improved_until_restored(h) -> None:
    _, story, session = _practised(h, ownership="We shipped it")
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    _finish(h, session["id"])
    h.client.post(f"/api/v1/stories/{story['id']}/archive", headers=A)

    [suggestion] = _review(h, session["id"]).json()
    assert suggestion["story_archived"] is True and suggestion["status"] == "OPEN"
    assert h.client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"ownership": "Mine"}).status_code == 409
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/accept", headers=A, json={"saved_version": 2}).status_code == 409

    h.client.post(f"/api/v1/stories/{story['id']}/restore", headers=A)
    saved = h.client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"ownership": "I chose the carrier"}).json()
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/accept", headers=A, json={"saved_version": saved["current_version"]}).status_code == 200


def test_a_suggestion_belongs_to_the_exact_role_practised(h) -> None:
    first, second = _role(h, "Product Manager"), _role(h, "Product Manager")
    story = _story(h)
    one = _practice(h, first, [story["id"]]).json()
    two = _practice(h, second, [story["id"]]).json()
    _answered(h, one["id"], "story-1-1", "OWNERSHIP_DRIFT")
    _finish(h, one["id"])
    _finish(h, two["id"])
    assert [s["role_profile_id"] for s in _review(h, one["id"]).json()] == [first]
    assert _review(h, two["id"]).json() == []  # the other same-named role's review shows nothing


# ------------------------------------------------------------------ ownership


def test_suggestions_never_cross_people(h) -> None:
    _, story, session = _practised(h, ownership="We shipped it")
    _answered(h, session["id"], "story-1-1", "OWNERSHIP_DRIFT")
    _answered(h, session["id"], "story-1-2", "OWNERSHIP_DRIFT", user=UUID("90000000-0000-4000-8000-000000000009"))
    _finish(h, session["id"])
    [suggestion] = _review(h, session["id"]).json()  # another person's observation on my session is ignored

    assert _review(h, session["id"], headers=B).status_code == 404
    assert h.client.get(f"/api/v1/stories/{story['id']}/suggestions", headers=B).status_code == 404
    assert h.client.get("/api/v1/story-suggestions", headers=B).json() == []
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/dismiss", headers=B).status_code == 404
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/accept", headers=B, json={"saved_version": 2}).status_code == 404
    their_story = _story(h, "Theirs", headers=B, ownership="x")
    theirs = h.client.patch(f"/api/v1/stories/{their_story['id']}", headers=B, json={"ownership": "y"}).json()
    # My suggestion cannot be resolved with a version number that only exists on their story.
    assert h.client.post(f"/api/v1/story-suggestions/{suggestion['id']}/accept", headers=A, json={"saved_version": theirs["current_version"]}).status_code == 409
    assert _review(h, session["id"]).json()[0]["status"] == "OPEN"
