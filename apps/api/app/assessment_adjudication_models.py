from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .specialist_assessor_models import SpecialistAssessmentBundle


class AdjudicationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessmentDisagreement(AdjudicationModel):
    affected_dimension: str = Field(min_length=2, max_length=200)
    specialist_positions: dict[str, str] = Field(min_length=2)
    reason: str = Field(min_length=3, max_length=1500)


class AdjudicationContext(AdjudicationModel):
    session_id: UUID
    disagreement: AssessmentDisagreement
    specialist_bundle: SpecialistAssessmentBundle
    rubric: list[dict[str, str]] = Field(default_factory=list)
    validated_evidence: list[dict[str, str | float | None]] = Field(default_factory=list)
    claims_state: list[dict[str, str | float | None]] = Field(default_factory=list)


class AdjudicationDecision(AdjudicationModel):
    affected_dimension: str = Field(min_length=2, max_length=200)
    final_position: str = Field(min_length=3, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    reason_summary: str = Field(min_length=3, max_length=2000)
    specialist_positions: dict[str, str] = Field(min_length=2)


class StoredAdjudication(AdjudicationModel):
    id: UUID
    session_id: UUID
    affected_dimension: str
    specialist_inputs: dict
    final_decision: AdjudicationDecision
    confidence: float
    model: str
    prompt_version: str
    created_at: datetime

