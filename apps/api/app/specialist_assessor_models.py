from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpecialistModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessorType(StrEnum):
    TECHNICAL = "TECHNICAL"
    BEHAVIOUR = "BEHAVIOUR"
    CLAIMS = "CLAIMS"


class SpecialistStatus(StrEnum):
    COMPLETE = "COMPLETE"
    NOT_ENOUGH_SIGNAL = "NOT_ENOUGH_SIGNAL"


class SignalStrength(StrEnum):
    NONE = "NONE"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class AssessmentEvidence(SpecialistModel):
    turn_id: UUID
    quote: str = Field(min_length=1, max_length=3000)


class DomainAssessment(SpecialistModel):
    domain: str = Field(min_length=2, max_length=200)
    status: SpecialistStatus
    signal_strength: SignalStrength
    confidence: float = Field(ge=0, le=1)
    evidence_turn_ids: list[UUID] = Field(default_factory=list, max_length=30)
    evidence_quotes: list[AssessmentEvidence] = Field(default_factory=list, max_length=30)
    reason_summary: str = Field(min_length=3, max_length=1500)

    @model_validator(mode="after")
    def evidence_matches_status(self) -> DomainAssessment:
        if self.status == SpecialistStatus.NOT_ENOUGH_SIGNAL and self.signal_strength != SignalStrength.NONE:
            raise ValueError("not-enough-signal assessments must have no signal strength")
        if self.status == SpecialistStatus.COMPLETE and not self.evidence_turn_ids:
            raise ValueError("completed assessments require evidence turns")
        if not {item.turn_id for item in self.evidence_quotes} <= set(self.evidence_turn_ids):
            raise ValueError("evidence quotes must reference declared turns")
        return self


class SpecialistAssessmentOutput(SpecialistModel):
    assessor_type: AssessorType
    status: SpecialistStatus
    dimensions: list[DomainAssessment] = Field(default_factory=list, max_length=30)
    competency_or_domain_assessments: list[DomainAssessment] = Field(default_factory=list, max_length=50)
    signal_strength: SignalStrength
    confidence: float = Field(ge=0, le=1)
    evidence_turn_ids: list[UUID] = Field(default_factory=list, max_length=100)
    evidence_quotes: list[AssessmentEvidence] = Field(default_factory=list, max_length=100)
    reason_summary: str = Field(min_length=3, max_length=2000)

    @model_validator(mode="after")
    def result_has_consistent_signal(self) -> SpecialistAssessmentOutput:
        if self.status == SpecialistStatus.NOT_ENOUGH_SIGNAL:
            if self.signal_strength != SignalStrength.NONE or self.evidence_turn_ids:
                raise ValueError("not-enough-signal output cannot claim evidence")
        if self.status == SpecialistStatus.COMPLETE and not self.evidence_turn_ids:
            raise ValueError("complete output requires evidence")
        all_turns = set(self.evidence_turn_ids)
        if not {item.turn_id for item in self.evidence_quotes} <= all_turns:
            raise ValueError("output quotes must reference evidence turns")
        return self


class AssessmentTranscriptTurn(SpecialistModel):
    id: UUID
    speaker: str
    text: str = Field(min_length=1, max_length=20_000)
    turn_type: str
    phase: str


class SpecialistAssessmentContext(SpecialistModel):
    session_id: UUID
    assessor_type: AssessorType
    role_competencies: list[dict[str, str | float]] = Field(default_factory=list)
    transcript_turns: list[AssessmentTranscriptTurn] = Field(default_factory=list, max_length=100)
    claims: list[dict[str, str | float | None]] = Field(default_factory=list, max_length=100)
    validated_evidence: list[dict[str, str | float | None]] = Field(default_factory=list, max_length=200)
    skeptic_observations: list[dict[str, str | float | None]] = Field(default_factory=list, max_length=100)
    rubric_anchors: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    rubric_version: str = "v1"


class StoredSpecialistAssessment(SpecialistModel):
    id: UUID
    session_id: UUID
    assessor_type: AssessorType
    status: SpecialistStatus
    result_json: SpecialistAssessmentOutput
    model: str
    model_version: str
    prompt_version: str
    rubric_version: str
    created_at: datetime


class SpecialistAssessmentBundle(SpecialistModel):
    session_id: UUID
    technical: StoredSpecialistAssessment | None = None
    behaviour: StoredSpecialistAssessment | None = None
    claims: StoredSpecialistAssessment | None = None
    disagreements: list[str] = Field(default_factory=list)

