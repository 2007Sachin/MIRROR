from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .assessment_pipeline_models import AssessmentPipelineState
from .schemas import Phase, SessionStatus


class DashboardModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DashboardDiagnostic(DashboardModel):
    id: UUID
    target_role: str
    company: str | None = None
    interview_status: SessionStatus
    phase: Phase
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    assessment: AssessmentPipelineState | None = None
    diagnostic_available: bool = False


class DashboardResponse(DashboardModel):
    current: DashboardDiagnostic | None = None
    previous: list[DashboardDiagnostic] = Field(default_factory=list)
