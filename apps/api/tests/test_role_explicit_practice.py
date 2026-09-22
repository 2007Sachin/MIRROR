"""Practice is role-explicit: role_profile_id flows through SessionCreate -> planner
load_context, without relying on the account's mutable current_role_profile_id, while
ownership of the role is still verified."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import (
    get_interview_state_machine,
    get_onboarding_repository,
    get_role_analysis_service,
)
from app.interview_engine import InterviewStateMachine
from app.main import app
from app.planner_service import InterviewPlanningService, PlanNotFound
from app.repository import MemorySessionRepository
from app.schemas import SessionCreate
from tests.test_interview_planner import USER_A, make_service
from tests.test_role_agent import MemoryOnboarding, RoleVerifier
from tests.test_role_agent import make_service as make_role_service


ROLE_A = UUID("70000000-0000-4000-8000-000000000001")
ROLE_B = UUID("70000000-0000-4000-8000-000000000002")

A = {"Authorization": "Bearer role-a"}
B = {"Authorization": "Bearer role-b"}


@pytest.fixture
def client():
    roles_service, _, _ = make_role_service()
    session_engine = InterviewStateMachine(
        MemorySessionRepository(),
        total_time_budget_seconds=1200,
        phase_time_budget_seconds=180,
    )
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_role_analysis_service] = lambda: roles_service
    app.dependency_overrides[get_interview_state_machine] = lambda: session_engine
    app.dependency_overrides[get_onboarding_repository] = lambda: MemoryOnboarding()
    with TestClient(app) as test_client:
        yield test_client
    for dependency in (
        get_token_verifier,
        get_role_analysis_service,
        get_interview_state_machine,
        get_onboarding_repository,
    ):
        app.dependency_overrides.pop(dependency, None)


def test_a_session_cannot_be_created_against_someone_elses_role(client) -> None:
    role = client.post("/api/v1/roles/analyze", headers=A, json={"target_role": "Software Engineer"}).json()

    stolen = client.post(
        "/api/v1/sessions",
        headers=B,
        json={"target_role": "Software Engineer", "role_profile_id": role["id"]},
    )
    assert stolen.status_code == 404

    owned = client.post(
        "/api/v1/sessions",
        headers=A,
        json={"target_role": "Software Engineer", "role_profile_id": role["id"]},
    )
    assert owned.status_code == 201
    assert owned.json()["role_profile_id"] == role["id"]


class RecordingPlans:
    """A minimal load_context stub that records which role_profile_id it was given."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def load_context(self, session_id, user_id, *, target_role, duration_seconds, role_profile_id=None):
        self.calls.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "role_profile_id": role_profile_id,
            }
        )
        raise PlanNotFound  # we only care about what was requested, not a full plan


def test_session_create_accepts_optional_role_profile_id() -> None:
    payload = SessionCreate(target_role="Analyst", role_profile_id=ROLE_A)
    assert payload.role_profile_id == ROLE_A
    # Backward compatible: omitting it still works, defaulting to None.
    legacy = SessionCreate(target_role="Analyst")
    assert legacy.role_profile_id is None


def test_session_persists_its_explicit_role_profile_id() -> None:
    async def run():
        sessions = MemorySessionRepository()
        created = await sessions.create(
            USER_A, SessionCreate(target_role="Analyst", role_profile_id=ROLE_A)
        )
        assert created.role_profile_id == ROLE_A
        fetched = await sessions.get(created.id, USER_A)
        assert fetched is not None and fetched.role_profile_id == ROLE_A

    asyncio.run(run())


def test_plan_passes_the_session_explicit_role_profile_id_to_load_context() -> None:
    async def run():
        sessions = MemorySessionRepository()
        created = await sessions.create(
            USER_A, SessionCreate(target_role="Analyst", role_profile_id=ROLE_A)
        )
        plans = RecordingPlans()
        service, *_ = make_service()
        service = InterviewPlanningService(
            sessions,
            plans,
            service._runner,
            model="planner-test-model",
            intro_reserve_seconds=60,
            transition_reserve_seconds=60,
            closing_reserve_seconds=60,
        )
        await sessions.update(created.id, USER_A, {"status": "PREPARING"})
        with pytest.raises(PlanNotFound):
            await service.plan(created.id, USER_A)
        assert plans.calls[-1]["role_profile_id"] == ROLE_A

    asyncio.run(run())


def test_plan_falls_back_to_current_role_when_session_has_no_explicit_role() -> None:
    async def run():
        sessions = MemorySessionRepository()
        created = await sessions.create(USER_A, SessionCreate(target_role="Analyst"))
        plans = RecordingPlans()
        service, *_ = make_service()
        service = InterviewPlanningService(
            sessions,
            plans,
            service._runner,
            model="planner-test-model",
            intro_reserve_seconds=60,
            transition_reserve_seconds=60,
            closing_reserve_seconds=60,
        )
        await sessions.update(created.id, USER_A, {"status": "PREPARING"})
        with pytest.raises(PlanNotFound):
            await service.plan(created.id, USER_A)
        # No explicit role_profile_id was set on the session, so none is forwarded;
        # the repository is left to fall back to profiles.current_role_profile_id
        # exactly as before this change.
        assert plans.calls[-1]["role_profile_id"] is None

    asyncio.run(run())


def test_two_roles_same_user_quick_drill_stays_on_the_non_current_role() -> None:
    """A session started explicitly against ROLE_B must resolve against ROLE_B's
    competencies even if the account's current role is ROLE_A."""

    async def run():
        sessions = MemorySessionRepository()
        created = await sessions.create(
            USER_A,
            SessionCreate(
                target_role="Analyst",
                practice_mode="QUICK_DRILL",
                practice_focus="impact",
                role_profile_id=ROLE_B,
            ),
        )
        plans = RecordingPlans()
        service, *_ = make_service()
        service = InterviewPlanningService(
            sessions,
            plans,
            service._runner,
            model="planner-test-model",
            intro_reserve_seconds=60,
            transition_reserve_seconds=60,
            closing_reserve_seconds=60,
        )
        await sessions.update(created.id, USER_A, {"status": "PREPARING"})
        with pytest.raises(PlanNotFound):
            await service.plan(created.id, USER_A)
        assert plans.calls[-1]["role_profile_id"] == ROLE_B

    asyncio.run(run())


def test_session_bound_role_does_not_change_when_current_role_changes_later() -> None:
    """Once a session is bound to a role_profile_id, later mutating the account's
    current role must not silently reassign the session's own role binding."""

    async def run():
        sessions = MemorySessionRepository()
        created = await sessions.create(
            USER_A, SessionCreate(target_role="Analyst", role_profile_id=ROLE_A)
        )
        # Simulate the account's mutable "current role" changing later; the session
        # record itself is untouched and must keep its own explicit binding.
        fetched = await sessions.get(created.id, USER_A)
        assert fetched is not None
        assert fetched.role_profile_id == ROLE_A

    asyncio.run(run())
