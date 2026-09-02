from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .agents import AgentRunner
from .agents.definitions import AgentExecutionContext
from .agents.adjudicator import ADJUDICATOR_AGENT_NAME
from .assessment_adjudication_models import (
    AdjudicationContext, AdjudicationDecision, AssessmentDisagreement,
    StoredAdjudication,
)
from .assessment_disagreement import AssessmentDisagreementDetector
from .specialist_assessor_models import SpecialistAssessmentBundle


class AssessmentAdjudicationRepository(Protocol):
    async def load_context(self, session_id: UUID, user_id: UUID,
                           disagreement: AssessmentDisagreement,
                           bundle: SpecialistAssessmentBundle) -> AdjudicationContext | None: ...
    async def store(self, context: AdjudicationContext, decision: AdjudicationDecision,
                    model: str, prompt_version: str) -> StoredAdjudication: ...


class AssessmentAdjudicator:
    def __init__(self, detector: AssessmentDisagreementDetector,
                 repository: AssessmentAdjudicationRepository, runner: AgentRunner) -> None:
        self._detector = detector
        self._repository = repository
        self._runner = runner

    async def adjudicate(self, session_id: UUID, user_id: UUID,
                         bundle: SpecialistAssessmentBundle) -> list[StoredAdjudication]:
        disagreements = self._detector.detect(bundle)
        if not disagreements:
            return []
        records: list[StoredAdjudication] = []
        for disagreement in disagreements:
            context = await self._repository.load_context(session_id, user_id, disagreement, bundle)
            if context is None:
                continue
            try:
                result = await self._runner.run(ADJUDICATOR_AGENT_NAME, context,
                    context=AgentExecutionContext(session_id=session_id, user_id=user_id))
                if not result.success or result.output is None:
                    continue
                decision = AdjudicationDecision.model_validate(result.output)
                if decision.affected_dimension != disagreement.affected_dimension:
                    continue
                valid_ids = {str(item.get("id")) for item in context.validated_evidence}
                if not {str(item) for item in decision.evidence_ids} <= valid_ids:
                    continue
                records.append(await self._repository.store(context, decision, result.model, result.prompt_version))
            except Exception:
                # Specialist records are immutable and remain usable if a narrow
                # adjudication call fails or returns invalid evidence.
                continue
        return records

