from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResumeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkillCategory(StrEnum):
    TECHNICAL = "TECHNICAL"
    BUSINESS = "BUSINESS"
    DOMAIN = "DOMAIN"
    TOOL = "TOOL"
    SOFT_SKILL = "SOFT_SKILL"
    OTHER = "OTHER"


class ResumeClaimType(StrEnum):
    SKILL = "SKILL"
    PROJECT = "PROJECT"
    SCALE = "SCALE"
    OWNERSHIP = "OWNERSHIP"
    TOOL = "TOOL"
    OUTCOME = "OUTCOME"
    EXPERIENCE = "EXPERIENCE"
    RESPONSIBILITY = "RESPONSIBILITY"


class VerificationPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ResumeAnalysisStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ClaimReviewStatus(StrEnum):
    CORRECT = "CORRECT"
    NEEDS_CORRECTION = "NEEDS_CORRECTION"


class CandidateProfileContext(ResumeModel):
    career_stage: str | None = None
    target_role: str | None = None
    preferred_language: str | None = None


class ResumeAgentInput(ResumeModel):
    # Execution identifiers are validated and available to application code but
    # excluded from the provider payload because they do not aid interpretation.
    document_id: UUID = Field(exclude=True)
    user_id: UUID = Field(exclude=True)
    resume_text: str = Field(min_length=1, max_length=200_000)
    candidate_profile: CandidateProfileContext


class ResumeSkill(ResumeModel):
    name: str = Field(min_length=1, max_length=200)
    category: SkillCategory
    source_reference: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class ResumeProject(ResumeModel):
    project_name: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=3000)
    technologies: list[str] = Field(default_factory=list, max_length=100)
    claimed_responsibilities: list[str] = Field(default_factory=list, max_length=100)
    claimed_outcomes: list[str] = Field(default_factory=list, max_length=100)
    source_reference: str = Field(min_length=1, max_length=500)


class ResumeWorkExperience(ResumeModel):
    organization: str = Field(min_length=1, max_length=300)
    role: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=3000)
    claimed_responsibilities: list[str] = Field(default_factory=list, max_length=100)
    claimed_outcomes: list[str] = Field(default_factory=list, max_length=100)
    start_date: str | None = Field(default=None, max_length=100)
    end_date: str | None = Field(default=None, max_length=100)
    source_reference: str = Field(min_length=1, max_length=500)


class ResumeEducation(ResumeModel):
    institution: str = Field(min_length=1, max_length=300)
    qualification: str = Field(min_length=1, max_length=300)
    field_of_study: str | None = Field(default=None, max_length=300)
    start_date: str | None = Field(default=None, max_length=100)
    end_date: str | None = Field(default=None, max_length=100)
    source_reference: str = Field(min_length=1, max_length=500)


class ResumeTool(ResumeModel):
    name: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class ResumeAchievement(ResumeModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=3000)
    source_reference: str = Field(min_length=1, max_length=500)


class ResumeClaim(ResumeModel):
    claim_text: str = Field(min_length=3, max_length=3000)
    claim_type: ResumeClaimType
    source: Literal["RESUME"]
    source_reference: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    verification_priority: VerificationPriority
    skill: str | None = Field(default=None, max_length=200)
    project_name: str | None = Field(default=None, max_length=300)
    metric_value: float | None = None
    metric_unit: str | None = Field(default=None, max_length=100)
    ownership_language: str | None = Field(default=None, max_length=500)
    outcome: str | None = Field(default=None, max_length=2000)
    tool: str | None = Field(default=None, max_length=200)


class ResumeAgentOutput(ResumeModel):
    skills: list[ResumeSkill] = Field(default_factory=list, max_length=300)
    projects: list[ResumeProject] = Field(default_factory=list, max_length=100)
    work_experience: list[ResumeWorkExperience] = Field(
        default_factory=list, max_length=100
    )
    education: list[ResumeEducation] = Field(default_factory=list, max_length=100)
    tools: list[ResumeTool] = Field(default_factory=list, max_length=300)
    achievements: list[ResumeAchievement] = Field(default_factory=list, max_length=100)
    claims: list[ResumeClaim] = Field(default_factory=list, max_length=1000)


class ResumeAnalysisRecord(ResumeModel):
    id: UUID
    document_id: UUID
    user_id: UUID
    version: int = Field(gt=0)
    status: ResumeAnalysisStatus
    output: ResumeAgentOutput | None = None
    model: str
    prompt_version: str
    analysis_version: str
    execution_id: UUID | None = None
    error_type: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ResumeClaimReview(ResumeClaim):
    id: UUID
    review_status: ClaimReviewStatus | None = None
    corrected_claim_text: str | None = None
    correction_version: int | None = None


class ResumeAnalysisResponse(ResumeAnalysisRecord):
    claims: list[ResumeClaimReview] = Field(default_factory=list)


class ClaimCorrectionCreate(ResumeModel):
    review_status: ClaimReviewStatus
    corrected_claim_text: str | None = Field(
        default=None, min_length=3, max_length=2000
    )

    @field_validator("corrected_claim_text")
    @classmethod
    def clean_correction(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None

    @model_validator(mode="after")
    def correction_matches_status(self) -> ClaimCorrectionCreate:
        if (
            self.review_status == ClaimReviewStatus.CORRECT
            and self.corrected_claim_text is not None
        ):
            raise ValueError("correct claims cannot include correction text")
        if (
            self.review_status == ClaimReviewStatus.NEEDS_CORRECTION
            and not self.corrected_claim_text
        ):
            raise ValueError("correction text is required")
        return self

