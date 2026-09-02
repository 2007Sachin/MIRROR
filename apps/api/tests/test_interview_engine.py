from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.dependencies import get_interview_planning_service, get_interview_state_machine
from app.interview_engine import (
    IllegalSessionTransition,
    InterviewFlowRejected,
    InterviewStateMachine,
    SessionNotFound,
)
from app.main import app
from app.repository import MemorySessionRepository
from app.schemas import Phase, SessionCreate, SessionStatus


USER_A = UUID("30000000-0000-4000-8000-000000000003")
USER_B = UUID("40000000-0000-4000-8000-000000000004")


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def make_engine(
    *, duration: int = 1200
) -> tuple[InterviewStateMachine, MemorySessionRepository, MutableClock]:
    repository = MemorySessionRepository()
    clock = MutableClock()
    engine = InterviewStateMachine(
        repository,
        total_time_budget_seconds=duration,
        phase_time_budget_seconds=180,
        clock=clock,
    )
    return engine, repository, clock


async def ready_session(engine: InterviewStateMachine):
    created = await engine.create_session_state(
        USER_A, SessionCreate(target_role="Data Analyst")
    )
    return await engine.prepare(created.id, USER_A)


async def active_session(engine: InterviewStateMachine):
    ready = await ready_session(engine)
    return await engine.start(ready.id, USER_A)


def test_legal_status_transitions_and_completion() -> None:
    engine, _, _ = make_engine()
    ready = asyncio.run(ready_session(engine))
    assert ready.status == SessionStatus.READY
    active = asyncio.run(engine.start(ready.id, USER_A))
    assert active.status == SessionStatus.ACTIVE
    assessing = asyncio.run(engine.request_close(active.id, USER_A))
    assert assessing.status == SessionStatus.ASSESSING
    completed = asyncio.run(engine.complete(active.id, USER_A))
    assert completed.status == SessionStatus.COMPLETED
    assert completed.phase == Phase.COMPLETE
    assert completed.completion_pct == 100


def test_illegal_transition_is_rejected() -> None:
    engine, _, _ = make_engine()
    created = asyncio.run(
        engine.create_session_state(USER_A, SessionCreate(target_role="Data Analyst"))
    )
    with pytest.raises(IllegalSessionTransition):
        asyncio.run(engine.start(created.id, USER_A))
    with pytest.raises(IllegalSessionTransition):
        asyncio.run(engine.complete(created.id, USER_A))


def test_phase_progression_is_ordered() -> None:
    engine, _, _ = make_engine()
    active = asyncio.run(active_session(engine))
    background = asyncio.run(engine.advance_phase(active.id, USER_A))
    projects = asyncio.run(engine.advance_phase(active.id, USER_A))
    assert background.phase == Phase.BACKGROUND
    assert projects.phase == Phase.PROJECTS
    assert projects.current_probe_count == 0


def test_two_probes_allowed_third_rejected_and_recovery_required() -> None:
    engine, _, _ = make_engine()
    active = asyncio.run(active_session(engine))
    primary = asyncio.run(
        engine.register_primary_question(active.id, USER_A, "background-1")
    )
    assert primary.total_questions == 1
    first = asyncio.run(engine.register_probe(active.id, USER_A))
    second = asyncio.run(engine.register_probe(active.id, USER_A))
    assert first.current_probe_count == 1
    assert second.current_probe_count == 2
    assert asyncio.run(engine.must_recover(active.id, USER_A)) is True
    with pytest.raises(InterviewFlowRejected):
        asyncio.run(engine.register_probe(active.id, USER_A))
    recovered = asyncio.run(engine.trigger_recovery(active.id, USER_A))
    assert recovered.current_probe_count == 0
    assert recovered.current_primary_question_id is None
    assert recovered.recovery_count == 1


def test_one_turn_late_flag_eligibility() -> None:
    assert (
        InterviewStateMachine.flag_is_eligible(detected_at_turn=7, current_turn=7)
        is False
    )
    assert (
        InterviewStateMachine.flag_is_eligible(detected_at_turn=7, current_turn=8)
        is True
    )
    assert (
        InterviewStateMachine.flag_is_eligible(detected_at_turn=7, current_turn=10)
        is True
    )


def test_time_budget_expiry_prevents_questions_and_probes() -> None:
    engine, _, clock = make_engine(duration=60)
    active = asyncio.run(active_session(engine))
    asyncio.run(engine.register_primary_question(active.id, USER_A, "intro-1"))
    clock.advance(60)
    assert asyncio.run(engine.can_ask_question(active.id, USER_A)) is False
    assert asyncio.run(engine.can_ask_question(active.id, USER_A, probe=True)) is False
    with pytest.raises(InterviewFlowRejected):
        asyncio.run(engine.register_probe(active.id, USER_A))


def test_configured_budget_is_fixed_in_created_state() -> None:
    engine, _, _ = make_engine(duration=900)
    created = asyncio.run(
        engine.create_session_state(USER_A, SessionCreate(target_role="Data Analyst"))
    )
    assert created.total_time_budget_seconds == 900
    assert created.phase_time_budget_seconds == 180


def test_migration_enforces_probe_and_budget_rules() -> None:
    migration = Path(
        "supabase/migrations/202609010008_interview_session_engine.sql"
    ).read_text()
    assert "sessions_probe_cap" in migration
    assert "time budget cannot be extended after start" in migration
    assert "apply_interview_state_change" in migration


def test_owner_isolation() -> None:
    engine, _, _ = make_engine()
    created = asyncio.run(
        engine.create_session_state(USER_A, SessionCreate(target_role="Data Analyst"))
    )
    with pytest.raises(SessionNotFound):
        asyncio.run(engine.get_state(created.id, USER_B))
    with pytest.raises(SessionNotFound):
        asyncio.run(engine.prepare(created.id, USER_B))


def test_events_capture_state_and_probe_changes() -> None:
    engine, _, _ = make_engine()
    active = asyncio.run(active_session(engine))
    asyncio.run(engine.register_primary_question(active.id, USER_A, "intro-1"))
    asyncio.run(engine.register_probe(active.id, USER_A))
    asyncio.run(engine.register_probe(active.id, USER_A))
    asyncio.run(engine.trigger_recovery(active.id, USER_A))
    event_types = [
        event.event_type for event in asyncio.run(engine.get_events(active.id, USER_A))
    ]
    assert event_types == [
        "SESSION_CREATED",
        "SESSION_PREPARING",
        "SESSION_PREPARED",
        "SESSION_STARTED",
        "PRIMARY_QUESTION_STARTED",
        "PROBE_REGISTERED",
        "PROBE_REGISTERED",
        "PROBE_LIMIT_REACHED",
        "RECOVERY_TRIGGERED",
    ]


class EngineVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token == "engine-a":
            return AuthenticatedUser(id=USER_A, email="a@example.com")
        if token == "engine-b":
            return AuthenticatedUser(id=USER_B, email="b@example.com")
        raise InvalidAccessToken


@pytest.fixture
def engine_client() -> TestClient:
    engine, _, _ = make_engine()

    class CompletedPlanning:
        async def plan(self, session_id, user_id):
            return type("Plan", (), {"status": "COMPLETED"})()

    previous_verifier = app.dependency_overrides.get(get_token_verifier)
    previous_engine = app.dependency_overrides.get(get_interview_state_machine)
    previous_planning = app.dependency_overrides.get(get_interview_planning_service)
    app.dependency_overrides[get_token_verifier] = lambda: EngineVerifier()
    app.dependency_overrides[get_interview_state_machine] = lambda: engine
    app.dependency_overrides[get_interview_planning_service] = (
        lambda: CompletedPlanning()
    )
    with TestClient(app) as client:
        yield client
    if previous_verifier is None:
        app.dependency_overrides.pop(get_token_verifier, None)
    else:
        app.dependency_overrides[get_token_verifier] = previous_verifier
    if previous_engine is None:
        app.dependency_overrides.pop(get_interview_state_machine, None)
    else:
        app.dependency_overrides[get_interview_state_machine] = previous_engine
    if previous_planning is None:
        app.dependency_overrides.pop(get_interview_planning_service, None)
    else:
        app.dependency_overrides[get_interview_planning_service] = previous_planning


def test_v1_session_endpoints_and_isolation(engine_client: TestClient) -> None:
    created = engine_client.post(
        "/api/v1/sessions",
        headers={"Authorization": "Bearer engine-a"},
        json={"target_role": "Data Analyst"},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert created.json()["status"] == "CREATED"
    assert (
        engine_client.post(
            f"/api/v1/sessions/{session_id}/prepare",
            headers={"Authorization": "Bearer engine-a"},
        ).json()["session"]["status"]
        == "READY"
    )
    assert (
        engine_client.post(
            f"/api/sessions/{session_id}/start",
            headers={"Authorization": "Bearer engine-a"},
        ).json()["status"]
        == "ACTIVE"
    )
    ended = engine_client.post(
        f"/api/v1/sessions/{session_id}/end",
        headers={"Authorization": "Bearer engine-a"},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "COMPLETED"
    assert (
        engine_client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"Authorization": "Bearer engine-b"},
        ).status_code
        == 404
    )

