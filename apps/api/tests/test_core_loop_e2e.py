"""HTTP loop: Quick drill, text answers, assessment, review. No live providers."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from app.agents import AgentRegistry, AgentRunner, PromptLoader
from app.agents.definitions import ProviderRequest, ProviderResponse
from app.agents.interviewer import create_interviewer_agent
from app.agents.planner import create_planner_agent
from app.assessment_pipeline_models import AssessmentPipelineStatus
from app.assessment_pipeline_repository import STALE_FAILURE_CODE, MemoryAssessmentPipelineRepository
from app.assessment_worker import AssessmentWorker
from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.dependencies import (
    get_assessment_pipeline_repository,
    get_interview_planning_service,
    get_interview_state_machine,
    get_report_service,
    get_repository,
    get_text_interview_service,
)
from app.final_assessment_aggregator import FinalAssessmentAggregator
from app.interview_engine import InterviewStateMachine
from app.interviewer_context import InterviewerContextBuilder
from app.interviewer_service import TextInterviewService
from app.main import app
from app.planner_service import InterviewPlanningService
from app.report_service import ReportService
from app.repository import MemorySessionRepository
from tests.test_assessment_pipeline import FakeAudit, FakeVerdict, NoopAdjudicator, SuccessfulOrchestrator
from tests.test_interview_planner import MemoryPlans, context
from tests.test_interviewer_agent import MemoryTurns
from tests.test_report import verified_specialists


USER = UUID("90000000-0000-4000-8000-000000000009")
AUTH = {"Authorization": "Bearer loop-owner"}
FOLLOW_UP = "What changed because of your work?"
LABELS = {
    "Strong",
    "Clear",
    "Developing",
    "Could go further",
    "Needs attention",
    "Not enough to say yet",
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class RecordingProvider:
    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []

    async def complete(self, request: ProviderRequest, *, timeout_seconds: float) -> ProviderResponse:
        self.requests.append(request)
        payload = json.loads(request.messages[1]["content"])
        thread = payload.get("primary_thread_id") or payload["objective"]["objective_id"]
        return ProviderResponse(content={
            "action": "ASK",
            "question_text": FOLLOW_UP,
            "turn_type": "DEPTH_PROBE",
            "target_claim_ids": [],
            "target_competency_ids": [],
            "primary_thread_id": thread,
            "reason_code": "NEED_MORE_DEPTH",
            "requested_phase_transition": None,
            "used_flag_id": None,
        })


class GuardProvider:
    """Fails the test if the planner agent is invoked."""

    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []

    async def complete(self, request: ProviderRequest, *, timeout_seconds: float) -> ProviderResponse:
        self.requests.append(request)
        raise AssertionError("quick drill must not call the planner")


class DrillPlans(MemoryPlans):
    async def load_context(self, session_id, user_id, *, target_role, duration_seconds, role_profile_id=None):
        item = self.contexts.get(session_id)
        if item is None:
            built = context(session_id)
            if built.planner_input.target_role != target_role:
                built = built.model_copy(update={
                    "planner_input": built.planner_input.model_copy(update={"target_role": target_role}),
                })
            self.contexts[session_id] = built
            item = built
        return item


class ResultAssessment(MemoryAssessmentPipelineRepository):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.saved: dict[tuple[UUID, UUID], dict] = {}

    async def persist_result(self, session_id, user_id, aggregate, language, *, model, prompt_version):
        await super().persist_result(
            session_id, user_id, aggregate, language, model=model, prompt_version=prompt_version,
        )
        self.saved[(session_id, user_id)] = {
            "role_readiness_low": aggregate.role_readiness_low,
            "role_readiness_high": aggregate.role_readiness_high,
            "interview_readiness_low": aggregate.interview_readiness_low,
            "interview_readiness_high": aggregate.interview_readiness_high,
            "verdict_code": aggregate.verdict_code.value,
            "root_cause_code": aggregate.root_cause_code.value,
            "summary": language.verdict_summary,
            "confidence_note": language.confidence_note,
            "assessment_confidence": aggregate.overall_signal_confidence,
        }


class LoopReportRepository:
    def __init__(self, sessions: MemorySessionRepository, assessment: ResultAssessment) -> None:
        self.sessions = sessions
        self.assessment = assessment

    async def get_session(self, session_id, user_id):
        return await self.sessions.get(session_id, user_id)

    async def get_target_assessment_scope(self, session_id, user_id, session_role_profile_id):
        return None

    async def get_result(self, session_id, user_id):
        return self.assessment.saved.get((session_id, user_id))

    async def list_claims(self, session_id, user_id):
        return []

    async def list_evidence(self, claim_ids, user_id):
        return []

    async def list_specialists(self, session_id, user_id):
        return verified_specialists()

    async def list_events(self, session_id, user_id):
        return []

    async def list_turns(self, session_id, user_id):
        return []


class Verifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token == "loop-owner":
            return AuthenticatedUser(id=USER, email="owner@example.com")
        raise InvalidAccessToken


def _bind(overrides: dict) -> None:
    for dependency, provider in overrides.items():
        app.dependency_overrides[dependency] = provider


def _restore(previous: dict) -> None:
    for dependency in previous:
        app.dependency_overrides.pop(dependency, None)
    app.dependency_overrides.update(previous)


def test_quick_drill_text_loop_reaches_a_labelled_review() -> None:
    sessions = MemorySessionRepository()
    engine = InterviewStateMachine(sessions, total_time_budget_seconds=1200, phase_time_budget_seconds=180)
    plans = DrillPlans()
    turns = MemoryTurns()
    planner = GuardProvider()
    interviewer = RecordingProvider()
    planner_registry = AgentRegistry()
    planner_registry.register(create_planner_agent("planner-test"))
    interviewer_registry = AgentRegistry()
    interviewer_registry.register(create_interviewer_agent("interviewer-test"))
    planning = InterviewPlanningService(
        sessions,
        plans,
        AgentRunner(planner_registry, planner, PromptLoader()),
        model="planner-test",
        intro_reserve_seconds=60,
        transition_reserve_seconds=60,
        closing_reserve_seconds=60,
    )
    interview = TextInterviewService(
        engine,
        InterviewerContextBuilder(engine, plans, turns),
        turns,
        AgentRunner(interviewer_registry, interviewer, PromptLoader()),
    )
    clock = Clock()
    assessment = ResultAssessment(stale_after=timedelta(seconds=30), clock=clock)
    report = ReportService(LoopReportRepository(sessions, assessment))
    worker = AssessmentWorker(
        assessment,
        SuccessfulOrchestrator(),
        NoopAdjudicator(),
        FinalAssessmentAggregator(),
        FakeVerdict(),
        FakeAudit(),
        max_attempts=2,
        retry_base_seconds=1,
    )
    overrides = {
        get_token_verifier: lambda: Verifier(),
        get_repository: lambda: sessions,
        get_interview_state_machine: lambda: engine,
        get_interview_planning_service: lambda: planning,
        get_text_interview_service: lambda: interview,
        get_assessment_pipeline_repository: lambda: assessment,
        get_report_service: lambda: report,
    }
    previous = {key: app.dependency_overrides[key] for key in overrides if key in app.dependency_overrides}
    _bind(overrides)
    try:
        with TestClient(app) as client:
            _run_loop(client, planner, interviewer, assessment, worker, clock)
    finally:
        _restore(previous)


def _run_loop(client, planner, interviewer, assessment, worker, clock) -> None:
    created = client.post(
        "/api/v1/sessions",
        headers=AUTH,
        json={"target_role": "Data Analyst", "practice_mode": "QUICK_DRILL", "practice_focus": "impact"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    session_id = body["id"]
    assert body["status"] == "CREATED"
    assert body["practice_mode"] == "QUICK_DRILL"
    assert body["practice_focus"] == "impact"
    assert body["total_time_budget_seconds"] == 300

    prepared = client.post(f"/api/v1/sessions/{session_id}/prepare", headers=AUTH)
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["session"]["status"] == "READY"
    assert planner.requests == []

    plan = client.get(f"/api/v1/sessions/{session_id}/plan", headers=AUTH)
    assert plan.status_code == 200, plan.text
    objectives = plan.json()["plan"]["objectives"]
    assert len(objectives) == 3
    assert [item["max_probes"] for item in objectives] == [1, 1, 1]
    assert plan.json()["plan"]["planning_version"] == "practice-plan-v1"
    questions = [item["initial_question"] for item in objectives]

    started = client.post(f"/api/v1/sessions/{session_id}/start", headers=AUTH)
    assert started.status_code == 200, started.text
    opening = started.json()
    assert opening["turn_type"] == "PLANNED"
    assert questions[0] in opening["question_text"]
    assert interviewer.requests == []

    answers = []
    for index in range(6):
        response = client.post(
            f"/api/v1/sessions/{session_id}/turn-text",
            headers=AUTH,
            json={"text": f"I changed the pricing report and checked the result myself. Answer {index + 1}."},
        )
        assert response.status_code == 200, response.text
        answers.append(response.json())

    assert [item["turn_type"] for item in answers] == [
        "DEPTH_PROBE", "RECOVERY", "DEPTH_PROBE", "RECOVERY", "DEPTH_PROBE", "CLOSING",
    ]
    assert [item["question_text"] for item in answers if item["turn_type"] == "DEPTH_PROBE"] == [FOLLOW_UP, FOLLOW_UP, FOLLOW_UP]
    assert answers[1]["question_text"] == questions[1]
    assert answers[3]["question_text"] == questions[2]
    assert len(interviewer.requests) == 6
    probes = [json.loads(request.messages[1]["content"]) for request in interviewer.requests]
    assert [item["probe_count"] for item in probes] == [0, 1, 0, 1, 0, 1]
    assert {item["objective"]["max_probes"] for item in probes} == {1}
    assert planner.requests == []

    session = client.get(f"/api/v1/sessions/{session_id}", headers=AUTH)
    assert session.status_code == 200, session.text
    assert session.json()["status"] == "ASSESSING"

    waiting_report = client.get(f"/api/v1/sessions/{session_id}/report", headers=AUTH)
    waiting_review = client.get(f"/api/v1/sessions/{session_id}/review", headers=AUTH)
    assert waiting_report.status_code == 409, waiting_report.text
    assert waiting_review.status_code == 409, waiting_review.text

    ended = client.post(f"/api/v1/sessions/{session_id}/end", headers=AUTH)
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "COMPLETED"
    assert ended.json()["assessment"]["status"] == "PENDING"
    assert len(assessment._jobs) == 1

    queued = client.get(f"/api/v1/sessions/{session_id}/assessment", headers=AUTH)
    assert queued.status_code == 200, queued.text
    assert queued.json()["status"] == "PENDING"
    assert queued.json()["failure_code"] is None
    # jobs.created_at. Null until a worker claims (jobs.locked_at).
    queued_at = queued.json()["queued_at"]
    assert queued_at
    assert queued.json()["started_at"] is None
    assert queued.json()["completed_at"] is None
    still_waiting = client.get(f"/api/v1/sessions/{session_id}/report", headers=AUTH)
    assert still_waiting.status_code == 409, still_waiting.text
    assert client.get(f"/api/v1/sessions/{session_id}/review", headers=AUTH).status_code == 409

    # The worker is down: the same job stays queued, then becomes a retryable failure.
    repeated = client.post(f"/api/v1/sessions/{session_id}/assessment/retry", headers=AUTH)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["status"] == "PENDING"
    assert len(assessment._jobs) == 1
    clock.advance(30)
    stale = client.get(f"/api/v1/sessions/{session_id}/assessment", headers=AUTH)
    assert stale.status_code == 200, stale.text
    assert stale.json()["status"] == "FAILED"
    assert stale.json()["failure_code"] == STALE_FAILURE_CODE
    assert client.get(f"/api/v1/sessions/{session_id}/report", headers=AUTH).status_code == 409
    assert client.get(f"/api/v1/sessions/{session_id}/review", headers=AUTH).status_code == 409

    retried = client.post(f"/api/v1/sessions/{session_id}/assessment/retry", headers=AUTH)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "PENDING"
    assert retried.json()["failure_code"] is None
    assert retried.json()["queued_at"] == queued_at
    assert retried.json()["started_at"] is None
    assert len(assessment._jobs) == 1

    result = asyncio.run(worker.run_once("core-loop-test"))
    assert result.processed and result.success
    finished = client.get(f"/api/v1/sessions/{session_id}/assessment", headers=AUTH)
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == AssessmentPipelineStatus.COMPLETED.value
    assert finished.json()["queued_at"] == queued_at
    assert finished.json()["started_at"]
    assert finished.json()["completed_at"]

    report_response = client.get(f"/api/v1/sessions/{session_id}/report", headers=AUTH)
    assert report_response.status_code == 200, report_response.text
    report_body = report_response.json()
    assert report_body["session"]["target_role"] == "Data Analyst"
    assert report_body["verdict"]["code"]
    assert report_body["verdict"]["label"]
    assert "readiness_percentage" not in report_body

    review = client.get(f"/api/v1/sessions/{session_id}/review", headers=AUTH)
    assert review.status_code == 200, review.text
    review_body = review.json()
    assert review_body["session_id"] == session_id
    assert review_body["target_role"] == "Data Analyst"
    assert review_body["root_cause"] == report_body["root_cause"]
    assert review_body["root_cause"] != "UNAVAILABLE"
    assert len(review_body["dimensions"]) == 4
    assert {item["state"] for item in review_body["dimensions"]} <= LABELS
    assert len(review_body["improvements"]) <= 3
    assert review_body["next_step"]["title"]
    assert "score" not in review_body
    assert "readiness_percentage" not in review_body
    assert "%" not in json.dumps(review_body["dimensions"])
