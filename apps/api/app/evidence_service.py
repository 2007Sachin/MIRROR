from __future__ import annotations

import logging
import re
import unicodedata
from uuid import UUID

from .agents import AgentRunner
from .agents.definitions import AgentExecutionContext
from .agents.evidence import EVIDENCE_AGENT_NAME
from .claims_models import ClaimStatus, VerificationPriority
from .claim_resolution_models import ClaimResolutionProposal, ResolutionTriggerType
from .claim_resolution_service import ClaimResolutionService
from .evidence_models import (
    EvidenceAssessment, EvidenceDirection, EvidenceItem, EvidenceReasonCode,
    EvidenceResolutionResult, EvidenceSourceType, EvidenceStrength,
)
from .evidence_repository import EvidenceRepository


logger = logging.getLogger("mirror.evidence")


class EvidenceClaimNotFound(Exception): pass


class EvidenceQuoteValidator:
    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository

    async def validate(self, item: EvidenceItem, user_id: UUID) -> bool:
        source = await self._repository.load_source_text(item.source_type, item.source_id, user_id)
        if source is None:
            return False
        if item.quote in source:
            return True
        return self._normalize(item.quote) in self._normalize(source)

    @staticmethod
    def _normalize(value: str) -> str:
        value = unicodedata.normalize("NFKC", value)
        value = value.translate(str.maketrans({"“": '"', "”": '"', "’": "'", "–": "-", "—": "-"}))
        return re.sub(r"\s+", " ", value).strip()


class EvidenceResolutionService:
    def __init__(self, repository: EvidenceRepository, resolutions: ClaimResolutionService, runner: AgentRunner) -> None:
        self._repository = repository
        self._resolutions = resolutions
        self._runner = runner
        self._validator = EvidenceQuoteValidator(repository)

    @staticmethod
    def should_resolve(*, meaningful_flag: bool = False, relevant_probe: bool = False,
                       session_ended: bool = False,
                       verification_priority: VerificationPriority = VerificationPriority.LOW) -> bool:
        return meaningful_flag or relevant_probe or (session_ended and verification_priority == VerificationPriority.HIGH)

    async def resolve(self, claim_id: UUID, user_id: UUID) -> EvidenceResolutionResult:
        context = await self._repository.load_context(claim_id, user_id)
        if context is None:
            raise EvidenceClaimNotFound
        execution = await self._runner.run(
            EVIDENCE_AGENT_NAME, context,
            context=AgentExecutionContext(session_id=context.claim.session_id, user_id=user_id),
        )
        if not execution.success or execution.output is None:
            raise ValueError("Evidence inference failed")
        assessment = EvidenceAssessment.model_validate(execution.output)
        if assessment.claim_id != claim_id:
            raise ValueError("Evidence assessment claim does not match")
        proposed = assessment.supporting_evidence + assessment.weakening_evidence + assessment.context_evidence
        validated: list[EvidenceItem] = []
        failures = 0
        for item in proposed:
            if await self._validator.validate(item, user_id):
                if await self._repository.save_validated(
                    claim_id, user_id, item, execution.execution_id,
                    execution.model, execution.prompt_version,
                ):
                    validated.append(item)
            else:
                failures += 1
                logger.warning("evidence quote validation failed", extra={
                    "evidence_execution_id": str(execution.execution_id),
                    "claim_id": str(claim_id), "source_id": str(item.source_id),
                })
        justified = self._justified_status(assessment.recommended_claim_status, validated)
        if justified != context.claim.status:
            evidence_ids = await self._repository.list_execution_evidence_ids(
                claim_id, user_id, execution.execution_id
            )
            await self._resolutions.resolve(user_id, ClaimResolutionProposal(
                claim_id=claim_id, proposed_status=justified,
                resolution_reason="Evidence recommendation validated by deterministic resolution rules",
                evidence_ids=evidence_ids, evidence=validated,
                trigger_type=ResolutionTriggerType.EVIDENCE_AGENT,
                confidence=assessment.confidence,
            ))
        logger.info("evidence resolution completed", extra={
            "evidence_execution_id": str(execution.execution_id), "claim_id": str(claim_id),
            "related_turns_count": len(context.related_transcript_turns),
            "evidence_items_proposed": len(proposed), "evidence_items_validated": len(validated),
            "quote_validation_failures": failures, "recommended_status": justified.value,
            "latency_ms": execution.latency_ms, "model": execution.model,
            "prompt_version": execution.prompt_version,
        })
        return EvidenceResolutionResult(
            claim_id=claim_id, evidence_execution_id=execution.execution_id,
            proposed_count=len(proposed), validated_count=len(validated),
            quote_validation_failures=failures,
            recommended_status=assessment.recommended_claim_status, applied_status=justified,
        )

    @staticmethod
    def _justified_status(recommended: ClaimStatus, items: list[EvidenceItem]) -> ClaimStatus:
        rank = {EvidenceStrength.NONE: 0, EvidenceStrength.WEAK: 1,
                EvidenceStrength.MODERATE: 2, EvidenceStrength.STRONG: 3}
        supports = [item for item in items if item.direction == EvidenceDirection.SUPPORTS and rank[item.strength] >= 2]
        weakens = [item for item in items if item.direction == EvidenceDirection.WEAKENS and rank[item.strength] >= 2]
        if recommended == ClaimStatus.CORROBORATED and supports and not weakens:
            return recommended
        if recommended == ClaimStatus.PARTIALLY_HELD and supports and weakens:
            return recommended
        if recommended == ClaimStatus.WALKED_BACK and any(
            item.reason_code in {EvidenceReasonCode.OWNERSHIP_NARROWED, EvidenceReasonCode.EXPLICIT_RETRACTION}
            for item in weakens
        ):
            return recommended
        if recommended == ClaimStatus.CONTRADICTED and supports and any(
            item.strength == EvidenceStrength.STRONG and item.reason_code == EvidenceReasonCode.DIRECT_CONFLICT
            for item in weakens
        ):
            return recommended
        if not supports and not weakens:
            return ClaimStatus.INSUFFICIENT_EVIDENCE
        return ClaimStatus.PARTIALLY_HELD if supports and weakens else ClaimStatus.INSUFFICIENT_EVIDENCE

