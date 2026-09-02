from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClaimsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimType(StrEnum):
    SKILL = "SKILL"
    PROJECT = "PROJECT"
    SCALE = "SCALE"
    OWNERSHIP = "OWNERSHIP"
    TOOL = "TOOL"
    OUTCOME = "OUTCOME"
    EXPERIENCE = "EXPERIENCE"
    RESPONSIBILITY = "RESPONSIBILITY"


class ClaimSource(StrEnum):
    RESUME = "RESUME"
    JD = "JD"
    SPOKEN = "SPOKEN"
    PROJECT = "PROJECT"


class ClaimStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    CORROBORATED = "CORROBORATED"
    PARTIALLY_HELD = "PARTIALLY_HELD"
    WALKED_BACK = "WALKED_BACK"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class VerificationPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ClaimEntityType(StrEnum):
    SKILL = "SKILL"
    PROJECT = "PROJECT"
    TOOL = "TOOL"
    COMPANY = "COMPANY"
    METRIC = "METRIC"
    OUTCOME = "OUTCOME"
    RESPONSIBILITY = "RESPONSIBILITY"


class ClaimNodeType(StrEnum):
    CLAIM = "CLAIM"
    ENTITY = "ENTITY"


class ClaimRelationType(StrEnum):
    ABOUT_SKILL = "ABOUT_SKILL"
    ABOUT_PROJECT = "ABOUT_PROJECT"
    USES_TOOL = "USES_TOOL"
    ABOUT_COMPANY = "ABOUT_COMPANY"
    HAS_METRIC = "HAS_METRIC"
    CLAIMS_OUTCOME = "CLAIMS_OUTCOME"
    CLAIMS_OWNERSHIP = "CLAIMS_OWNERSHIP"
    CLAIMS_RESPONSIBILITY = "CLAIMS_RESPONSIBILITY"
    RELATED_TO = "RELATED_TO"


class ClaimRelationSource(StrEnum):
    RESUME_ANALYSIS = "RESUME_ANALYSIS"
    APPLICATION = "APPLICATION"
    USER = "USER"
    INTERVIEW = "INTERVIEW"


class ClaimChangedBy(StrEnum):
    SYSTEM = "SYSTEM"
    AI = "AI"
    USER = "USER"
    ADMIN = "ADMIN"


class ClaimEvidenceType(StrEnum):
    DOCUMENT_EXCERPT = "DOCUMENT_EXCERPT"
    INTERVIEW_TURN = "INTERVIEW_TURN"
    USER_CORRECTION = "USER_CORRECTION"
    SYSTEM_OBSERVATION = "SYSTEM_OBSERVATION"


class EvidenceDirection(StrEnum):
    SUPPORTS = "SUPPORTS"
    WEAKENS = "WEAKENS"
    CONTEXT_ONLY = "CONTEXT_ONLY"


class ClaimCreate(ClaimsModel):
    session_id: UUID | None = None
    claim_text: str = Field(min_length=3, max_length=5000)
    claim_type: ClaimType
    source: ClaimSource
    source_document_id: UUID | None = None
    source_reference: str | None = Field(default=None, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    verification_priority: VerificationPriority = VerificationPriority.MEDIUM
    synthetic: bool = False


class ClaimRead(ClaimCreate):
    id: UUID
    user_id: UUID
    status: ClaimStatus
    created_at: datetime
    updated_at: datetime


class ClaimEntityCreate(ClaimsModel):
    entity_type: ClaimEntityType
    canonical_name: str = Field(min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimEntityRead(ClaimEntityCreate):
    id: UUID
    user_id: UUID
    created_at: datetime


class ClaimRelationCreate(ClaimsModel):
    source_entity_type: ClaimNodeType
    source_entity_id: UUID
    relation_type: ClaimRelationType
    target_entity_type: ClaimNodeType
    target_entity_id: UUID
    confidence: float = Field(ge=0, le=1)
    source: ClaimRelationSource


class ClaimRelationRead(ClaimRelationCreate):
    id: UUID
    user_id: UUID
    created_at: datetime


class ClaimVersionCreate(ClaimsModel):
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any]
    changed_by: ClaimChangedBy
    reason: str = Field(min_length=3, max_length=2000)


class ClaimVersionRead(ClaimVersionCreate):
    id: UUID
    user_id: UUID
    claim_id: UUID
    version: int = Field(gt=0)
    created_at: datetime


class ClaimEvidenceCreate(ClaimsModel):
    evidence_type: ClaimEvidenceType
    turn_id: UUID | None = None
    document_id: UUID | None = None
    quote_text: str | None = Field(default=None, min_length=1, max_length=5000)
    evidence_direction: EvidenceDirection
    strength: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_anchor(self) -> ClaimEvidenceCreate:
        if not (self.turn_id or self.document_id or self.quote_text):
            raise ValueError("evidence must reference a turn, document, or quote")
        if self.evidence_type == ClaimEvidenceType.INTERVIEW_TURN and not self.turn_id:
            raise ValueError("interview-turn evidence requires a turn")
        if (
            self.evidence_type == ClaimEvidenceType.DOCUMENT_EXCERPT
            and not self.document_id
        ):
            raise ValueError("document evidence requires a document")
        return self


class ClaimEvidenceRead(ClaimEvidenceCreate):
    id: UUID
    user_id: UUID
    claim_id: UUID
    created_at: datetime


class ClaimGraphRead(ClaimsModel):
    claim: ClaimRead
    entities: list[ClaimEntityRead] = Field(default_factory=list)
    relations: list[ClaimRelationRead] = Field(default_factory=list)
    versions: list[ClaimVersionRead] = Field(default_factory=list)
    evidence: list[ClaimEvidenceRead] = Field(default_factory=list)
    related_claims: list[ClaimRead] = Field(default_factory=list)

