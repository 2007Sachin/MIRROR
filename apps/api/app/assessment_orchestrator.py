from __future__ import annotations

import asyncio
from uuid import UUID

from .agents import AgentRunner
from .agents.definitions import AgentExecutionContext
from .evidence_service import EvidenceQuoteValidator
from .specialist_assessment_repository import SpecialistAssessmentRepository
from .specialist_assessor_models import (
    AssessorType, SpecialistAssessmentBundle, SpecialistAssessmentOutput,
    SpecialistStatus, StoredSpecialistAssessment,
)


class SpecialistAssessmentRejected(Exception):
    pass


class AssessmentOrchestrator:
    """Runs isolated assessors; it stores results but never adjudicates them."""

    def __init__(
        self, repository: SpecialistAssessmentRepository,
        runners: dict[AssessorType, AgentRunner],
        quote_validator: EvidenceQuoteValidator,
    ) -> None:
        self._repository = repository
        self._runners = runners
        self._quotes = quote_validator

    async def assess(self, session_id: UUID, user_id: UUID) -> SpecialistAssessmentBundle:
        results = await asyncio.gather(*[
            self._run_one(session_id, user_id, kind)
            for kind in AssessorType
        ])
        by_type = {item.assessor_type: item for item in results if item is not None}
        return SpecialistAssessmentBundle(
            session_id=session_id,
            technical=by_type.get(AssessorType.TECHNICAL),
            behaviour=by_type.get(AssessorType.BEHAVIOUR),
            claims=by_type.get(AssessorType.CLAIMS),
            disagreements=self._disagreements(by_type),
        )

    async def _run_one(
        self, session_id: UUID, user_id: UUID, assessor_type: AssessorType
    ) -> StoredSpecialistAssessment | None:
        context = await self._repository.load_context(session_id, user_id, assessor_type)
        if context is None:
            return None
        runner = self._runners[assessor_type]
        agent_name = f"assessor_{assessor_type.value.lower()}"
        execution = await runner.run(
            agent_name, context,
            context=AgentExecutionContext(session_id=session_id, user_id=user_id),
        )
        if not execution.success or execution.output is None:
            raise SpecialistAssessmentRejected(f"{assessor_type.value} assessor failed")
        output = SpecialistAssessmentOutput.model_validate(execution.output)
        if output.assessor_type != assessor_type:
            raise SpecialistAssessmentRejected("assessor output type mismatch")
        await self._validate_quotes(output, context, user_id)
        return await self._repository.store(
            session_id, assessor_type, output.status, output,
            execution.model, execution.model, execution.prompt_version,
            context.rubric_version,
        )

    async def _validate_quotes(self, output, context, user_id: UUID) -> None:
        allowed = {turn.id: turn.text for turn in context.transcript_turns}
        citations = list(output.evidence_quotes)
        for assessment in output.dimensions + output.competency_or_domain_assessments:
            citations.extend(assessment.evidence_quotes)
        for citation in citations:
            text = allowed.get(citation.turn_id)
            if text is None or not self._quote_in_text(citation.quote, text):
                raise SpecialistAssessmentRejected("assessor proposed an untraceable quote")

    @staticmethod
    def _quote_in_text(quote: str, source: str) -> bool:
        return quote in source or EvidenceQuoteValidator._normalize(quote) in EvidenceQuoteValidator._normalize(source)

    @staticmethod
    def _disagreements(results: dict[AssessorType, StoredSpecialistAssessment]) -> list[str]:
        # Deliberately descriptive only; adjudication belongs to a later Verdict Agent.
        complete = [kind.value for kind, result in results.items() if result.status == SpecialistStatus.COMPLETE]
        insufficient = [kind.value for kind, result in results.items() if result.status == SpecialistStatus.NOT_ENOUGH_SIGNAL]
        if complete and insufficient:
            return [f"Signal availability differs: complete={','.join(complete)}; insufficient={','.join(insufficient)}"]
        return []

