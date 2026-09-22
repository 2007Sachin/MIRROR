"""My Stories: how a candidate explains a real experience in an interview.

A story is written by the candidate. Mirror may suggest prompts and pre-fill the
source statement it came from, but it never writes the situation, the actions or the
outcome itself. Experience (documents, resume analysis) stays the factual source;
a story only points at it.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StoryOrigin(StrEnum):
    MANUAL = "MANUAL"
    PRESSURE_TEST = "PRESSURE_TEST"
    FIND_A_STORY = "FIND_A_STORY"
    EXPERIENCE = "EXPERIENCE"


# The parts of a story, in the order an interviewer usually hears them.
STORY_PARTS: tuple[str, ...] = (
    "situation",
    "ownership",
    "actions",
    "reasoning",
    "outcome",
    "measurable_result",
    "learning",
)

# The parts without which a story does not hold up under a follow-up question.
CORE_PARTS: tuple[str, ...] = ("situation", "actions", "outcome")

_TEXT = Field(default=None, max_length=4000)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_themes(value: list[str]) -> list[str]:
    seen: list[str] = []
    for theme in value:
        cleaned = " ".join(theme.split())[:120]
        if cleaned and cleaned.casefold() not in {item.casefold() for item in seen}:
            seen.append(cleaned)
    return seen


class StoryFields(StoryModel):
    situation: str | None = _TEXT
    ownership: str | None = _TEXT
    actions: str | None = _TEXT
    reasoning: str | None = _TEXT
    trade_offs: str | None = _TEXT
    outcome: str | None = _TEXT
    measurable_result: str | None = _TEXT
    learning: str | None = _TEXT
    do_differently: str | None = _TEXT

    @field_validator(
        "situation", "ownership", "actions", "reasoning", "trade_offs",
        "outcome", "measurable_result", "learning", "do_differently",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _clean(value)


class StoryCreate(StoryFields):
    title: str = Field(min_length=2, max_length=200)
    themes: list[str] = Field(default_factory=list, max_length=12)
    role_profile_id: UUID | None = None
    source_claim_id: UUID | None = None
    source_document_id: UUID | None = None
    source_text: str | None = Field(default=None, max_length=3000)
    origin: StoryOrigin = StoryOrigin.MANUAL

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("themes")
    @classmethod
    def clean_themes(cls, value: list[str]) -> list[str]:
        return _clean_themes(value)


class StoryUpdate(StoryFields):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    themes: list[str] | None = Field(default=None, max_length=12)
    role_profile_id: UUID | None = None

    @field_validator("themes")
    @classmethod
    def clean_themes(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _clean_themes(value)


class StoryCompleteness(StrEnum):
    """How ready a story is to be told, from which parts the candidate has written."""

    READY = "READY"          # every core part, plus what you owned and why you chose it
    DEVELOPING = "DEVELOPING"  # every core part
    STARTED = "STARTED"      # something written, a core part missing


class StoryRead(StoryFields):
    id: UUID
    user_id: UUID
    title: str
    themes: list[str] = Field(default_factory=list)
    role_profile_id: UUID | None = None
    source_claim_id: UUID | None = None
    source_document_id: UUID | None = None
    source_text: str | None = None
    origin: StoryOrigin
    created_at: datetime
    updated_at: datetime


class StoryView(StoryRead):
    completeness: StoryCompleteness
    missing_parts: list[str] = Field(default_factory=list)


def story_completeness(story: StoryFields) -> tuple[StoryCompleteness, list[str]]:
    """Deterministic: which parts are written, never how good they are."""
    missing = [part for part in STORY_PARTS if not getattr(story, part)]
    core_missing = [part for part in CORE_PARTS if part in missing]
    if core_missing:
        return StoryCompleteness.STARTED, missing
    if story.reasoning and story.ownership:
        return StoryCompleteness.READY, missing
    return StoryCompleteness.DEVELOPING, missing


def story_view(story: StoryRead) -> StoryView:
    completeness, missing = story_completeness(story)
    return StoryView(**story.model_dump(), completeness=completeness, missing_parts=missing)
