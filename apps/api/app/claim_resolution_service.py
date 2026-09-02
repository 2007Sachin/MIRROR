from __future__ import annotations

from uuid import UUID

from .claim_resolution_models import (
    ClaimResolutionProposal, ClaimResolutionResult, ClaimsAudit,
    ResolutionTriggerType,
)
from .claim_resolution_repository import ClaimResolutionRepository
from .claims_models import ClaimStatus
from .evidence_models import EvidenceDirection, EvidenceReasonCode, EvidenceStrength


class ClaimResolutionRejected(Exception):
    pass


LEGAL_TRANSITIONS: dict[ClaimStatus, frozenset[ClaimStatus]] = {
    ClaimStatus.UNVERIFIED: frozenset({
        ClaimStatus.CORROBORATED, ClaimStatus.PARTIALLY_HELD,
        ClaimStatus.WALKED_BACK, ClaimStatus.CONTRADICTED,
        ClaimStatus.INSUFFICIENT_EVIDENCE,
    }),
    ClaimStatus.CORROBORATED: frozenset({
        ClaimStatus.PARTIALLY_HELD, ClaimStatus.WALKED_BACK,
        ClaimStatus.CONTRADICTED,
    }),
    ClaimStatus.PARTIALLY_HELD: frozenset({
        ClaimStatus.CORROBORATED, ClaimStatus.WALKED_BACK,
        ClaimStatus.CONTRADICTED, ClaimStatus.INSUFFICIENT_EVIDENCE,
    }),
    ClaimStatus.WALKED_BACK: frozenset({
        ClaimStatus.PARTIALLY_HELD, ClaimStatus.CORROBORATED,
        ClaimStatus.CONTRADICTED,
    }),
    ClaimStatus.CONTRADICTED: frozenset({
        ClaimStatus.PARTIALLY_HELD, ClaimStatus.CORROBORATED,
    }),
    ClaimStatus.INSUFFICIENT_EVIDENCE: frozenset({
        ClaimStatus.CORROBORATED, ClaimStatus.PARTIALLY_HELD,
        ClaimStatus.WALKED_BACK, ClaimStatus.CONTRADICTED,
    }),
}


class ClaimResolutionService:
    """The sole application authority permitted to commit claim status."""

    def __init__(self, repository: ClaimResolutionRepository) -> None:
        self._repository = repository

    async def resolve(self, user_id: UUID, proposal: ClaimResolutionProposal) -> ClaimResolutionResult:
        claim = await self._repository.get_claim(proposal.claim_id, user_id)
        if claim is None:
            raise ClaimResolutionRejected("claim not found")
        target = proposal.proposed_status
        if proposal.extraction_correction:
            # Correcting AI extraction before interview is audit history, not a
            # candidate retracting a statement.
            if target == ClaimStatus.WALKED_BACK:
                target = ClaimStatus.UNVERIFIED
            if claim.status != ClaimStatus.UNVERIFIED:
                raise ClaimResolutionRejected("extraction correction cannot rewrite interview state")
        elif target == claim.status or target not in LEGAL_TRANSITIONS[claim.status]:
            raise ClaimResolutionRejected("illegal claim status transition")
        self._validate_support(target, proposal)
        updated, record = await self._repository.commit(
            claim.id, user_id, claim.status, target, proposal.resolution_reason,
            proposal.evidence_ids, proposal.trigger_type, proposal.confidence,
        )
        return ClaimResolutionResult(claim=updated, resolution=record)

    @staticmethod
    def _validate_support(target: ClaimStatus, proposal: ClaimResolutionProposal) -> None:
        substantial_support = [item for item in proposal.evidence if
            item.direction == EvidenceDirection.SUPPORTS and item.strength in {EvidenceStrength.MODERATE, EvidenceStrength.STRONG}]
        substantial_weakening = [item for item in proposal.evidence if
            item.direction == EvidenceDirection.WEAKENS and item.strength in {EvidenceStrength.MODERATE, EvidenceStrength.STRONG}]
        if target == ClaimStatus.CORROBORATED and (not substantial_support or substantial_weakening):
            raise ClaimResolutionRejected("corroboration requires unconflicted supporting evidence")
        if target == ClaimStatus.PARTIALLY_HELD and not (substantial_support and substantial_weakening):
            raise ClaimResolutionRejected("partial status requires support and weakening evidence")
        if target == ClaimStatus.WALKED_BACK and not any(
            item.reason_code in {EvidenceReasonCode.OWNERSHIP_NARROWED, EvidenceReasonCode.EXPLICIT_RETRACTION}
            for item in substantial_weakening
        ):
            raise ClaimResolutionRejected("walk-back requires explicit narrowing or retraction")
        if target == ClaimStatus.CONTRADICTED and not (
            substantial_support and any(item.strength == EvidenceStrength.STRONG and item.reason_code == EvidenceReasonCode.DIRECT_CONFLICT for item in substantial_weakening)
        ):
            raise ClaimResolutionRejected("contradiction requires strong direct-conflict evidence")
        if target == ClaimStatus.INSUFFICIENT_EVIDENCE and (substantial_support or substantial_weakening):
            raise ClaimResolutionRejected("substantive evidence cannot be marked insufficient")


class ClaimsAuditService:
    def __init__(self, repository: ClaimResolutionRepository) -> None:
        self._repository = repository

    async def audit(self, user_id: UUID) -> ClaimsAudit:
        groups = {status: [] for status in ClaimStatus}
        for claim in await self._repository.list_claims(user_id):
            groups[claim.status].append(claim)
        return ClaimsAudit(
            held=groups[ClaimStatus.CORROBORATED],
            partially_held=groups[ClaimStatus.PARTIALLY_HELD],
            walked_back=groups[ClaimStatus.WALKED_BACK],
            contradicted=groups[ClaimStatus.CONTRADICTED],
            insufficient_evidence=groups[ClaimStatus.INSUFFICIENT_EVIDENCE],
            unverified=groups[ClaimStatus.UNVERIFIED],
        )

