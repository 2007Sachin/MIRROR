from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RoleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompetencyCategory(StrEnum):
    TECHNICAL = "TECHNICAL"
    ANALYTICAL = "ANALYTICAL"
    DOMAIN = "DOMAIN"
    BEHAVIOURAL = "BEHAVIOURAL"
    COMMUNICATION = "COMMUNICATION"
    TOOL = "TOOL"


class ExpectedLevel(StrEnum):
    FOUNDATIONAL = "FOUNDATIONAL"
    BASIC = "BASIC"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class RoleSeniority(StrEnum):
    ENTRY_LEVEL = "ENTRY_LEVEL"
    JUNIOR = "JUNIOR"
    MID_LEVEL = "MID_LEVEL"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    UNSPECIFIED = "UNSPECIFIED"


class RoleSourceType(StrEnum):
    JOB_DESCRIPTION = "JOB_DESCRIPTION"
    SYNTHETIC_CANONICAL = "SYNTHETIC_CANONICAL"


class CompetencySourceType(StrEnum):
    JOB_DESCRIPTION_EXPLICIT = "JOB_DESCRIPTION_EXPLICIT"
    JOB_DESCRIPTION_INFERRED = "JOB_DESCRIPTION_INFERRED"
    SYNTHETIC_CANONICAL = "SYNTHETIC_CANONICAL"


class RoleAnalysisStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RoleAgentInput(RoleModel):
    target_role: str = Field(min_length=2, max_length=160)
    job_description_text: str | None = Field(default=None, max_length=100_000)
    career_stage: str | None = Field(default=None, max_length=100)

    @field_validator("target_role")
    @classmethod
    def clean_target_role(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("job_description_text")
    @classmethod
    def clean_job_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class RoleCompetency(RoleModel):
    name: str = Field(min_length=2, max_length=300)
    category: CompetencyCategory
    importance_weight: float = Field(ge=0, le=1)
    expected_level: ExpectedLevel
    source_type: CompetencySourceType
    source_reference: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class RoleAgentOutput(RoleModel):
    canonical_role: str = Field(min_length=2, max_length=300)
    seniority: RoleSeniority
    source_type: RoleSourceType
    competencies: list[RoleCompetency] = Field(min_length=1, max_length=100)
    must_have_skills: list[str] = Field(default_factory=list, max_length=100)
    nice_to_have_skills: list[str] = Field(default_factory=list, max_length=100)
    behavioural_expectations: list[str] = Field(default_factory=list, max_length=100)
    domain_expectations: list[str] = Field(default_factory=list, max_length=100)
    interview_themes: list[str] = Field(default_factory=list, max_length=100)


class RoleAnalyzeRequest(RoleModel):
    target_role: str = Field(min_length=2, max_length=160)
    job_description_text: str | None = Field(default=None, max_length=100_000)
    job_description_document_id: UUID | None = None
    role_profile_id: UUID | None = None

    @field_validator("target_role")
    @classmethod
    def clean_role(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("job_description_text")
    @classmethod
    def clean_jd(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def one_job_description_source(self) -> RoleAnalyzeRequest:
        if self.job_description_text and self.job_description_document_id:
            raise ValueError("provide job description text or a document id, not both")
        return self


class RoleAnalysisVersion(RoleModel):
    id: UUID
    role_profile_id: UUID
    user_id: UUID
    version: int = Field(gt=0)
    status: RoleAnalysisStatus
    source_type: RoleSourceType
    source_document_id: UUID | None = None
    model: str
    prompt_version: str
    analysis_version: str
    output: RoleAgentOutput | None = None
    execution_id: UUID | None = None
    error_type: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class RoleProfileRead(RoleModel):
    id: UUID
    user_id: UUID
    target_role: str
    canonical_role: str | None = None
    seniority: RoleSeniority | None = None
    source_type: RoleSourceType
    source_document_id: UUID | None = None
    current_analysis_version_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class StoredRoleCompetency(RoleCompetency):
    id: UUID
    role_profile_id: UUID
    analysis_version_id: UUID


class RoleAnalysisResponse(RoleProfileRead):
    latest_analysis: RoleAnalysisVersion | None = None
    competencies: list[StoredRoleCompetency] = Field(default_factory=list)

