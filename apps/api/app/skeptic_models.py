from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .claims_models import ClaimStatus, ClaimType
from .interviewer_models import InterviewerTurnType, TurnSpeaker
from .schemas import Phase


class SkepticModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObservationType(StrEnum):
    CONTRADICTION = "CONTRADICTION"
    VAGUENESS = "VAGUENESS"
    UNSUPPORTED_SCALE = "UNSUPPORTED_SCALE"
    OWNERSHIP_DRIFT = "OWNERSHIP_DRIFT"
    CLARIFICATION = "CLARIFICATION"
    ADDITIONAL_DETAIL = "ADDITIONAL_DETAIL"
    SCOPE_DIFFERENCE = "SCOPE_DIFFERENCE"
    TIMELINE_DIFFERENCE = "TIMELINE_DIFFERENCE"
    PARAPHRASE = "PARAPHRASE"
    CORROBORATION = "CORROBORATION"


class SkepticSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SkepticTurn(SkepticModel):
    id: UUID
    turn_index: int = Field(ge=0)
    speaker: TurnSpeaker
    text: str = Field(min_length=1, max_length=20_000)
    turn_type: InterviewerTurnType
    phase: Phase
    primary_thread_id: str | None = None
    created_at: datetime


class SkepticClaim(SkepticModel):
    id: UUID
    claim_text: str = Field(min_length=3, max_length=5000)
    claim_type: ClaimType
    source: str
    status: ClaimStatus
    source_reference: str | None = None
    confidence: float = Field(ge=0, le=1)
    related_entity_ids: list[UUID] = Field(default_factory=list, max_length=50)


class SkepticEntity(SkepticModel):
    id: UUID
    entity_type: str
    canonical_name: str = Field(min_length=1, max_length=500)


class SkepticRelation(SkepticModel):
    source_entity_type: str
    source_entity_id: UUID
    relation_type: str
    target_entity_type: str
    target_entity_id: UUID
    confidence: float = Field(ge=0, le=1)


class SkepticContext(SkepticModel):
    session_id: UUID
    current_turn: SkepticTurn
    related_resume_claims: list[SkepticClaim] = Field(default_factory=list, max_length=40)
    related_spoken_claims: list[SkepticClaim] = Field(default_factory=list, max_length=40)
    relevant_prior_turns: list[SkepticTurn] = Field(default_factory=list, max_length=8)
    current_project_context: list[SkepticEntity] = Field(default_factory=list, max_length=20)
    current_phase: Phase
    entities: list[SkepticEntity] = Field(default_factory=list, max_length=80)
    claim_relations: list[SkepticRelation] = Field(default_factory=list, max_length=160)


class SkepticRetrievalData(SkepticModel):
    session_id: UUID
    user_id: UUID
    current_turn: SkepticTurn
    prior_turns: list[SkepticTurn] = Field(default_factory=list)
    claims: list[SkepticClaim] = Field(default_factory=list)
    entities: list[SkepticEntity] = Field(default_factory=list)
    relations: list[SkepticRelation] = Field(default_factory=list)


class SkepticNewClaim(SkepticModel):
    claim_text: str = Field(min_length=3, max_length=5000)
    claim_type: ClaimType
    related_entity_ids: list[UUID] = Field(default_factory=list, max_length=50)
    source_turn_id: UUID
    confidence: float = Field(ge=0, le=1)


class SkepticClaimUpdate(SkepticModel):
    claim_id: UUID
    proposed_status: ClaimStatus
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=3, max_length=2000)
    related_turn_ids: list[UUID] = Field(min_length=1, max_length=20)


class SkepticObservation(SkepticModel):
    observation_type: ObservationType
    summary: str = Field(min_length=3, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    source_turn_id: UUID
    related_claim_ids: list[UUID] = Field(default_factory=list, max_length=20)
    related_turn_ids: list[UUID] = Field(default_factory=list, max_length=20)


class SkepticFlagProposal(SkepticModel):
    flag_type: ObservationType
    claim_id: UUID | None = None
    severity: SkepticSeverity
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=3, max_length=2000)
    suggested_probe: str = Field(min_length=3, max_length=1000)
    safe_to_surface: bool
    source_turn_id: UUID
    related_turn_ids: list[UUID] = Field(default_factory=list, max_length=20)


class SkepticAnalysis(SkepticModel):
    new_claims: list[SkepticNewClaim] = Field(default_factory=list, max_length=30)
    claim_updates: list[SkepticClaimUpdate] = Field(default_factory=list, max_length=30)
    observations: list[SkepticObservation] = Field(default_factory=list, max_length=50)
    flag_proposals: list[SkepticFlagProposal] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def no_duplicate_items(self) -> SkepticAnalysis:
        observation_keys = {
            (item.observation_type, item.summary.casefold(), item.source_turn_id)
            for item in self.observations
        }
        if len(observation_keys) != len(self.observations):
            raise ValueError("duplicate observations are not allowed")
        return self


class SkepticJob(SkepticModel):
    id: UUID
    session_id: UUID
    turn_id: UUID
    user_id: UUID
    attempts: int = Field(ge=1)


class SkepticProcessSummary(SkepticModel):
    flags_created: int = Field(ge=0)
    new_claims_created: int = Field(ge=0)
    claim_update_proposals_created: int = Field(ge=0)
    observations_created: int = Field(ge=0)


class StoredSkepticFlag(SkepticModel):
    id: UUID
    session_id: UUID
    claim_id: UUID | None = None
    flag_type: ObservationType
    severity: SkepticSeverity
    confidence: float = Field(ge=0, le=1)
    reason: str
    suggested_probe: str
    safe_to_surface: bool
    source_turn_id: UUID | None = None
    related_turn_ids: list[UUID] = Field(default_factory=list)
    detected_at_turn: int = Field(ge=0)
    consumed: bool
    shadow_mode: bool
    disputed: bool
    created_at: datetime
    resolved_at: datetime | None = None
    consumed_at_turn: int | None = Field(default=None, ge=0)
    consumed_at: datetime | None = None
    interviewer_turn_id: UUID | None = None


class StoredSkepticObservation(SkepticModel):
    id: UUID
    observation_type: ObservationType
    summary: str
    confidence: float = Field(ge=0, le=1)
    source_turn_id: UUID
    related_claim_ids: list[UUID] = Field(default_factory=list)
    related_turn_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime


class SkepticAdminTurnResult(SkepticModel):
    turn: SkepticTurn
    skeptic_execution_id: UUID | None = None
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    failure_type: str | None = None
    observations: list[StoredSkepticObservation] = Field(default_factory=list)
    flags: list[StoredSkepticFlag] = Field(default_factory=list)


class SkepticAdminSessionResult(SkepticModel):
    session_id: UUID
    shadow_mode: bool
    turns: list[SkepticAdminTurnResult] = Field(default_factory=list)

