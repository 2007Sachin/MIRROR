from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .claims_models import ClaimRead, ClaimStatus
from .evidence_models import EvidenceItem


class ResolutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResolutionTriggerType(StrEnum):
    SKEPTIC_FLAG = "SKEPTIC_FLAG"
    EVIDENCE_AGENT = "EVIDENCE_AGENT"
    USER_CORRECTION = "USER_CORRECTION"
    ADMIN_REVIEW = "ADMIN_REVIEW"
    SESSION_FINALIZATION = "SESSION_FINALIZATION"


class ClaimResolutionProposal(ResolutionModel):
    claim_id: UUID
    proposed_status: ClaimStatus
    resolution_reason: str = Field(min_length=3, max_length=2000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=200)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=100)
    trigger_type: ResolutionTriggerType
    confidence: float = Field(ge=0, le=1)
    extraction_correction: bool = False

    @model_validator(mode="after")
    def correction_semantics(self) -> ClaimResolutionProposal:
        if self.extraction_correction and self.trigger_type != ResolutionTriggerType.USER_CORRECTION:
            raise ValueError("extraction corrections must be user corrections")
        return self


class ClaimResolutionRecord(ResolutionModel):
    id: UUID
    user_id: UUID
    claim_id: UUID
    previous_status: ClaimStatus
    new_status: ClaimStatus
    resolution_reason: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    trigger_type: ResolutionTriggerType
    confidence: float = Field(ge=0, le=1)
    created_at: datetime


class ClaimResolutionResult(ResolutionModel):
    claim: ClaimRead
    resolution: ClaimResolutionRecord


class ClaimsAudit(ResolutionModel):
    held: list[ClaimRead] = Field(default_factory=list)
    partially_held: list[ClaimRead] = Field(default_factory=list)
    walked_back: list[ClaimRead] = Field(default_factory=list)
    contradicted: list[ClaimRead] = Field(default_factory=list)
    insufficient_evidence: list[ClaimRead] = Field(default_factory=list)
    unverified: list[ClaimRead] = Field(default_factory=list)

