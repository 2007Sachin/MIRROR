from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .claim_resolution_models import ClaimsAudit
from .specialist_assessor_models import SpecialistAssessmentBundle


class VerdictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VerdictCode(StrEnum):
    NOT_READY_YET = "NOT_READY_YET"
    DEVELOPING = "DEVELOPING"
    NEAR_READY = "NEAR_READY"
    READY = "READY"
    STRONG = "STRONG"


class RootCauseCode(StrEnum):
    OWNERSHIP_SPECIFICITY = "OWNERSHIP_SPECIFICITY"
    TECHNICAL_DEPTH = "TECHNICAL_DEPTH"
    ANSWER_STRUCTURE = "ANSWER_STRUCTURE"
    OUTCOME_EVIDENCE = "OUTCOME_EVIDENCE"
    COMPOSURE_UNDER_PROBE = "COMPOSURE_UNDER_PROBE"
    ROLE_SKILL_GAP = "ROLE_SKILL_GAP"


class AggregatedAssessment(VerdictModel):
    role_readiness_internal: float = Field(ge=0, le=100)
    interview_readiness_internal: float = Field(ge=0, le=100)
    role_readiness_low: int = Field(ge=0, le=100)
    role_readiness_high: int = Field(ge=0, le=100)
    interview_readiness_low: int = Field(ge=0, le=100)
    interview_readiness_high: int = Field(ge=0, le=100)
    overall_signal_confidence: float = Field(ge=0, le=1)
    availability_status: str
    verdict_code: VerdictCode
    root_cause_code: RootCauseCode


class VerdictLanguageInput(VerdictModel):
    aggregate: AggregatedAssessment
    specialist_summaries: dict[str, str]
    claims_audit: ClaimsAudit


class VerdictLanguageOutput(VerdictModel):
    verdict_summary: str = Field(min_length=10, max_length=1000)
    root_cause_explanation: str = Field(min_length=10, max_length=1000)
    confidence_note: str = Field(min_length=10, max_length=1000)

