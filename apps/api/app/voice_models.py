from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .interviewer_models import InterviewerTurnType, TurnSpeaker
from .schemas import Phase


class VoiceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AudioStatus(StrEnum):
    READY = "READY"
    FAILED = "FAILED"


class VoiceRequestStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SpeechToTextResult(VoiceModel):
    transcript: str = Field(max_length=50_000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    detected_language: str | None = Field(default=None, max_length=32)
    provider: str
    model: str
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)


class TextToSpeechResult(VoiceModel):
    audio_bytes: bytes = Field(min_length=1)
    mime_type: str
    provider: str
    model: str
    voice: str
    language: str
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)


class VoiceTurnResponse(VoiceModel):
    session_id: UUID
    turn_id: UUID
    question_text: str
    audio_url: str | None = None
    audio_status: AudioStatus
    turn_index: int = Field(ge=0)
    phase: Phase
    turn_type: InterviewerTurnType
    remaining_time_seconds: int = Field(ge=0)


class VoiceRequestRecord(VoiceModel):
    id: UUID
    session_id: UUID
    user_id: UUID
    client_turn_id: UUID
    status: VoiceRequestStatus
    candidate_audio_path: str | None = None
    candidate_audio_mime_type: str | None = None
    recorded_duration_ms: int | None = None
    candidate_turn_id: UUID | None = None
    interviewer_turn_id: UUID | None = None
    response_json: dict[str, Any] | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class VoiceRequestClaim(VoiceModel):
    request: VoiceRequestRecord
    claimed: bool


class TtsCacheRecord(VoiceModel):
    cache_key: str
    user_id: UUID
    session_id: UUID
    provider: str
    model: str
    voice: str
    language: str
    storage_path: str
    mime_type: str


class OwnedVoiceTurn(VoiceModel):
    id: UUID
    session_id: UUID
    user_id: UUID
    turn_index: int
    speaker: TurnSpeaker
    text: str
    turn_type: InterviewerTurnType
    phase: Phase
    audio_storage_path: str | None = None
    audio_mime_type: str | None = None
    audio_status: AudioStatus | None = None
    tts_provider: str | None = None
    tts_model: str | None = None


class VoiceLatencyMetrics(VoiceModel):
    session_id: UUID
    user_id: UUID
    turn_index: int | None = Field(default=None, ge=0)
    candidate_turn_id: UUID | None = None
    interviewer_turn_id: UUID | None = None
    audio_upload_ms: int = Field(default=0, ge=0)
    audio_processing_ms: int = Field(default=0, ge=0)
    stt_ms: int = Field(default=0, ge=0)
    context_build_ms: int = Field(default=0, ge=0)
    interviewer_ms: int = Field(default=0, ge=0)
    tts_ms: int = Field(default=0, ge=0)
    storage_ms: int = Field(default=0, ge=0)
    total_turn_ms: int = Field(default=0, ge=0)
    stt_provider: str | None = None
    stt_model: str | None = None
    tts_provider: str | None = None
    tts_model: str | None = None

