from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssessmentPipelineStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AssessmentPipelineState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: UUID
    status: AssessmentPipelineStatus
    retry_count: int = Field(ge=0)
    failure_code: str | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AssessmentJob(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    session_id: UUID
    user_id: UUID
    attempts: int = Field(ge=1)
