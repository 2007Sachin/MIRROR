from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileRead(ApiModel):
    id: UUID
    full_name: str | None = None
    email: str


class ProfileUpdate(ApiModel):
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("full_name")
    @classmethod
    def normalise_full_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("full_name must not be blank")
        return cleaned


class CareerStage(StrEnum):
    STUDENT = "STUDENT"
    FINAL_YEAR_STUDENT = "FINAL_YEAR_STUDENT"
    FRESHER = "FRESHER"
    EARLY_CAREER = "EARLY_CAREER"
    EXPERIENCED = "EXPERIENCED"


class CareerIntent(StrEnum):
    CAMPUS_PLACEMENT = "CAMPUS_PLACEMENT"
    INTERNSHIP = "INTERNSHIP"
    FIRST_JOB = "FIRST_JOB"
    JOB_SWITCH = "JOB_SWITCH"
    SPECIFIC_COMPANY = "SPECIFIC_COMPANY"
    EXPLORING = "EXPLORING"


class InterviewTimeline(StrEnum):
    TODAY = "TODAY"
    THIS_WEEK = "THIS_WEEK"
    THIS_MONTH = "THIS_MONTH"
    LATER = "LATER"
    EXPLORING = "EXPLORING"


class PreferredLanguage(StrEnum):
    ENGLISH = "ENGLISH"
    HINDI = "HINDI"
    KANNADA = "KANNADA"
    TAMIL = "TAMIL"
    TELUGU = "TELUGU"


class InquiryDepth(StrEnum):
    EVIDENCE_BEHIND_CLAIMS = "EVIDENCE_BEHIND_CLAIMS"
    ROLE_KNOWLEDGE = "ROLE_KNOWLEDGE"
    DECISION_QUALITY = "DECISION_QUALITY"
    OWNERSHIP_IMPACT = "OWNERSHIP_IMPACT"
    COMMUNICATION_UNDER_SCRUTINY = "COMMUNICATION_UNDER_SCRUTINY"
    COMPLETE_READINESS = "COMPLETE_READINESS"


class DocumentType(StrEnum):
    RESUME = "RESUME"
    JOB_DESCRIPTION = "JOB_DESCRIPTION"
    PROJECT = "PROJECT"


class EvidenceCategory(StrEnum):
    RESUME = "RESUME"
    PROJECT = "PROJECT"
    CASE_STUDY = "CASE_STUDY"
    CERTIFICATE = "CERTIFICATE"
    PORTFOLIO = "PORTFOLIO"
    COVER_LETTER = "COVER_LETTER"
    ACHIEVEMENT = "ACHIEVEMENT"
    WORK_SAMPLE = "WORK_SAMPLE"
    ROLE_BRIEF = "ROLE_BRIEF"
    OTHER = "OTHER"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class DocumentRead(ApiModel):
    id: UUID
    user_id: UUID
    document_type: DocumentType
    storage_path: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    raw_text: str | None = None
    status: DocumentStatus
    error_message: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    title: str | None = None
    evidence_category: EvidenceCategory | None = None
    context_note: str | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None
    version_number: int = Field(default=1, ge=1)
    supersedes_document_id: UUID | None = None


class EvidenceMetadataUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    evidence_category: EvidenceCategory | None = None
    context_note: str | None = Field(default=None, max_length=4_000)
    acknowledge_active_use: bool = False

    @field_validator("title")
    @classmethod
    def normalise_evidence_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("evidence title must not be blank")
        return cleaned

    @field_validator("context_note")
    @classmethod
    def normalise_evidence_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def require_evidence_change(self) -> EvidenceMetadataUpdate:
        if not ({"title", "evidence_category", "context_note"} & self.model_fields_set):
            raise ValueError("at least one evidence field is required")
        return self


class EvidenceArchiveRequest(ApiModel):
    acknowledge_active_use: bool = False


class EvidenceDiagnosticReference(ApiModel):
    session_id: UUID
    target_role: str
    status: Literal[
        "CREATED",
        "PREPARING",
        "READY",
        "ACTIVE",
        "ASSESSING",
        "COMPLETED",
        "FAILED",
    ]
    linked_at: datetime
    completed_at: datetime | None = None


class EvidenceUsage(ApiModel):
    active_diagnostic_count: int = Field(ge=0)
    completed_diagnostic_count: int = Field(ge=0)
    diagnostics: list[EvidenceDiagnosticReference] = Field(default_factory=list)


class EvidenceDetail(ApiModel):
    document: DocumentRead
    usage: EvidenceUsage


class JobDescriptionCreate(ApiModel):
    raw_text: str = Field(min_length=1, max_length=100_000)

    @field_validator("raw_text")
    @classmethod
    def normalise_raw_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("job description must not be blank")
        return cleaned


class SessionDocumentsLink(ApiModel):
    document_ids: list[UUID] = Field(min_length=1, max_length=5)

    @field_validator("document_ids")
    @classmethod
    def unique_document_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("document_ids must be unique")
        return value


class OnboardingRead(ApiModel):
    career_stage: CareerStage | None = None
    career_intent: CareerIntent | None = None
    target_role: str | None = None
    interview_timeline: InterviewTimeline | None = None
    preferred_language: PreferredLanguage | None = None
    college_id: UUID | None = None
    target_company: str | None = None
    onboarding_step: int = Field(default=1, ge=1, le=5)
    onboarding_resume_document_id: UUID | None = None
    onboarding_role_brief_document_id: UUID | None = None
    onboarding_role_brief_skipped: bool = False
    onboarding_role_profile_id: UUID | None = None
    onboarding_session_id: UUID | None = None
    inquiry_depth: list[InquiryDepth] = Field(
        default_factory=lambda: [InquiryDepth.COMPLETE_READINESS],
        min_length=1,
        max_length=5,
    )
    onboarding_completed: bool = False


class OnboardingUpdate(ApiModel):
    career_stage: CareerStage | None = None
    career_intent: CareerIntent | None = None
    target_role: str | None = Field(default=None, min_length=2, max_length=160)
    interview_timeline: InterviewTimeline | None = None
    preferred_language: PreferredLanguage | None = None
    college_id: UUID | None = None
    target_company: str | None = Field(default=None, max_length=160)
    onboarding_step: int | None = Field(default=None, ge=1, le=5)
    onboarding_resume_document_id: UUID | None = None
    onboarding_role_brief_document_id: UUID | None = None
    onboarding_role_brief_skipped: bool | None = None
    onboarding_role_profile_id: UUID | None = None
    onboarding_session_id: UUID | None = None
    inquiry_depth: list[InquiryDepth] | None = Field(
        default=None, min_length=1, max_length=5
    )
    onboarding_completed: bool | None = None

    @field_validator("target_role")
    @classmethod
    def normalise_target_role(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("target_role must contain at least two characters")
        return cleaned

    @field_validator("target_company")
    @classmethod
    def normalise_target_company(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("inquiry_depth")
    @classmethod
    def validate_inquiry_depth(
        cls, value: list[InquiryDepth] | None
    ) -> list[InquiryDepth] | None:
        if value is None:
            return None
        if len(value) != len(set(value)):
            raise ValueError("inquiry_depth values must be unique")
        if InquiryDepth.COMPLETE_READINESS in value and len(value) != 1:
            raise ValueError("complete readiness cannot be combined with another depth")
        return value

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> OnboardingUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one onboarding field is required")
        return self


def onboarding_is_complete(onboarding: OnboardingRead) -> bool:
    legacy_complete = all(
        (
            onboarding.career_stage,
            onboarding.career_intent,
            onboarding.target_role,
            onboarding.interview_timeline,
            onboarding.preferred_language,
        )
    )
    diagnostic_complete = all(
        (
            onboarding.target_role,
            onboarding.onboarding_step == 5,
            onboarding.onboarding_resume_document_id,
            onboarding.onboarding_role_profile_id,
            onboarding.onboarding_session_id,
            onboarding.inquiry_depth,
        )
    )
    return bool(legacy_complete or diagnostic_complete)


class Phase(StrEnum):
    INTRO = "INTRO"
    BACKGROUND = "BACKGROUND"
    PROJECTS = "PROJECTS"
    ROLE_CORE = "ROLE_CORE"
    DEEP_DIVE = "DEEP_DIVE"
    BEHAVIOURAL = "BEHAVIOURAL"
    CLOSING = "CLOSING"
    COMPLETE = "COMPLETE"


class TurnType(StrEnum):
    PLANNED = "planned"
    DEPTH_PROBE = "depth_probe"
    CONTRADICTION_PROBE = "contradiction_probe"
    LADDER_UP = "ladder_up"
    LADDER_DOWN = "ladder_down"
    RECOVERY = "recovery"
    TRANSITION = "transition"
    CLOSING = "closing"


class SessionStatus(StrEnum):
    CREATED = "CREATED"
    PREPARING = "PREPARING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    ASSESSING = "ASSESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Question(ApiModel):
    id: str
    skill_id: UUID | None = None
    canonical_question: str = Field(min_length=3)
    reason: str = Field(min_length=3)
    expected_duration_seconds: int = Field(default=90, ge=15, le=300)
    max_probes: int = Field(default=2, ge=0, le=2)


class QuestionPhase(ApiModel):
    phase: Phase
    questions: list[Question]


class QuestionPlan(ApiModel):
    role: str
    phases: list[QuestionPhase]


class SessionCreate(ApiModel):
    target_role: str = Field(min_length=2, max_length=160)
    jd_text: str = Field(default="", max_length=80_000)


class SessionRead(ApiModel):
    id: UUID
    user_id: UUID
    target_role: str
    resume_url: str | None = None
    jd_text: str
    status: SessionStatus
    phase: Phase
    question_plan: QuestionPlan | None = None
    completion_pct: float
    synthetic: bool
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    phase_started_at: datetime
    phase_time_budget_seconds: int = Field(gt=0)
    total_time_budget_seconds: int = Field(gt=0)
    elapsed_seconds: int = Field(ge=0)
    current_primary_question_id: str | None = None
    current_probe_count: int = Field(ge=0, le=2)
    total_questions: int = Field(ge=0)
    recovery_count: int = Field(ge=0)


class SessionEventRead(ApiModel):
    id: UUID
    session_id: UUID
    user_id: UUID
    event_type: str
    payload: dict
    created_at: datetime


class SessionPatch(ApiModel):
    jd_text: str = Field(max_length=80_000)


class PrepareResponse(ApiModel):
    session: SessionRead
    claims_extracted: int
    competencies_derived: int


class TurnResponse(ApiModel):
    question_text: str
    audio_url: str | None
    turn_index: int
    phase: Phase
    turn_type: TurnType


class ClaimType(StrEnum):
    SKILL = "skill"
    PROJECT = "project"
    SCALE = "scale"
    OWNERSHIP = "ownership"
    TOOL = "tool"
    OUTCOME = "outcome"
    EXPERIENCE = "experience"
    RESPONSIBILITY = "responsibility"


class ClaimStatus(StrEnum):
    UNVERIFIED = "unverified"
    CORROBORATED = "corroborated"
    CONTRADICTED = "contradicted"
    WALKED_BACK = "walked_back"


class NewClaim(ApiModel):
    claim_text: str = Field(min_length=3)
    claim_type: ClaimType
    confidence: float = Field(ge=0, le=1)


class ClaimUpdate(ApiModel):
    claim_id: UUID
    new_status: ClaimStatus
    confidence: float = Field(ge=0, le=1)


class FlagType(StrEnum):
    CONTRADICTION = "contradiction"
    VAGUENESS = "vagueness"
    UNSUPPORTED_SCALE = "unsupported_scale"
    OWNERSHIP_DRIFT = "ownership_drift"


class SkepticFlag(ApiModel):
    claim_id: UUID | None = None
    flag_type: FlagType
    severity: int = Field(ge=1, le=3)
    suggested_probe: str = Field(min_length=5)
    confidence: float = Field(ge=0, le=1)
    distinction: Literal[
        "contradiction",
        "clarification",
        "additional_detail",
        "different_scope",
        "team_vs_personal",
        "timeline_difference",
        "different_environment",
        "paraphrase",
    ]


class SkepticOutput(ApiModel):
    new_claims: list[NewClaim] = Field(default_factory=list)
    claim_updates: list[ClaimUpdate] = Field(default_factory=list)
    flags: list[SkepticFlag] = Field(default_factory=list)


class EvidenceScore(ApiModel):
    question_index: int = Field(ge=0)
    skill: str
    skill_id: UUID | None = None
    status: Literal["scored", "not_enough_signal"]
    clarity: float | None = Field(default=None, ge=0, le=100)
    depth: float | None = Field(default=None, ge=0, le=100)
    relevance: float | None = Field(default=None, ge=0, le=100)
    communication: float | None = Field(default=None, ge=0, le=100)
    composite: float | None = Field(default=None, ge=0, le=100)
    evidence_quotes: list[str] = Field(default_factory=list)
    evidence_turn_ids: list[UUID] = Field(default_factory=list)
    signal_strength: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_evidence_for_score(self) -> EvidenceScore:
        if self.status == "scored":
            numeric = [
                self.clarity,
                self.depth,
                self.relevance,
                self.communication,
                self.composite,
            ]
            if any(value is None for value in numeric):
                raise ValueError("scored rows require every numeric dimension")
            if not self.evidence_quotes or not self.evidence_turn_ids:
                raise ValueError("scored rows require candidate evidence and turn ids")
        elif any(
            value is not None
            for value in [
                self.clarity,
                self.depth,
                self.relevance,
                self.communication,
                self.composite,
            ]
        ):
            raise ValueError("not_enough_signal rows must not contain numeric scores")
        return self


class ReadinessRange(ApiModel):
    low: float = Field(ge=0, le=100)
    high: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def ordered(self) -> ReadinessRange:
        if self.low > self.high:
            raise ValueError("low must not exceed high")
        return self


class ReplayMarker(ApiModel):
    turn_id: UUID
    timecode_ms: int = Field(ge=0)
    label: str
    kind: Literal["strength", "recovery", "contradiction", "evidence"]


class AssessorOutput(ApiModel):
    question_scores: list[EvidenceScore]
    role_readiness: ReadinessRange | None
    interview_readiness: ReadinessRange | None
    verdict: Literal[
        "Not Ready Yet", "Developing", "Stable", "Strong", "Not enough signal"
    ]
    root_cause: str
    prescribed_fix: str
    replay_markers: list[ReplayMarker] = Field(default_factory=list)
    confidence_note: str
    model_provider: str
    model_name: str
    model_version: str
    prompt_version: str
    rubric_version: str


class DisputeCreate(ApiModel):
    reason: Literal[
        "Mirror misunderstood my answer",
        "Resume wording was ambiguous",
        "Audio/transcription error",
        "Important context was missing",
        "Other",
    ]
    comment: str = Field(default="", max_length=2_000)


TurnDuration = Annotated[int, Field(ge=0, le=600_000)]


class JobType(StrEnum):
    SKEPTIC_TURN = "skeptic_turn"
    GENERATE_REPORT = "generate_report"
    GENERATE_TTS = "generate_tts"
    PROCESS_RESUME = "process_resume"
    GENERATE_QUESTION_PLAN = "generate_question_plan"


class JobPayload(ApiModel):
    session_id: UUID
    turn_id: UUID | None = None
    requested_by: UUID | None = None
    prompt_version: str | None = None


class JobCreate(ApiModel):
    job_type: JobType
    payload: JobPayload
    run_after: datetime | None = None


class TurnRequestMetadata(ApiModel):
    duration_ms: TurnDuration
    silence_before_ms: int = Field(default=0, ge=0, le=60_000)
    client_turn_id: UUID
    content_type: Literal["audio/webm", "audio/ogg", "audio/mp4", "audio/wav"]

