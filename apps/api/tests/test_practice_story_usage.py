"""Practice <-> story usage: recorded only for stories the candidate chose, at the exact version
practised, tied to the exact role, never rewritten, and never a score."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import (
    get_interview_state_machine,
    get_onboarding_repository,
    get_practice_story_usage_repository,
    get_role_analysis_service,
    get_story_repository,
)
from app.interview_engine import InterviewStateMachine
from app.main import app
from app.planner_service import InterviewPlanningService
from app.practice_story_usage import (
    MemoryPracticeStoryUsageRepository,
    UsageRejected,
    practice_story_versions,
)
from app.repository import MemorySessionRepository
from app.schemas import SessionCreate
from app.story_repository import MemoryStoryRepository
from tests.test_interview_planner import MemoryPlans, context
from tests.test_interview_planner import make_service as make_planner_service
from tests.test_role_agent import USER_A, MemoryOnboarding, RoleVerifier
from tests.test_role_agent import make_service as make_role_service

A = {"Authorization": "Bearer role-a"}
B = {"Authorization": "Bearer role-b"}


class RolePlans(MemoryPlans):
    """The planner test double, accepting the explicit role a story practice always has."""

    async def load_context(self, session_id, user_id, *, target_role, duration_seconds, role_profile_id=None):
        return await super().load_context(session_id, user_id, target_role=target_role, duration_seconds=duration_seconds)


class Harness:
    def __init__(self) -> None:
        self.sessions = MemorySessionRepository()
        self.stories = MemoryStoryRepository()
        self.usages = MemoryPracticeStoryUsageRepository(self.sessions, self.stories)
        self.engine = InterviewStateMachine(self.sessions, total_time_budget_seconds=1200, phase_time_budget_seconds=180)
        self.plans = RolePlans()
        runner = make_planner_service()[0]._runner

        async def pinned(session_id, user_id):
            return await practice_story_versions(self.usages, self.stories, session_id, user_id)

        self.planner = InterviewPlanningService(
            self.sessions, self.plans, runner, model="planner-test-model",
            intro_reserve_seconds=60, transition_reserve_seconds=60, closing_reserve_seconds=60,
            story_versions=pinned,
        )

    def plan_questions(self, session_id, user=USER_A) -> list[str]:
        session_id = UUID(str(session_id))

        async def run():
            self.plans.contexts[session_id] = context(session_id)
            await self.sessions.update(session_id, user, {"status": "PREPARING"})
            record = await self.planner.plan(session_id, user)
            return [objective.initial_question for objective in record.plan.objectives]
        return asyncio.run(run())

    def start(self, session_id, user=USER_A) -> None:
        asyncio.run(self.sessions.update(UUID(str(session_id)), user, {"status": "ACTIVE", "started_at": datetime.now(UTC)}))


@pytest.fixture
def harness():
    h = Harness()
    roles_service, _, _ = make_role_service()
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_role_analysis_service] = lambda: roles_service
    app.dependency_overrides[get_interview_state_machine] = lambda: h.engine
    app.dependency_overrides[get_story_repository] = lambda: h.stories
    app.dependency_overrides[get_practice_story_usage_repository] = lambda: h.usages
    app.dependency_overrides[get_onboarding_repository] = lambda: MemoryOnboarding()
    with TestClient(app) as client:
        h.client = client
        yield h
    for dependency in (
        get_token_verifier, get_role_analysis_service, get_interview_state_machine,
        get_story_repository, get_practice_story_usage_repository, get_onboarding_repository,
    ):
        app.dependency_overrides.pop(dependency, None)


def _role(h, label="Product Manager", headers=A) -> str:
    return h.client.post("/api/v1/roles/analyze", headers=headers, json={"target_role": label}).json()["id"]


def _story(h, title="Fixing delivery delays", headers=A, **values) -> dict:
    response = h.client.post("/api/v1/stories", headers=headers, json={"title": title, **values})
    assert response.status_code == 201
    return response.json()


def _versions(h, story_id, headers=A) -> dict[int, str]:
    return {item["version"]: item["id"] for item in h.client.get(f"/api/v1/stories/{story_id}/versions", headers=headers).json()}


def _practice(h, role_id, story_ids, headers=A, mode="QUICK_DRILL", focus="story", **extra):
    return h.client.post("/api/v1/sessions", headers=headers, json={
        "target_role": "Product Manager", "practice_mode": mode, "practice_focus": focus,
        "role_profile_id": role_id, "story_ids": story_ids, **extra,
    })


def _used(h, session_id, headers=A) -> list[dict]:
    response = h.client.get(f"/api/v1/sessions/{session_id}/stories", headers=headers)
    assert response.status_code == 200
    return response.json()


# ------------------------------------------------------------------ creation and planning


def test_a_chosen_story_is_recorded_and_the_plan_is_built_from_it(harness) -> None:
    role = _role(harness)
    story = _story(harness)
    session = _practice(harness, role, [story["id"]])
    assert session.status_code == 201

    [usage] = _used(harness, session.json()["id"])
    assert usage["story_id"] == story["id"] and usage["story_version_id"] == _versions(harness, story["id"])[1]
    assert usage["role_profile_id"] == role and usage["position"] == 1

    questions = harness.plan_questions(session.json()["id"])
    assert len(questions) == 3 and all("Fixing delivery delays" in question for question in questions)


def test_two_chosen_stories_are_both_recorded_and_both_asked_about(harness) -> None:
    role = _role(harness)
    first, second = _story(harness, "Fixing delivery delays"), _story(harness, "Launching the pricing page")
    session = _practice(harness, role, [first["id"], second["id"]]).json()

    used = _used(harness, session["id"])
    assert [(item["story_id"], item["position"]) for item in used] == [(first["id"], 1), (second["id"], 2)]
    questions = harness.plan_questions(session["id"])
    assert "Fixing delivery delays" in questions[0] and "Launching the pricing page" in questions[1]
    assert "Fixing delivery delays" in questions[2]


def test_practice_without_a_chosen_story_records_nothing(harness) -> None:
    role = _role(harness)
    _story(harness, themes=["Delivery"], role_profile_id=role)  # relevant to the role, but not chosen
    for body in (
        {"practice_mode": "QUICK_DRILL", "practice_focus": "story"},
        {"practice_mode": "QUICK_DRILL", "practice_focus": "role", "practice_theme": "Delivery"},
        {},
    ):
        session = harness.client.post("/api/v1/sessions", headers=A, json={"target_role": "Product Manager", "role_profile_id": role, **body})
        assert session.status_code == 201 and _used(harness, session.json()["id"]) == []
    generic = harness.client.post("/api/v1/sessions", headers=A, json={
        "target_role": "Product Manager", "role_profile_id": role, "practice_mode": "QUICK_DRILL", "practice_focus": "story",
    }).json()
    assert not any("Fixing delivery delays" in question for question in harness.plan_questions(generic["id"]))
    assert harness.usages.rows == []


def test_replaying_the_same_request_never_duplicates_usage(harness) -> None:
    role = _role(harness)
    story = _story(harness)
    key = str(uuid4())
    first = _practice(harness, role, [story["id"]], idempotency_key=key).json()
    harness.client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"situation": "edited before the replay"})
    again = _practice(harness, role, [story["id"]], idempotency_key=key).json()

    assert again["id"] == first["id"]
    [usage] = _used(harness, first["id"])
    assert usage["story_version_id"] == _versions(harness, story["id"])[1]  # still the version first chosen
    assert len(harness.usages.rows) == 1


# ------------------------------------------------------------------ versions, archive, restore


def test_an_old_practice_keeps_the_version_it_used(harness) -> None:
    role = _role(harness)
    story = _story(harness, "Fixing delivery delays")
    old = _practice(harness, role, [story["id"]]).json()
    harness.client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"title": "Cutting delivery delays by a third"})
    new = _practice(harness, role, [story["id"]]).json()

    versions = _versions(harness, story["id"])
    assert _used(harness, old["id"])[0]["story_version_id"] == versions[1]
    assert _used(harness, new["id"])[0]["story_version_id"] == versions[2]
    # Planning after the edit still uses the version the old practice was set up with.
    assert all("Fixing delivery delays" in question for question in harness.plan_questions(old["id"]))
    assert all("Cutting delivery delays" in question for question in harness.plan_questions(new["id"]))

    history = harness.client.get(f"/api/v1/stories/{story['id']}/practice", headers=A).json()
    assert {item["session_id"]: item["story_version"] for item in history} == {old["id"]: 1, new["id"]: 2}


def test_archived_stories_cannot_be_chosen_but_keep_their_practice_history(harness) -> None:
    role = _role(harness)
    story = _story(harness)
    old = _practice(harness, role, [story["id"]]).json()
    harness.client.post(f"/api/v1/stories/{story['id']}/archive", headers=A)

    sessions_before = len(harness.sessions.sessions)
    assert _practice(harness, role, [story["id"]]).status_code == 409
    assert len(harness.sessions.sessions) == sessions_before  # no session was created
    history = harness.client.get(f"/api/v1/stories/{story['id']}/practice", headers=A).json()
    assert [item["session_id"] for item in history] == [old["id"]]

    harness.client.post(f"/api/v1/stories/{story['id']}/restore", headers=A)
    again = _practice(harness, role, [story["id"]])
    assert again.status_code == 201
    history = harness.client.get(f"/api/v1/stories/{story['id']}/practice", headers=A).json()
    assert {item["session_id"] for item in history} == {old["id"], again.json()["id"]}


def test_usage_is_tied_to_the_exact_role_even_with_the_same_name(harness) -> None:
    first, second = _role(harness, "Product Manager"), _role(harness, "Product Manager")
    assert first != second
    story = _story(harness)
    one = _practice(harness, first, [story["id"]]).json()
    two = _practice(harness, second, [story["id"]]).json()
    history = {item["session_id"]: item["role_profile_id"] for item in harness.client.get(f"/api/v1/stories/{story['id']}/practice", headers=A).json()}
    assert history == {one["id"]: first, two["id"]: second}


def test_only_started_practices_count_and_no_score_is_given(harness) -> None:
    role = _role(harness)
    story, untouched = _story(harness), _story(harness, "Never practised")
    started = _practice(harness, role, [story["id"]]).json()
    _practice(harness, role, [story["id"]])  # set up but never started
    harness.start(started["id"])

    summaries = {item["story_id"]: item for item in harness.client.get("/api/v1/story-practice", headers=A).json()}
    assert summaries[story["id"]]["practice_count"] == 1 and summaries[story["id"]]["last_practiced_at"]
    assert untouched["id"] not in summaries
    assert set(summaries[story["id"]]) == {"story_id", "practice_count", "last_practiced_at"}


# ------------------------------------------------------------------ validation and ownership


def test_story_practice_requests_are_validated(harness) -> None:
    role = _role(harness)
    story = _story(harness)
    assert _practice(harness, None, [story["id"]]).status_code == 422  # needs the exact role
    assert _practice(harness, role, [story["id"]], mode="FULL_INTERVIEW", focus=None).status_code == 422
    assert _practice(harness, role, [story["id"]], focus="impact").status_code == 422
    assert _practice(harness, role, [story["id"], story["id"]]).status_code == 422
    many = [_story(harness, f"Story {n}")["id"] for n in range(4)]
    assert _practice(harness, role, many).status_code == 422  # a quick drill has three questions
    assert _practice(harness, role, many, mode="FOCUSED_PRACTICE").status_code == 201
    assert _practice(harness, role, [str(uuid4())]).status_code == 404


def test_stories_sessions_and_roles_never_cross_people(harness) -> None:
    mine, theirs = _role(harness, headers=A), _role(harness, headers=B)
    story = _story(harness, headers=A)
    their_story = _story(harness, headers=B, title="Their story")
    session = _practice(harness, mine, [story["id"]]).json()

    assert _practice(harness, theirs, [story["id"]], headers=B).status_code == 404  # my story, their session
    assert _practice(harness, mine, [their_story["id"]]).status_code == 404  # their story, my session
    assert _practice(harness, theirs, [story["id"]]).status_code == 404  # their role
    assert harness.client.get(f"/api/v1/sessions/{session['id']}/stories", headers=B).status_code == 404
    assert harness.client.get(f"/api/v1/stories/{story['id']}/practice", headers=B).status_code == 404
    assert harness.client.get("/api/v1/story-practice", headers=B).json() == []
    assert harness.client.get(f"/api/v1/sessions/{session['id']}/stories").status_code == 401
    assert len(harness.usages.rows) == 1


def test_the_usage_store_rejects_mismatched_links() -> None:
    async def run():
        from tests.test_role_agent import USER_B

        h = Harness()
        role, other_role = uuid4(), uuid4()
        from app.story_models import StoryCreate

        story = await h.stories.create(USER_A, StoryCreate(title="Mine"))
        other = await h.stories.create(USER_A, StoryCreate(title="Other"))
        [version] = await h.stories.versions(story.id, USER_A)
        [other_version] = await h.stories.versions(other.id, USER_A)
        session = await h.sessions.create(USER_A, SessionCreate(
            target_role="PM", practice_mode="QUICK_DRILL", practice_focus="story", role_profile_id=role,
        ))
        with pytest.raises(UsageRejected):  # role other than the session's
            await h.usages.record(USER_A, session.id, other_role, [version])
        with pytest.raises(UsageRejected):  # someone else's session
            await h.usages.record(USER_B, session.id, role, [version])
        with pytest.raises(UsageRejected):  # a version of a different story
            await h.usages.record(USER_A, session.id, role, [version.model_copy(update={"id": other_version.id})])
        assert h.usages.rows == []

    asyncio.run(run())
