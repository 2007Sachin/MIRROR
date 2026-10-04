from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from .agents import AgentRunner
from .agents.definitions import AgentExecutionContext
from .evidence_service import EvidenceQuoteValidator
from .evidence_validator import EvidenceValidator, EvidenceValidationError
from .specialist_assessment_repository import SpecialistAssessmentRepository
from .specialist_assessor_models import (
    AssessorType, SpecialistAssessmentBundle, SpecialistAssessmentOutput,
    SpecialistStatus, StoredSpecialistAssessment,
)


class SpecialistAssessmentRejected(Exception):
    pass


logger = logging.getLogger("mirror.assessment")


class AssessmentOrchestrator:
    """Runs isolated assessors; it stores results but never adjudicates them."""

    def __init__(
        self, repository: SpecialistAssessmentRepository,
        runners: dict[AssessorType, AgentRunner],
        quote_validator: EvidenceQuoteValidator,
        evidence_validator: EvidenceValidator | None = None,
    ) -> None:
        self._repository = repository
        self._runners = runners
        self._quotes = quote_validator
        self._evidence_validator = evidence_validator or EvidenceValidator()

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
        # Retried jobs reuse immutable specialist results instead of invoking again.
        get_latest = getattr(self._repository, "get_latest", None)
        if get_latest is not None:
            existing = await get_latest(session_id, user_id, assessor_type)
            if existing is not None:
                # B5: Revalidate cached specialist against current context
                # Unverifiable cached rows (invalid evidence, or no context to verify
                # against) are never reused; fall through to fresh generation, whose
                # newer row supersedes the stale one. Nothing is deleted.
                context = await self._repository.load_context(session_id, user_id, assessor_type)
                try:
                    if context is None:
                        raise SpecialistAssessmentRejected("no context to revalidate cached assessment")
                    await self._validate_evidence_b5(existing.result_json, context)
                    return existing
                except SpecialistAssessmentRejected:
                    logger.warning(
                        "B5 cached specialist unverifiable; regenerating",
                        extra={
                            "session_id": str(session_id),
                            "user_id": str(user_id),
                            "assessor_type": assessor_type.value,
                            "cached_id": str(existing.id),
                        },
                    )
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
            logger.error(
                "specialist assessment execution failed",
                extra={
                    "execution_id": str(execution.execution_id),
                    "session_id": str(session_id),
                    "user_id": str(user_id),
                    "assessor_type": assessor_type.value,
                    "error_type": (
                        execution.error_type.value if execution.error_type else "unknown"
                    ),
                },
            )
            raise SpecialistAssessmentRejected(f"{assessor_type.value} assessor failed")
        output = SpecialistAssessmentOutput.model_validate(execution.output)
        if output.assessor_type != assessor_type:
            raise SpecialistAssessmentRejected("assessor output type mismatch")
        # B5: Validate evidence before storage
        await self._validate_evidence_b5(output, context)
        await self._validate_quotes(output, context, user_id)
        return await self._repository.store(
            session_id, assessor_type, output.status, output,
            execution.model, execution.model, execution.prompt_version,
            context.rubric_version,
        )

    async def _validate_evidence_b5(self, output, context) -> None:
        """B5: Validate that all evidence resolves to actual candidate content."""
        candidate_turns = EvidenceValidator.extract_candidate_turns(
            context.transcript_turns,
            turn_horizon=100,
        )
        
        # Collect nested assessments
        nested_assessments = []
        for assessment in output.dimensions + output.competency_or_domain_assessments:
            nested_assessments.append({
                "evidence_turn_ids": assessment.evidence_turn_ids,
                "evidence_quotes": [
                    {"turn_id": q.turn_id, "quote": q.quote}
                    for q in assessment.evidence_quotes
                ],
            })
        
        # Validate all evidence
        try:
            self._evidence_validator.validate_assessment_output(
                evidence_turn_ids=output.evidence_turn_ids,
                evidence_quotes=[
                    {"turn_id": q.turn_id, "quote": q.quote}
                    for q in output.evidence_quotes
                ],
                candidate_turns=candidate_turns,
                nested_assessments=nested_assessments,
            )
        except EvidenceValidationError as e:
            logger.error(
                "B5 evidence validation failed",
                extra={
                    "session_id": str(context.session_id),
                    "assessor_type": output.assessor_type.value,
                    "error": str(e),
                },
            )
            raise SpecialistAssessmentRejected(f"Evidence validation failed: {e}")

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

