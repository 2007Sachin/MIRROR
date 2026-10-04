from __future__ import annotations

import logging
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


logger = logging.getLogger("mirror.assessment")


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

    def requires_adjudication(self, bundle: SpecialistAssessmentBundle) -> bool:
        return bool(self._detector.detect(bundle))

    async def adjudicate(self, session_id: UUID, user_id: UUID,
                         bundle: SpecialistAssessmentBundle) -> list[StoredAdjudication]:
        # B7: specialist rows are historical truth owned by the specialists. The
        # repository and runner only ever see private deep copies, the runner's copy
        # is separate from the context that gets stored, and every allow-list used to
        # judge the decision is snapshotted before the model runs.
        original = bundle.model_dump(mode="json")
        disagreements = self._detector.detect(bundle)
        if not disagreements:
            return []
        records: list[StoredAdjudication] = []
        for disagreement in disagreements:
            context = await self._repository.load_context(session_id, user_id, disagreement.model_copy(deep=True), bundle.model_copy(deep=True))
            if context is None:
                continue
            if context.specialist_bundle.model_dump(mode="json") != original or context.disagreement != disagreement:
                logger.warning("adjudication context does not match persisted specialist state; skipped",
                               extra={"session_id": str(session_id), "dimension": disagreement.affected_dimension})
                continue
            valid_ids = {str(item.get("id")) for item in context.validated_evidence}
            try:
                result = await self._runner.run(ADJUDICATOR_AGENT_NAME, context.model_copy(deep=True),
                    context=AgentExecutionContext(session_id=session_id, user_id=user_id))
                if not result.success or result.output is None:
                    continue
                decision = AdjudicationDecision.model_validate(result.output)
                if decision.affected_dimension != disagreement.affected_dimension:
                    continue
                # The decision may interpret the disagreement but may not restate the
                # specialists' positions: those come from the deterministic detector.
                if decision.specialist_positions != disagreement.specialist_positions:
                    logger.warning("adjudication rewrote specialist positions; decision dropped",
                                   extra={"session_id": str(session_id), "dimension": disagreement.affected_dimension})
                    continue
                if not {str(item) for item in decision.evidence_ids} <= valid_ids:
                    continue
                records.append(await self._repository.store(context, decision, result.model, result.prompt_version))
            except Exception:
                # Specialist records are immutable and remain usable if a narrow
                # adjudication call fails or returns invalid evidence.
                continue
        if bundle.model_dump(mode="json") != original:  # regression tripwire: copies make this unreachable
            raise RuntimeError("specialist assessments were mutated during adjudication")
        return records

