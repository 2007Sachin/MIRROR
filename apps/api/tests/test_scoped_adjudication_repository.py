from __future__ import annotations

import asyncio
from uuid import uuid4

from app.assessment_adjudication_models import AssessmentDisagreement
from app.assessment_adjudication_repository import SupabaseAssessmentAdjudicationRepository
from app.specialist_assessor_models import (
    AssessmentQuestionContext,
    AssessmentScope,
    AssessorType,
    SpecialistAssessmentBundle,
)

SESSION, USER, CLAIM, EVIDENCE = (uuid4() for _ in range(4))


def disagreement() -> AssessmentDisagreement:
    return AssessmentDisagreement(
        affected_dimension="structured_problem_solving",
        specialist_positions={"TECHNICAL": "position one", "BEHAVIOUR": "position two"},
        reason="The specialist positions materially differ.",
    )


def scoped_bundle() -> SpecialistAssessmentBundle:
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
        competency_keys=("structured_problem_solving",),
        assessor_types=(AssessorType.TECHNICAL, AssessorType.BEHAVIOUR),
        provenance_class="MIRROR_GENERATED",
        dimensions=({
            "competency_key": "structured_problem_solving",
            "title": "Structured problem solving",
            "criteria": "Frames and breaks down the business question.",
            "insufficient_signal": "When framing is absent, use NOT_ENOUGH_SIGNAL.",
        },),
        questions=(AssessmentQuestionContext(
            position=1,
            template_id="case.cafe_profit",
            family_key="profit_diagnosis",
            competency_key="structured_problem_solving",
            question_family="case_discussion",
            text="How would you structure the case?",
        ),),
    )
    return SpecialistAssessmentBundle(session_id=SESSION, assessment_scope=scope)


class RecordingRepository(SupabaseAssessmentAdjudicationRepository):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def _get(self, resource, params):
        self.calls.append((resource, params))
        if resource == "sessions":
            return [{"id": str(SESSION)}]
        if resource == "claims":
            return [{
                "id": str(CLAIM),
                "claim_text": "I structured the case analysis.",
                "status": "CORROBORATED",
                "confidence": 0.8,
            }]
        if resource == "claim_evidence":
            return [{
                "id": str(EVIDENCE),
                "claim_id": str(CLAIM),
                "turn_id": str(uuid4()),
                "quote_text": "I structured the case analysis.",
                "evidence_direction": "SUPPORTS",
                "strength": "STRONG",
            }]
        return []


async def load_context(repository, bundle):
    return await repository.load_context(SESSION, USER, disagreement(), bundle)


def test_scoped_adjudication_limits_claims_and_evidence_to_session_claims() -> None:
    repository = RecordingRepository()

    context = asyncio.run(load_context(repository, scoped_bundle()))

    claims_query = next(params for table, params in repository.calls if table == "claims")
    evidence_query = next(params for table, params in repository.calls if table == "claim_evidence")
    assert claims_query.get("session_id") == f"eq.{SESSION}"
    assert "or" not in claims_query
    assert evidence_query.get("claim_id") == f"in.({CLAIM})"
    assert context is not None
    assert [row["id"] for row in context.claims_state] == [str(CLAIM)]
    assert [row["id"] for row in context.validated_evidence] == [str(EVIDENCE)]


def test_legacy_adjudication_keeps_existing_claim_context_scope() -> None:
    repository = RecordingRepository()
    bundle = SpecialistAssessmentBundle(session_id=SESSION)

    context = asyncio.run(load_context(repository, bundle))

    claims_query = next(params for table, params in repository.calls if table == "claims")
    evidence_query = next(params for table, params in repository.calls if table == "claim_evidence")
    assert claims_query.get("or") == f"(session_id.eq.{SESSION},session_id.is.null)"
    assert "claim_id" not in evidence_query
    assert context is not None
