from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .claims_models import ClaimSource, ClaimStatus, EvidenceDirection
from .verdict_models import VerdictCode


class ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportSession(ReportModel):
    target_role: str
    completed_at: datetime
    duration_seconds: int = Field(ge=0)
    assessment_confidence: float = Field(ge=0, le=1)


class ReportVerdict(ReportModel):
    code: VerdictCode
    label: str
    summary: str


class ReportReadiness(ReportModel):
    low: int | None = Field(default=None, ge=0, le=100)
    high: int | None = Field(default=None, ge=0, le=100)
    label: str
    signal_strength: str
    confidence_note: str


class ReportEvidence(ReportModel):
    turn_id: UUID | None = None
    timecode_ms: int | None = Field(default=None, ge=0)
    quote: str
    direction: EvidenceDirection


class ReportClaim(ReportModel):
    id: UUID
    claim_text: str
    source: ClaimSource
    status: ClaimStatus
    explanation: str
    evidence: list[ReportEvidence] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ReportClaimsAudit(ReportModel):
    held: list[ReportClaim] = Field(default_factory=list)
    partially_held: list[ReportClaim] = Field(default_factory=list)
    walked_back: list[ReportClaim] = Field(default_factory=list)
    contradicted: list[ReportClaim] = Field(default_factory=list)
    insufficient_evidence: list[ReportClaim] = Field(default_factory=list)
    unverified: list[ReportClaim] = Field(default_factory=list)


class ReportSkillAssessment(ReportModel):
    skill: str
    status: str
    readiness: ReportReadiness | None = None
    signal_strength: str
    evidence: list[ReportEvidence] = Field(default_factory=list)
    explanation: str


class SessionMomentType(StrEnum):
    STRONG_EVIDENCE = "STRONG_EVIDENCE"
    RECOVERY = "RECOVERY"
    OWNERSHIP_CLARIFICATION = "OWNERSHIP_CLARIFICATION"
    UNSUPPORTED_SCALE = "UNSUPPORTED_SCALE"
    TECHNICAL_DEPTH = "TECHNICAL_DEPTH"


class ReportSessionMoment(ReportModel):
    type: SessionMomentType
    turn_id: UUID | None = None
    timecode_ms: int | None = Field(default=None, ge=0)
    quote: str | None = None
    explanation: str


class TrustAndLimitations(ReportModel):
    ai_assessments_can_make_mistakes: bool = True
    candidate_may_dispute_assessments: bool = True
    skills_may_have_insufficient_signal: bool = True
    evaluates_this_interview_evidence: bool = True
    outcome_validation_status: str


class ReportResponse(ReportModel):
    session: ReportSession
    verdict: ReportVerdict
    role_readiness: ReportReadiness
    interview_readiness: ReportReadiness
    claims_audit: ReportClaimsAudit
    skill_assessments: list[ReportSkillAssessment] = Field(default_factory=list)
    session_moments: list[ReportSessionMoment] = Field(default_factory=list)
    root_cause: str
    trust_and_limitations: TrustAndLimitations
    prescription: dict | None = None

