from __future__ import annotations

import asyncio
from uuid import uuid4

from app.assessment_pipeline_repository import SupabaseAssessmentPipelineRepository
from app.verdict_models import AggregatedAssessment, RootCauseCode, VerdictCode, VerdictLanguageOutput


class CaptureRepository(SupabaseAssessmentPipelineRepository):
    def __init__(self) -> None:
        self.payload = None

    async def _get(self, resource, params):
        return [{"id": str(uuid4())}]

    async def _post(self, resource, payload, *, prefer=None, ignore_conflict=False):
        self.payload = payload
        return []


def test_session_result_persists_the_selected_round_rubric_version() -> None:
    repository = CaptureRepository()
    aggregate = AggregatedAssessment(
        role_readiness_internal=None,
        interview_readiness_internal=None,
        role_readiness_low=None,
        role_readiness_high=None,
        interview_readiness_low=None,
        interview_readiness_high=None,
        overall_signal_confidence=0.0,
        availability_status="ROUND_SCOPED",
        verdict_code=VerdictCode.PRACTICE_ONLY,
        root_cause_code=RootCauseCode.NOT_APPLICABLE,
        rubric_version="assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1",
    )
    language = VerdictLanguageOutput(
        verdict_summary="This is practice-round feedback only.",
        root_cause_explanation="This practice does not produce an overall readiness result.",
        confidence_note="Only this round's answers are reflected here.",
    )

    asyncio.run(repository.persist_result(uuid4(), uuid4(), aggregate, language, model="mock", prompt_version="v2"))

    assert repository.payload is not None
    assert repository.payload["rubric_version"] == "assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1"
