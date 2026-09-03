from __future__ import annotations

from uuid import UUID

from .assessment_adjudication_models import AdjudicationContext, AdjudicationDecision, AssessmentDisagreement, StoredAdjudication
from .config import Settings
from .skeptic_repository import SkepticPersistenceUnavailable, SupabaseSkepticRepository
from .specialist_assessor_models import SpecialistAssessmentBundle


class SupabaseAssessmentAdjudicationRepository(SupabaseSkepticRepository):
    def __init__(self, settings: Settings) -> None:
        try:
            super().__init__(settings)
        except SkepticPersistenceUnavailable as exc:
            raise RuntimeError("adjudication persistence is not configured") from exc

    async def load_context(self, session_id: UUID, user_id: UUID, disagreement: AssessmentDisagreement, bundle: SpecialistAssessmentBundle) -> AdjudicationContext | None:
        owned = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not owned:
            return None
        evidence = await self._get("claim_evidence", {"user_id": f"eq.{user_id}", "validated": "eq.true", "select": "id,claim_id,turn_id,quote_text,evidence_direction,strength", "limit": "200"})
        claims = await self._get("claims", {"user_id": f"eq.{user_id}", "or": f"(session_id.eq.{session_id},session_id.is.null)", "select": "id,claim_text,status,confidence", "limit": "100"})
        return AdjudicationContext(session_id=session_id, disagreement=disagreement, specialist_bundle=bundle, validated_evidence=evidence, claims_state=claims)

    async def store(self, context: AdjudicationContext, decision: AdjudicationDecision, model: str, prompt_version: str) -> StoredAdjudication:
        rows = await self._post("assessment_adjudications", {"session_id": str(context.session_id), "affected_dimension": decision.affected_dimension, "specialist_inputs": context.specialist_bundle.model_dump(mode="json"), "final_decision": decision.model_dump(mode="json"), "confidence": decision.confidence, "model": model, "prompt_version": prompt_version}, prefer="return=representation")
        return StoredAdjudication.model_validate(rows[0])
