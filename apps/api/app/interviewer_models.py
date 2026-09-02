from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .planner_models import DifficultyStart, ObjectivePriority
from .schemas import Phase


class InterviewerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterviewerAction(StrEnum):
    ASK = "ASK"
    TRANSITION = "TRANSITION"
    RECOVERY = "RECOVERY"
    CLOSE = "CLOSE"


class InterviewerTurnType(StrEnum):
    PLANNED = "PLANNED"
    DEPTH_PROBE = "DEPTH_PROBE"
    CONTRADICTION_PROBE = "CONTRADICTION_PROBE"
    LADDER_UP = "LADDER_UP"
    LADDER_DOWN = "LADDER_DOWN"
    RECOVERY = "RECOVERY"
    TRANSITION = "TRANSITION"
    CLOSING = "CLOSING"


class InterviewerReasonCode(StrEnum):
    START_OBJECTIVE = "START_OBJECTIVE"
    NEED_MORE_DEPTH = "NEED_MORE_DEPTH"
    STRONG_SIGNAL_LADDER_UP = "STRONG_SIGNAL_LADDER_UP"
    WEAK_SIGNAL_MOVE_ON = "WEAK_SIGNAL_MOVE_ON"
    OBJECTIVE_COMPLETE = "OBJECTIVE_COMPLETE"
    TIME_LIMIT = "TIME_LIMIT"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    PHASE_COMPLETE = "PHASE_COMPLETE"
    SESSION_COMPLETE = "SESSION_COMPLETE"
    SKEPTIC_FLAG_PROBE = "SKEPTIC_FLAG_PROBE"


class TurnSpeaker(StrEnum):
    CANDIDATE = "CANDIDATE"
    INTERVIEWER = "INTERVIEWER"


class RecentInterviewTurn(InterviewerModel):
    turn_index: int = Field(ge=0)
    speaker: TurnSpeaker
    text: str = Field(min_length=1, max_length=20_000)
    turn_type: InterviewerTurnType
    phase: Phase


class RelevantClaim(InterviewerModel):
    id: UUID
    claim_text: str = Field(min_length=3, max_length=3000)
    claim_type: str
    source: str
    status: str


class RelevantCompetency(InterviewerModel):
    id: UUID
    name: str = Field(min_length=2, max_length=300)
    category: str
    expected_level: str


class PendingInterviewerFlag(InterviewerModel):
    flag_id: UUID
    flag_type: str
    claim_summary: str | None = Field(default=None, max_length=500)
    reason_summary: str = Field(min_length=3, max_length=1000)
    suggested_probe: str = Field(min_length=3, max_length=1000)
    recommended_turn_type: InterviewerTurnType
    confidence_band: str


class InterviewerObjective(InterviewerModel):
    """Planner objective fields that are necessary to conduct, not assess."""

    objective_id: str
    phase: Phase
    objective: str
    priority: ObjectivePriority
    target_claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    target_competency_ids: list[UUID] = Field(default_factory=list, max_length=100)
    target_project_ids: list[UUID] = Field(default_factory=list, max_length=50)
    initial_question: str
    question_intent: str
    time_budget_seconds: int = Field(ge=30, le=1800)
    max_probes: int = Field(ge=0, le=10)
    difficulty_start: DifficultyStart


class InterviewerContext(InterviewerModel):
    session_id: UUID
    current_turn_index: int = Field(ge=0)
    phase: Phase
    objective: InterviewerObjective
    recent_turns: list[RecentInterviewTurn] = Field(max_length=6)
    relevant_claims: list[RelevantClaim] = Field(default_factory=list, max_length=100)
    relevant_competencies: list[RelevantCompetency] = Field(
        default_factory=list, max_length=100
    )
    primary_thread_id: str | None = None
    probe_count: int = Field(ge=0, le=2)
    remaining_phase_time_seconds: int = Field(ge=0)
    remaining_time_seconds: int = Field(ge=0)
    pending_flag: PendingInterviewerFlag | None = None


class InterviewerDecision(InterviewerModel):
    action: InterviewerAction
    question_text: str = Field(min_length=3, max_length=1000)
    turn_type: InterviewerTurnType
    target_claim_ids: list[UUID] = Field(default_factory=list, max_length=100)
    target_competency_ids: list[UUID] = Field(default_factory=list, max_length=100)
    primary_thread_id: str = Field(min_length=2, max_length=100)
    reason_code: InterviewerReasonCode
    requested_phase_transition: Phase | None = None
    used_flag_id: UUID | None = None

    @model_validator(mode="after")
    def action_matches_turn_type(self) -> InterviewerDecision:
        permitted = {
            InterviewerAction.ASK: {
                InterviewerTurnType.PLANNED,
                InterviewerTurnType.DEPTH_PROBE,
                InterviewerTurnType.CONTRADICTION_PROBE,
                InterviewerTurnType.LADDER_UP,
                InterviewerTurnType.LADDER_DOWN,
            },
            InterviewerAction.TRANSITION: {InterviewerTurnType.TRANSITION},
            InterviewerAction.RECOVERY: {InterviewerTurnType.RECOVERY},
            InterviewerAction.CLOSE: {InterviewerTurnType.CLOSING},
        }
        if self.turn_type not in permitted[self.action]:
            raise ValueError("action and turn type do not match")
        if self.action != InterviewerAction.TRANSITION and self.requested_phase_transition:
            raise ValueError("only transition actions may request a phase")
        if self.requested_phase_transition == Phase.COMPLETE:
            raise ValueError("the state machine controls completion")
        return self


class TextTurnRequest(InterviewerModel):
    text: str = Field(min_length=1, max_length=20_000)
    client_turn_id: UUID = Field(default_factory=uuid4)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("candidate response must not be blank")
        return cleaned


class StoredInterviewTurn(InterviewerModel):
    id: UUID
    session_id: UUID
    turn_index: int
    speaker: TurnSpeaker
    text: str
    turn_type: InterviewerTurnType
    phase: Phase
    primary_thread_id: str | None = None
    response_to_turn_id: UUID | None = None
    client_turn_id: UUID | None = None
    agent_execution_id: UUID | None = None
    model: str | None = None
    prompt_version: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    retry_count: int | None = Field(default=None, ge=0)
    target_claim_ids: list[UUID] = Field(default_factory=list)
    target_competency_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime


class PublicTurn(InterviewerModel):
    id: UUID
    session_id: UUID
    turn_index: int
    speaker: TurnSpeaker
    text: str
    turn_type: InterviewerTurnType
    phase: Phase
    created_at: datetime


class TextTurnResponse(InterviewerModel):
    session_id: UUID
    candidate_turn_index: int
    interviewer_turn_index: int
    question_text: str
    phase: Phase
    turn_type: InterviewerTurnType
    remaining_time_seconds: int = Field(ge=0)


class InterviewStartResponse(InterviewerModel):
    session_id: UUID
    interviewer_turn_index: int
    question_text: str
    phase: Phase
    turn_type: InterviewerTurnType
    remaining_time_seconds: int = Field(ge=0)

