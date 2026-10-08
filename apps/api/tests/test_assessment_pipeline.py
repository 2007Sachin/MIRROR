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
    AssessmentEvidence, AssessmentQuestionContext, AssessmentScope, AssessorType, DomainAssessment, SignalStrength,
    SpecialistAssessmentBundle, SpecialistAssessmentOutput, SpecialistStatus, StoredSpecialistAssessment,
)
from app.verdict_models import RootCauseCode, VerdictCode, VerdictLanguageOutput


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


class TransientClaimRepository(MemoryAssessmentPipelineRepository):
    def __init__(self) -> None:
        super().__init__()
        self.claim_attempts = 0

    async def claim(self, worker_id: str, max_attempts: int):
        self.claim_attempts += 1
        if self.claim_attempts == 1:
            raise RuntimeError("temporary_database_disconnect")
        raise asyncio.CancelledError


def worker(repository, orchestrator, *, max_attempts=2):
    return AssessmentWorker(repository, orchestrator, NoopAdjudicator(), FinalAssessmentAggregator(), FakeVerdict(), FakeAudit(), max_attempts=max_attempts, retry_base_seconds=1)


def test_round_scoped_aggregation_suppresses_global_readiness_and_root_cause() -> None:
    scope = AssessmentScope(
        target_id=uuid4(), role_profile_id=uuid4(), role_family_key="business_analysis",
        round_key="business_problem_solving", round_label="Working through a business case", question_family="case_discussion",
        taxonomy_version=1, catalog_version=1, rubric_key="business_case_v1",
        rubric_version="assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1",
        competency_keys=("structured_problem_solving", "quantitative_reasoning", "business_judgement"),
        assessor_types=(AssessorType.TECHNICAL,), provenance_class="MIRROR_GENERATED",
        dimensions=tuple(
            {"competency_key": key, "title": title, "criteria": criteria, "insufficient_signal": insufficient}
            for key, title, criteria, insufficient in (
                ("structured_problem_solving", "Structured problem solving", "Break down the case.", "No framing means NOT_ENOUGH_SIGNAL."),
                ("quantitative_reasoning", "Quantitative reasoning", "Explain assumptions and calculations.", "No number reasoning means NOT_ENOUGH_SIGNAL."),
                ("business_judgement", "Business judgment", "Explain decisions and trade-offs.", "No decision signal means NOT_ENOUGH_SIGNAL."),
            )
        ),
        questions=(AssessmentQuestionContext(position=1, template_id="case.cafe_profit", family_key="profit_diagnosis", competency_key="structured_problem_solving", question_family="case_discussion", text="How would you structure the case?"),),
    )
    turn_id = uuid4()
    quote = "I would split the profit decline into price, volume, and cost."
    scoped_domains = [
        DomainAssessment(
            domain=key,
            status=(SpecialistStatus.NOT_ENOUGH_SIGNAL if key == "business_judgement" else SpecialistStatus.COMPLETE),
            signal_strength=(SignalStrength.NONE if key == "business_judgement" else SignalStrength.STRONG),
            confidence=(0.2 if key == "business_judgement" else 0.8),
            evidence_turn_ids=[] if key == "business_judgement" else [turn_id],
            evidence_quotes=[] if key == "business_judgement" else [AssessmentEvidence(turn_id=turn_id, quote=quote)],
            reason_summary=("There is not enough signal yet." if key == "business_judgement" else "You showed a reasoned approach here."),
        )
        for key in scope.competency_keys
    ]
    scoped_output = SpecialistAssessmentOutput(
        assessor_type=AssessorType.TECHNICAL, status=SpecialistStatus.COMPLETE,
        competency_or_domain_assessments=scoped_domains, signal_strength=SignalStrength.STRONG,
        confidence=0.8, evidence_turn_ids=[turn_id], evidence_quotes=[AssessmentEvidence(turn_id=turn_id, quote=quote)],
        reason_summary="You showed a reasoned approach here.",
    )
    scoped_row = StoredSpecialistAssessment(
        id=uuid4(), session_id=SESSION_ID, assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.COMPLETE, result_json=scoped_output, model="mock", model_version="mock",
        prompt_version="v2", rubric_version=scope.rubric_version, created_at=datetime.now(UTC),
    )
    bundle = SpecialistAssessmentBundle(
        session_id=SESSION_ID,
        assessment_scope=scope,
        technical=scoped_row,
    )

    aggregate = FinalAssessmentAggregator().aggregate(bundle)

    assert aggregate.role_readiness_internal is None
    assert aggregate.interview_readiness_internal is None
    assert aggregate.role_readiness_low is None and aggregate.role_readiness_high is None
    assert aggregate.interview_readiness_low is None and aggregate.interview_readiness_high is None
    assert aggregate.verdict_code == VerdictCode.PRACTICE_ONLY
    assert aggregate.root_cause_code == RootCauseCode.NOT_APPLICABLE
    assert aggregate.rubric_version == "assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1"
    assert aggregate.overall_signal_confidence == 0.8


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


def test_failed_assessment_can_be_requeued_without_duplicate_job() -> None:
    repository = MemoryAssessmentPipelineRepository()
    asyncio.run(repository.enqueue(SESSION_ID, USER_ID))
    asyncio.run(worker(repository, FailingOrchestrator(), max_attempts=1).run_once("test"))

    retried = asyncio.run(repository.retry(SESSION_ID, USER_ID))
    repeated = asyncio.run(repository.retry(SESSION_ID, USER_ID))

    assert retried.status == AssessmentPipelineStatus.PENDING
    assert repeated.status == AssessmentPipelineStatus.PENDING
    assert len(repository._jobs) == 1


def test_forever_worker_survives_transient_claim_failure() -> None:
    repository = TransientClaimRepository()

    async def exercise() -> None:
        try:
            await worker(repository, SuccessfulOrchestrator()).run_forever(
                "test", poll_seconds=0.001
            )
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())
    assert repository.claim_attempts == 2
