from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from app.assessment_pipeline_models import AssessmentPipelineStatus
from app.assessment_pipeline_repository import MemoryAssessmentPipelineRepository
from app.assessment_worker import AssessmentWorker
from app.claim_resolution_models import ClaimsAudit
from app.final_assessment_aggregator import FinalAssessmentAggregator
from app.specialist_assessor_models import (
    AssessmentQuestionContext,
    AssessmentScope,
    AssessorType,
    DomainAssessment,
    SignalStrength,
    SpecialistAssessmentBundle,
    SpecialistAssessmentOutput,
    SpecialistStatus,
    StoredSpecialistAssessment,
)
from app.verdict_models import RootCauseCode, VerdictCode, VerdictLanguageOutput

USER_ID = uuid4()
SESSION_ID = uuid4()


def case_bundle() -> SpecialistAssessmentBundle:
    keys = ("structured_problem_solving", "quantitative_reasoning", "business_judgement")
    dimensions = tuple(
        {
            "competency_key": key,
            "title": title,
            "criteria": criteria,
            "insufficient_signal": "If no direct answer signal is available, mark NOT_ENOUGH_SIGNAL.",
        }
        for key, title, criteria in (
            (keys[0], "Structured problem solving", "Break down the case into relevant parts."),
            (keys[1], "Quantitative reasoning", "Explain assumptions, calculations, and interpretation."),
            (keys[2], "Business judgment", "Connect recommendations to priorities, risks, and trade-offs."),
        )
    )
    scope = AssessmentScope(
        target_id=uuid4(),
        role_profile_id=uuid4(),
        role_family_key="business_analysis",
        round_key="business_problem_solving",
        round_label="Working through a business case",
        question_family="case_discussion",
        taxonomy_version=1,
        catalog_version=1,
        rubric_key="business_case_v1",
        rubric_version="assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1",
        competency_keys=keys,
        assessor_types=(AssessorType.TECHNICAL,),
        provenance_class="MIRROR_GENERATED",
        dimensions=dimensions,
        questions=(AssessmentQuestionContext(
            position=1,
            template_id="case.cafe_profit",
            family_key="profit_diagnosis",
            competency_key=keys[0],
            question_family="case_discussion",
            text="How would you structure the case?",
        ),),
    )
    domain_rows = [
        DomainAssessment(
            domain=key,
            status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
            signal_strength=SignalStrength.NONE,
            confidence=0.2,
            reason_summary="There is not enough signal yet.",
        )
        for key in keys
    ]
    output = SpecialistAssessmentOutput(
        assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
        competency_or_domain_assessments=domain_rows,
        signal_strength=SignalStrength.NONE,
        confidence=0.2,
        reason_summary="There is not enough signal yet.",
    )
    technical = StoredSpecialistAssessment(
        id=uuid4(),
        session_id=SESSION_ID,
        assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
        result_json=output,
        model="scripted",
        model_version="scripted",
        prompt_version="v2",
        rubric_version=scope.rubric_version,
        created_at=datetime.now(UTC),
    )
    return SpecialistAssessmentBundle(session_id=SESSION_ID, assessment_scope=scope, technical=technical)


class ScopedOrchestrator:
    async def assess(self, session_id, user_id):
        assert session_id == SESSION_ID and user_id == USER_ID
        return case_bundle()


class RecordingAdjudicator:
    def __init__(self):
        self.seen = []

    async def adjudicate(self, session_id, user_id, bundle):
        self.seen.append(bundle.assessment_scope)
        return []

    def requires_adjudication(self, bundle):
        return False


class ForbiddenLegacyVerdict:
    async def write(self, *args, **kwargs):
        raise AssertionError("round-scoped practice must not generate global verdict language")


class ForbiddenClaimsAudit:
    async def audit(self, user_id):
        raise AssertionError("round-scoped practice must not use profile-wide claims audit")


class CapturingPipelineRepository(MemoryAssessmentPipelineRepository):
    def __init__(self):
        super().__init__()
        self.aggregate = None
        self.language = None

    async def persist_result(self, session_id, user_id, aggregate, language, *, model, prompt_version):
        self.aggregate = aggregate
        self.language = language
        await super().persist_result(session_id, user_id, aggregate, language, model=model, prompt_version=prompt_version)


def test_scoped_worker_fails_instead_of_persisting_when_required_adjudication_is_missing() -> None:
    class RequiredButMissingAdjudicator:
        def __init__(self):
            self.seen = []

        async def adjudicate(self, session_id, user_id, bundle):
            self.seen.append(bundle.assessment_scope)
            return []

        def requires_adjudication(self, bundle):
            return True

    repository = CapturingPipelineRepository()
    adjudicator = RequiredButMissingAdjudicator()
    asyncio.run(repository.enqueue(SESSION_ID, USER_ID))
    task = AssessmentWorker(
        repository,
        cast(Any, ScopedOrchestrator()),
        cast(Any, adjudicator),
        FinalAssessmentAggregator(),
        cast(Any, ForbiddenLegacyVerdict()),
        cast(Any, ForbiddenClaimsAudit()),
        max_attempts=1,
        retry_base_seconds=1,
    )

    result = asyncio.run(task.run_once("scope-adjudication-failure-test"))

    state = asyncio.run(repository.status(SESSION_ID, USER_ID))
    assert not result.success and not result.retry_scheduled
    assert state and state.status == AssessmentPipelineStatus.FAILED
    assert repository.aggregate is None and repository.language is None
    assert adjudicator.seen and adjudicator.seen[0] is not None


def test_scoped_worker_keeps_adjudication_but_skips_global_verdict_and_claims_audit() -> None:
    repository = CapturingPipelineRepository()
    adjudicator = RecordingAdjudicator()
    asyncio.run(repository.enqueue(SESSION_ID, USER_ID))
    task = AssessmentWorker(
        repository,
        cast(Any, ScopedOrchestrator()),
        cast(Any, adjudicator),
        FinalAssessmentAggregator(),
        cast(Any, ForbiddenLegacyVerdict()),
        cast(Any, ForbiddenClaimsAudit()),
        max_attempts=1,
        retry_base_seconds=1,
    )

    result = asyncio.run(task.run_once("scope-test"))

    state = asyncio.run(repository.status(SESSION_ID, USER_ID))
    assert result.success and state and state.status == AssessmentPipelineStatus.COMPLETED
    assert repository.aggregate is not None
    assert repository.aggregate.verdict_code == VerdictCode.PRACTICE_ONLY
    assert repository.aggregate.root_cause_code == RootCauseCode.NOT_APPLICABLE
    assert repository.aggregate.role_readiness_low is None and repository.aggregate.interview_readiness_low is None
    assert repository.aggregate.rubric_version == "assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1"
    assert repository.language is not None
    assert "practice round only" in repository.language.verdict_summary.casefold()
    assert adjudicator.seen and adjudicator.seen[0] is not None
