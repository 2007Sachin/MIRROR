from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .schemas import Phase


class PlannerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObjectivePriority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DifficultyStart(StrEnum):
    FOUNDATIONAL = "FOUNDATIONAL"
    BASIC = "BASIC"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class PlanningStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PlannerCandidateProfile(PlannerModel):
    career_stage: str | None = None
    career_intent: str | None = None
    interview_timeline: str | None = None
    preferred_language: str | None = None


class PlannerClaimSummary(PlannerModel):
    id: UUID
    claim_text: str = Field(min_length=3, max_length=3000)
    claim_type: str
    source: str
    confidence: float = Field(ge=0, le=1)
    verification_priority: str
    entity_names: list[str] = Field(default_factory=list, max_length=30)


class PlannerCompetencySummary(PlannerModel):
    id: UUID
    name: str = Field(min_length=2, max_length=300)
    category: str
    importance_weight: float = Field(ge=0, le=1)
    expected_level: str


class PlannerProjectSummary(PlannerModel):
    id: UUID
    name: str = Field(min_length=1, max_length=500)


class ExistingEvidenceSummary(PlannerModel):
    claim_id: UUID
    supports_count: int = Field(default=0, ge=0)
    weakens_count: int = Field(default=0, ge=0)
    context_only_count: int = Field(default=0, ge=0)


class InterviewPlannerInput(PlannerModel):
    session_id: UUID
    candidate_profile: PlannerCandidateProfile
    target_role: str = Field(min_length=2, max_length=160)
    career_stage: str | None = None
    interview_duration_seconds: int = Field(gt=0, le=14_400)
    claims_summary: list[PlannerClaimSummary] = Field(max_length=1000)
    role_competencies: list[PlannerCompetencySummary] = Field(
        min_length=1, max_length=100
    )
    projects: list[PlannerProjectSummary] = Field(default_factory=list, max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=300)
    high_verification_priority_claims: list[UUID] = Field(
        default_factory=list, max_length=1000
    )
    existing_evidence_summary: list[ExistingEvidenceSummary] = Field(
        default_factory=list, max_length=1000
    )


class InterviewObjective(PlannerModel):
    objective_id: str = Field(min_length=2, max_length=100)
    phase: Phase
    objective: str = Field(min_length=5, max_length=1000)
    priority: ObjectivePriority
    target_claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    target_competency_ids: list[UUID] = Field(default_factory=list, max_length=100)
    target_project_ids: list[UUID] = Field(default_factory=list, max_length=50)
    initial_question: str = Field(min_length=5, max_length=1000)
    question_intent: str = Field(min_length=5, max_length=1000)
    expected_signal: list[str] = Field(min_length=1, max_length=30)
    time_budget_seconds: int = Field(ge=30, le=1800)
    max_probes: int = Field(default=2, ge=0, le=10)
    difficulty_start: DifficultyStart
    completion_conditions: list[str] = Field(min_length=1, max_length=30)

    @field_validator("phase")
    @classmethod
    def phase_must_be_active(cls, value: Phase) -> Phase:
        if value == Phase.COMPLETE:
            raise ValueError("COMPLETE is controlled by the state machine")
        return value


class PlanCoverageSummary(PlannerModel):
    role_competency_coverage: list[UUID] = Field(default_factory=list, max_length=100)
    claims_targeted: list[UUID] = Field(default_factory=list, max_length=1000)
    projects_targeted: list[UUID] = Field(default_factory=list, max_length=100)
    uncovered_high_priority_items: list[str] = Field(
        default_factory=list, max_length=300
    )
    estimated_duration_seconds: int = Field(ge=0, le=14_400)


class InterviewPlanDraft(PlannerModel):
    session_id: UUID
    target_role: str = Field(min_length=2, max_length=160)
    total_time_budget_seconds: int = Field(gt=0, le=14_400)
    planning_version: str = Field(min_length=1, max_length=100)
    objectives: list[InterviewObjective] = Field(min_length=2, max_length=50)
    coverage_summary: PlanCoverageSummary

    @model_validator(mode="after")
    def unique_objectives(self) -> InterviewPlanDraft:
        ids = [objective.objective_id for objective in self.objectives]
        if len(ids) != len(set(ids)):
            raise ValueError("objective ids must be unique")
        return self


class InterviewPlan(InterviewPlanDraft):
    created_at: datetime


class PlanningContext(PlannerModel):
    resume_analysis_id: UUID
    role_analysis_id: UUID
    planner_input: InterviewPlannerInput


class InterviewPlanRecord(PlannerModel):
    id: UUID
    session_id: UUID
    user_id: UUID
    version: int = Field(gt=0)
    status: PlanningStatus
    plan: InterviewPlan | None = None
    planner_model: str
    prompt_version: str
    planning_version: str
    execution_id: UUID | None = None
    error_type: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    active: bool = False


class PlanSummary(PlannerModel):
    objective_count: int = Field(ge=0)
    estimated_duration_seconds: int = Field(ge=0)
    phases: list[Phase]


class PlanningResponse(PlannerModel):
    planning_status: PlanningStatus
    plan_id: UUID
    version: int
    summary: PlanSummary


class PublicInterviewPlan(PlannerModel):
    session_id: UUID
    target_role: str
    total_time_budget_seconds: int
    planning_version: str
    objectives: list[InterviewObjective]
    created_at: datetime


class InterviewPlanResponse(PlannerModel):
    id: UUID
    session_id: UUID
    version: int
    status: PlanningStatus
    plan: PublicInterviewPlan | None

