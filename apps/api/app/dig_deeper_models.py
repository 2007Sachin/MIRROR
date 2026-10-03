from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class DigDeeperModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class DigDeeperResponseCreate(DigDeeperModel):
    role_profile_id: UUID
    claim_id: UUID
    question_kind: str = Field(min_length=2, max_length=60)
    question_text: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=6000)
    story_part: str = Field(min_length=2, max_length=60)

class DigDeeperResponseRead(DigDeeperResponseCreate):
    id: UUID
    user_id: UUID
    story_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

