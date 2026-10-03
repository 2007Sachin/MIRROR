"""Interview events and debriefs (see docs/architecture/INTERVIEW_EVENTS_CONTRACT.md).

A debrief is what the person reports. Nothing here judges it or explains an outcome.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .interview_map import Coverage, MapState
from .pressure_test import Readiness

MAX_QUESTIONS_ASKED = 15
MAX_QUESTION_CHARS = 500


class EventModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoundKind(StrEnum):
    SCREENING = "SCREENING"
    TECHNICAL = "TECHNICAL"
    BEHAVIOURAL = "BEHAVIOURAL"
    HR = "HR"
    OTHER = "OTHER"


class Feeling(StrEnum):
    WENT_WELL = "WENT_WELL"
    MIXED = "MIXED"
    WENT_BADLY = "WENT_BADLY"


class Outcome(StrEnum):
    WAITING = "WAITING"
    NEXT_ROUND = "NEXT_ROUND"
    OFFER = "OFFER"
    NOT_SELECTED = "NOT_SELECTED"
    WITHDREW = "WITHDREW"


class Timing(StrEnum):
    UPCOMING = "UPCOMING"
    SOON = "SOON"
    PAST = "PAST"


class FollowUpAction(StrEnum):
    ADD_STORY = "ADD_STORY"
    STRENGTHEN_STORY = "STRENGTHEN_STORY"
    NONE = "NONE"


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("scheduled_for must include a timezone")
    return value


def _label(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    if len(value) > 120:
        raise ValueError("company_label must be at most 120 characters")
    return value or None


class InterviewEventCreate(EventModel):
    scheduled_for: datetime
    round_kind: RoundKind = RoundKind.OTHER
    company_label: str | None = None

    _check_time = field_validator("scheduled_for")(_aware)
    _check_label = field_validator("company_label")(_label)


class InterviewEventUpdate(EventModel):
    scheduled_for: datetime | None = None
    round_kind: RoundKind | None = None
    company_label: str | None = None

    _check_time = field_validator("scheduled_for")(_aware)
    _check_label = field_validator("company_label")(_label)


class InterviewEventRecord(EventModel):
    """A stored event as the repository returns it."""

    id: UUID
    user_id: UUID
    role_profile_id: UUID
    scheduled_for: datetime
    round_kind: RoundKind
    company_label: str | None = None
    has_debrief: bool = False
    created_at: datetime
    updated_at: datetime


class InterviewEvent(EventModel):
    id: UUID
    role_profile_id: UUID
    scheduled_for: datetime
    round_kind: RoundKind
    company_label: str | None = None
    has_debrief: bool
    timing: Timing
    created_at: datetime
    updated_at: datetime


class BriefTheme(EventModel):
    key: str
    label: str
    coverage: Coverage
    support: str | None = None
    story_id: UUID | None = None
    prompt: str


class BriefClaim(EventModel):
    claim_id: UUID
    statement: str
    readiness: Readiness | None = None
    question: str


class BriefFocus(EventModel):
    title: str
    body: str
    session_id: UUID | None = None


class InterviewBrief(EventModel):
    event: InterviewEvent
    role_title: str
    state: MapState
    themes: list[BriefTheme] = Field(default_factory=list)
    recheck: list[BriefClaim] = Field(default_factory=list)
    focus: BriefFocus | None = None
    questions_to_ask: list[str]
    limitations: list[str]


class InterviewDebriefWrite(EventModel):
    questions_asked: list[str] = Field(default_factory=list, max_length=100)  # raw cap before dedupe
    feeling: Feeling | None = None
    outcome: Outcome = Outcome.WAITING
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("questions_asked")
    @classmethod
    def _questions(cls, value: list[str]) -> list[str]:
        kept: list[str] = []
        seen: set[str] = set()
        for raw in value:
            text = raw.strip()
            if not text:
                continue
            if len(text) > MAX_QUESTION_CHARS:
                raise ValueError(f"each question must be at most {MAX_QUESTION_CHARS} characters")
            if text.casefold() in seen:
                continue
            seen.add(text.casefold())
            kept.append(text)
        if len(kept) > MAX_QUESTIONS_ASKED:
            raise ValueError(f"at most {MAX_QUESTIONS_ASKED} questions")
        return kept

    @field_validator("notes")
    @classmethod
    def _notes(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class InterviewDebrief(EventModel):
    id: UUID
    interview_event_id: UUID
    questions_asked: list[str]
    feeling: Feeling | None = None
    outcome: Outcome
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class DebriefFollowUp(EventModel):
    question: str
    theme_key: str | None = None
    theme_label: str | None = None
    coverage: Coverage | None = None
    action: FollowUpAction
    action_href: str | None = None


class InterviewDebriefView(EventModel):
    debrief: InterviewDebrief
    follow_ups: list[DebriefFollowUp]

