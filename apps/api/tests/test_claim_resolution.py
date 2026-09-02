from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.claim_resolution_models import (
    ClaimResolutionProposal, ClaimResolutionRecord, ResolutionTriggerType,
)
from app.claim_resolution_repository import ConcurrentClaimResolution
from app.claim_resolution_service import (
    ClaimResolutionRejected, ClaimResolutionService, ClaimsAuditService,
)
from app.claims_models import (
    ClaimRead, ClaimSource, ClaimStatus, ClaimType, VerificationPriority,
)
from app.evidence_models import (
    EvidenceDirection, EvidenceItem, EvidenceReasonCode,
    EvidenceSourceType, EvidenceStrength,
)


USER_ID = UUID("f1000000-0000-4000-8000-000000000001")


def make_claim(status=ClaimStatus.UNVERIFIED):
    return ClaimRead(
        id=uuid4(), user_id=USER_ID, claim_text="I built the database architecture.",
        claim_type=ClaimType.OWNERSHIP, source=ClaimSource.RESUME,
        confidence=0.9, verification_priority=VerificationPriority.HIGH,
        status=status, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )


def evidence(direction, strength=EvidenceStrength.MODERATE,
             reason=EvidenceReasonCode.DIRECT_SUPPORT):
    turn_id = uuid4()
    return EvidenceItem(
        source_type=EvidenceSourceType.CANDIDATE_TURN, source_id=turn_id,
        turn_id=turn_id, quote="Stored exact quote", direction=direction,
        strength=strength, reason_code=reason,
    )


class MemoryResolutionRepository:
    def __init__(self, *claims):
        self.claims = {claim.id: claim for claim in claims}
        self.history = []

    async def get_claim(self, claim_id, user_id):
        item = self.claims.get(claim_id)
        return item if item and item.user_id == user_id else None

    async def commit(self, claim_id, user_id, expected_status, new_status, reason,
                     evidence_ids, trigger_type, confidence):
        current = self.claims[claim_id]
        if current.status != expected_status:
            raise ConcurrentClaimResolution
        updated = current.model_copy(update={"status": new_status, "updated_at": datetime.now(UTC)})
        record = ClaimResolutionRecord(
            id=uuid4(), user_id=user_id, claim_id=claim_id,
            previous_status=current.status, new_status=new_status,
            resolution_reason=reason, evidence_ids=evidence_ids,
            trigger_type=trigger_type, confidence=confidence,
            created_at=datetime.now(UTC),
        )
        self.claims[claim_id] = updated
        self.history.append(record)
        return updated, record

    async def list_claims(self, user_id):
        return [item for item in self.claims.values() if item.user_id == user_id]


def proposal(claim, status, items=None, **changes):
    values = {
        "claim_id": claim.id, "proposed_status": status,
        "resolution_reason": "Validated evidence supports this transition",
        "evidence_ids": [uuid4()] if items else [], "evidence": items or [],
        "trigger_type": ResolutionTriggerType.EVIDENCE_AGENT,
        "confidence": 0.9,
    }
    values.update(changes)
    return ClaimResolutionProposal(**values)


@pytest.mark.parametrize("target", list(ClaimStatus)[1:])
def test_unverified_has_explicit_legal_transitions(target):
    claim = make_claim()
    support = evidence(EvidenceDirection.SUPPORTS)
    weakening = evidence(EvidenceDirection.WEAKENS)
    items = {
        ClaimStatus.CORROBORATED: [support],
        ClaimStatus.PARTIALLY_HELD: [support, weakening],
        ClaimStatus.WALKED_BACK: [evidence(EvidenceDirection.WEAKENS, reason=EvidenceReasonCode.EXPLICIT_RETRACTION)],
        ClaimStatus.CONTRADICTED: [support, evidence(EvidenceDirection.WEAKENS, EvidenceStrength.STRONG, EvidenceReasonCode.DIRECT_CONFLICT)],
        ClaimStatus.INSUFFICIENT_EVIDENCE: [],
    }[target]
    result = asyncio.run(ClaimResolutionService(MemoryResolutionRepository(claim)).resolve(
        USER_ID, proposal(claim, target, items)
    ))
    assert result.claim.status == target
    assert result.resolution.previous_status == ClaimStatus.UNVERIFIED


def test_invalid_transition_is_rejected():
    claim = make_claim(ClaimStatus.CORROBORATED)
    with pytest.raises(ClaimResolutionRejected):
        asyncio.run(ClaimResolutionService(MemoryResolutionRepository(claim)).resolve(
            USER_ID, proposal(claim, ClaimStatus.INSUFFICIENT_EVIDENCE)
        ))


def test_walked_back_preserves_original_claim_and_history():
    claim = make_claim()
    repository = MemoryResolutionRepository(claim)
    result = asyncio.run(ClaimResolutionService(repository).resolve(
        USER_ID, proposal(claim, ClaimStatus.WALKED_BACK, [
            evidence(EvidenceDirection.WEAKENS, EvidenceStrength.STRONG,
                     EvidenceReasonCode.OWNERSHIP_NARROWED)
        ])
    ))
    assert result.claim.claim_text == claim.claim_text
    assert repository.history[0].previous_status == ClaimStatus.UNVERIFIED


def test_user_extraction_correction_is_not_walked_back():
    claim = make_claim()
    result = asyncio.run(ClaimResolutionService(MemoryResolutionRepository(claim)).resolve(
        USER_ID, proposal(
            claim, ClaimStatus.WALKED_BACK, trigger_type=ResolutionTriggerType.USER_CORRECTION,
            extraction_correction=True, resolution_reason="AI extracted the ownership incorrectly",
        )
    ))
    assert result.claim.status == ClaimStatus.UNVERIFIED
    assert result.resolution.trigger_type == ResolutionTriggerType.USER_CORRECTION


def test_contradiction_requires_strong_direct_conflict():
    claim = make_claim(ClaimStatus.CORROBORATED)
    with pytest.raises(ClaimResolutionRejected):
        asyncio.run(ClaimResolutionService(MemoryResolutionRepository(claim)).resolve(
            USER_ID, proposal(claim, ClaimStatus.CONTRADICTED, [
                evidence(EvidenceDirection.SUPPORTS),
                evidence(EvidenceDirection.WEAKENS, reason=EvidenceReasonCode.AMBIGUOUS),
            ])
        ))


def test_finalization_can_preserve_uncertainty():
    claim = make_claim()
    result = asyncio.run(ClaimResolutionService(MemoryResolutionRepository(claim)).resolve(
        USER_ID, proposal(
            claim, ClaimStatus.INSUFFICIENT_EVIDENCE,
            trigger_type=ResolutionTriggerType.SESSION_FINALIZATION,
            resolution_reason="High-priority claim remained unresolved at session end",
        )
    ))
    assert result.claim.status == ClaimStatus.INSUFFICIENT_EVIDENCE


def test_concurrent_resolution_uses_expected_state_protection():
    claim = make_claim()
    repository = MemoryResolutionRepository(claim)
    stale = proposal(claim, ClaimStatus.CORROBORATED, [evidence(EvidenceDirection.SUPPORTS)])
    repository.claims[claim.id] = claim.model_copy(update={"status": ClaimStatus.PARTIALLY_HELD})
    with pytest.raises(ConcurrentClaimResolution):
        asyncio.run(repository.commit(
            claim.id, USER_ID, ClaimStatus.UNVERIFIED, stale.proposed_status,
            stale.resolution_reason, stale.evidence_ids, stale.trigger_type, stale.confidence,
        ))


def test_claims_audit_groups_every_state():
    claims = [make_claim(status) for status in ClaimStatus]
    audit = asyncio.run(ClaimsAuditService(MemoryResolutionRepository(*claims)).audit(USER_ID))
    assert len(audit.held) == 1
    assert len(audit.partially_held) == 1
    assert len(audit.walked_back) == 1
    assert len(audit.contradicted) == 1
    assert len(audit.insufficient_evidence) == 1
    assert len(audit.unverified) == 1

