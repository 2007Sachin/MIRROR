from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.assessment_pipeline_models import AssessmentPipelineStatus
from app.assessment_pipeline_repository import MemoryAssessmentPipelineRepository
from app.assessment_worker import AssessmentWorker
from app.claim_resolution_models import ClaimsAudit
from app.final_assessment_aggregator import FinalAssessmentAggregator
from app.specialist_assessor_models import (
    AssessorType, SignalStrength, SpecialistAssessmentBundle,
    SpecialistAssessmentOutput, SpecialistStatus, StoredSpecialistAssessment,
)
from app.verdict_models import VerdictLanguageOutput


USER_ID = UUID("c0000000-0000-4000-8000-000000000001")
SESSION_ID = UUID("d0000000-0000-4000-8000-000000000001")


def row(kind: AssessorType, strength: SignalStrength) -> StoredSpecialistAssessment:
    turn_id = uuid4()
    output = SpecialistAssessmentOutput(
        assessor_type=kind, status=SpecialistStatus.COMPLETE,
        signal_strength=strength, confidence=.8, evidence_turn_ids=[turn_id],
        reason_summary="Bounded evidence supports this assessment.",
    )
    return StoredSpecialistAssessment(
        id=uuid4(), session_id=SESSION_ID, assessor_type=kind,
        status=SpecialistStatus.COMPLETE, result_json=output, model="mock",
        model_version="mock", prompt_version="v1", rubric_version="v1",
        created_at=datetime.now(UTC),
    )


class SuccessfulOrchestrator:
    async def assess(self, session_id, user_id):
        return SpecialistAssessmentBundle(
            session_id=session_id,
            technical=row(AssessorType.TECHNICAL, SignalStrength.STRONG),
            behaviour=row(AssessorType.BEHAVIOUR, SignalStrength.MODERATE),
            claims=row(AssessorType.CLAIMS, SignalStrength.MODERATE),
        )


class FailingOrchestrator:
    async def assess(self, session_id, user_id):
        raise RuntimeError("malformed_specialist_output")


class NoopAdjudicator:
    async def adjudicate(self, session_id, user_id, bundle): return []
    def requires_adjudication(self, bundle): return False


class FakeVerdict:
    async def write(self, value, *, session_id, user_id):
        return VerdictLanguageOutput(
            verdict_summary="The available interview evidence is recorded in this report.",
            root_cause_explanation="Practice the least-supported dimension with specific examples.",
            confidence_note="This result reflects the evidence captured in this interview.",
        )


class FakeAudit:
    async def audit(self, user_id): return ClaimsAudit()


class FailingPersistenceRepository(MemoryAssessmentPipelineRepository):
    async def persist_result(self, *args, **kwargs):
        raise RuntimeError("database_write_failed")


def worker(repository, orchestrator, *, max_attempts=2):
    return AssessmentWorker(repository, orchestrator, NoopAdjudicator(), FinalAssessmentAggregator(), FakeVerdict(), FakeAudit(), max_attempts=max_attempts, retry_base_seconds=1)


def test_worker_persists_completed_result_once() -> None:
    repository = MemoryAssessmentPipelineRepository()
    asyncio.run(repository.enqueue(SESSION_ID, USER_ID))
    result = asyncio.run(worker(repository, SuccessfulOrchestrator()).run_once("test"))
    state = asyncio.run(repository.status(SESSION_ID, USER_ID))
    assert result.success and result.processed
    assert state and state.status == AssessmentPipelineStatus.COMPLETED
    assert asyncio.run(repository.has_result(SESSION_ID, USER_ID))


def test_worker_failure_is_retried_then_terminal() -> None:
    repository = MemoryAssessmentPipelineRepository()
    asyncio.run(repository.enqueue(SESSION_ID, USER_ID))
    first = asyncio.run(worker(repository, FailingOrchestrator(), max_attempts=1).run_once("test"))
    state = asyncio.run(repository.status(SESSION_ID, USER_ID))
    assert first.processed and not first.success and not first.retry_scheduled
    assert state and state.status == AssessmentPipelineStatus.FAILED


def test_worker_schedules_bounded_retry_for_persistence_failure() -> None:
    repository = FailingPersistenceRepository()
    asyncio.run(repository.enqueue(SESSION_ID, USER_ID))
    result = asyncio.run(worker(repository, SuccessfulOrchestrator(), max_attempts=2).run_once("test"))
    state = asyncio.run(repository.status(SESSION_ID, USER_ID))
    assert result.processed and not result.success and result.retry_scheduled
    assert state and state.status == AssessmentPipelineStatus.PENDING
    assert state.retry_count == 1


def test_existing_result_is_acknowledged_without_reexecution() -> None:
    repository = MemoryAssessmentPipelineRepository()
    asyncio.run(repository.enqueue(SESSION_ID, USER_ID))
    asyncio.run(repository.persist_result(SESSION_ID, USER_ID, FinalAssessmentAggregator().aggregate(SpecialistAssessmentBundle(session_id=SESSION_ID)), VerdictLanguageOutput(verdict_summary="The available interview evidence is recorded in this report.", root_cause_explanation="Practice the least-supported dimension with specific examples.", confidence_note="This result reflects the evidence captured in this interview."), model="mock", prompt_version="v1"))
    result = asyncio.run(worker(repository, FailingOrchestrator()).run_once("test"))
    assert result.success
    assert asyncio.run(repository.status(SESSION_ID, USER_ID)).status == AssessmentPipelineStatus.COMPLETED
