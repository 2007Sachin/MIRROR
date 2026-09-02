from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .claims_models import ClaimEvidenceRead, ClaimRead, ClaimStatus


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceSourceType(StrEnum):
    RESUME = "RESUME"
    CANDIDATE_TURN = "CANDIDATE_TURN"
    INTERVIEWER_TURN = "INTERVIEWER_TURN"
    PROJECT = "PROJECT"
    OTHER_DOCUMENT = "OTHER_DOCUMENT"


class EvidenceDirection(StrEnum):
    SUPPORTS = "SUPPORTS"
    WEAKENS = "WEAKENS"
    CONTEXT_ONLY = "CONTEXT_ONLY"


class EvidenceStrength(StrEnum):
    NONE = "NONE"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class EvidenceReasonCode(StrEnum):
    DIRECT_SUPPORT = "DIRECT_SUPPORT"
    OWNERSHIP_NARROWED = "OWNERSHIP_NARROWED"
    EXPLICIT_RETRACTION = "EXPLICIT_RETRACTION"
    METRIC_UNSUPPORTED = "METRIC_UNSUPPORTED"
    SCOPE_DIFFERENCE = "SCOPE_DIFFERENCE"
    DIRECT_CONFLICT = "DIRECT_CONFLICT"
    BACKGROUND_CONTEXT = "BACKGROUND_CONTEXT"
    AMBIGUOUS = "AMBIGUOUS"


class EvidenceItem(EvidenceModel):
    source_type: EvidenceSourceType
    source_id: UUID
    turn_id: UUID | None = None
    document_id: UUID | None = None
    quote: str = Field(min_length=1, max_length=5000)
    direction: EvidenceDirection
    strength: EvidenceStrength
    reason_code: EvidenceReasonCode

    @model_validator(mode="after")
    def source_anchor_matches(self) -> EvidenceItem:
        turn_source = self.source_type in {
            EvidenceSourceType.CANDIDATE_TURN,
            EvidenceSourceType.INTERVIEWER_TURN,
        }
        if turn_source and (self.turn_id != self.source_id or self.document_id):
            raise ValueError("turn evidence must use its turn as source")
        if not turn_source and self.source_type != EvidenceSourceType.PROJECT:
            if self.document_id != self.source_id or self.turn_id:
                raise ValueError("document evidence must use its document as source")
        return self


class EvidenceSourceExcerpt(EvidenceModel):
    source_type: EvidenceSourceType
    source_id: UUID
    text: str = Field(min_length=1, max_length=20_000)
    source_reference: str | None = None


class EvidenceContext(EvidenceModel):
    claim: ClaimRead
    resume_source_excerpts: list[EvidenceSourceExcerpt] = Field(default_factory=list)
    related_transcript_turns: list[EvidenceSourceExcerpt] = Field(default_factory=list)
    related_flags: list[dict[str, str | float | bool | None]] = Field(default_factory=list)
    related_probes: list[EvidenceSourceExcerpt] = Field(default_factory=list)
    existing_evidence: list[ClaimEvidenceRead] = Field(default_factory=list)
    project_context: list[dict[str, str]] = Field(default_factory=list)


class EvidenceAssessment(EvidenceModel):
    claim_id: UUID
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    weakening_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    context_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    evidence_strength: EvidenceStrength
    recommended_claim_status: ClaimStatus
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def directions_match_buckets(self) -> EvidenceAssessment:
        expected = (
            (self.supporting_evidence, EvidenceDirection.SUPPORTS),
            (self.weakening_evidence, EvidenceDirection.WEAKENS),
            (self.context_evidence, EvidenceDirection.CONTEXT_ONLY),
        )
        if any(item.direction != direction for items, direction in expected for item in items):
            raise ValueError("evidence direction does not match its collection")
        return self


class ValidatedEvidenceItem(EvidenceModel):
    item: EvidenceItem
    validated: bool = True


class EvidenceResolutionResult(EvidenceModel):
    claim_id: UUID
    evidence_execution_id: UUID
    proposed_count: int
    validated_count: int
    quote_validation_failures: int
    recommended_status: ClaimStatus
    applied_status: ClaimStatus

