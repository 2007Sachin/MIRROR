"""Try again: answering the same question again, and seeing what is different.

The comparison is deliberately narrow. For a fixed set of aspects, it records only
whether each answer contains that aspect (PRESENT or ABSENT). Everything the candidate
sees about "what changed" is derived from those pairs, so no improvement can be claimed
without an observable difference behind it. Free text is limited to a one-sentence
summary and one suggestion, both screened for banned words, and never a number.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AttemptModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Aspect(StrEnum):
    """What an interview answer can contain. Order is the order people hear it."""

    SITUATION = "SITUATION"
    OWNERSHIP = "OWNERSHIP"
    ACTIONS = "ACTIONS"
    REASONING = "REASONING"
    RESULT = "RESULT"
    MEASURE = "MEASURE"
    SPECIFIC_EXAMPLE = "SPECIFIC_EXAMPLE"


class Presence(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class ComparisonSource(StrEnum):
    MODEL = "MODEL"    # the retry-comparison agent
    CHECKS = "CHECKS"  # the deterministic presence checks, used when the agent is unavailable


class AspectChange(AttemptModel):
    aspect: Aspect
    first: Presence
    latest: Presence


# ------------------------------------------------------------------ agent contract


class RetryComparisonInput(AttemptModel):
    question: str = Field(min_length=3, max_length=2000)
    first_answer: str = Field(min_length=1, max_length=6000)
    latest_answer: str = Field(min_length=1, max_length=6000)
    target_role: str | None = Field(default=None, max_length=160)
    practising: str | None = Field(default=None, max_length=300)
    aspects: list[Aspect] = Field(default_factory=lambda: list(Aspect), min_length=1)


class RetryComparisonOutput(AttemptModel):
    changes: list[AspectChange] = Field(min_length=1, max_length=len(Aspect))
    summary: str = Field(min_length=3, max_length=280)
    next_suggestion: str = Field(min_length=3, max_length=240)

    @field_validator("summary", "next_suggestion")
    @classmethod
    def no_numbers_as_grades(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        # A comparison may quote nothing numeric of its own: no scores, no percentages.
        if any(char.isdigit() for char in cleaned) or "%" in cleaned:
            raise ValueError("comparison text must not contain numbers")
        return cleaned

    @model_validator(mode="after")
    def one_entry_per_aspect(self) -> RetryComparisonOutput:
        aspects = [change.aspect for change in self.changes]
        if len(aspects) != len(set(aspects)):
            raise ValueError("each aspect may appear once")
        return self


# ------------------------------------------------------------------ stored and shown


class AttemptComparison(AttemptModel):
    source: ComparisonSource
    changes: list[AspectChange]
    summary: str
    next_suggestion: str


class AttemptComparisonView(AttemptComparison):
    came_through_more_clearly: list[Aspect] = Field(default_factory=list)
    still_missing: list[Aspect] = Field(default_factory=list)
    first_present: list[Aspect] = Field(default_factory=list)
    latest_present: list[Aspect] = Field(default_factory=list)


def comparison_view(comparison: AttemptComparison) -> AttemptComparisonView:
    changes = comparison.changes
    return AttemptComparisonView(
        source=comparison.source,
        changes=changes,
        summary=comparison.summary,
        next_suggestion=comparison.next_suggestion,
        came_through_more_clearly=[c.aspect for c in changes if c.first == Presence.ABSENT and c.latest == Presence.PRESENT],
        still_missing=[c.aspect for c in changes if c.latest == Presence.ABSENT],
        first_present=[c.aspect for c in changes if c.first == Presence.PRESENT],
        latest_present=[c.aspect for c in changes if c.latest == Presence.PRESENT],
    )


class AttemptCreate(AttemptModel):
    answer: str = Field(min_length=1, max_length=6000)
    area_key: str | None = Field(default=None, max_length=80)
    area_title: str | None = Field(default=None, max_length=200)
    idempotency_key: UUID | None = None

    @field_validator("answer")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("an answer is required")
        return value.strip()


class AttemptRecord(AttemptModel):
    id: UUID
    user_id: UUID
    session_id: UUID
    question_turn_id: UUID
    original_turn_id: UUID
    sequence: int = Field(ge=1)
    question_text: str
    original_answer: str
    answer_text: str
    area_key: str | None = None
    area_title: str | None = None
    role_profile_id: UUID | None = None
    idempotency_key: UUID | None = None
    comparison: AttemptComparison | None = None
    comparison_source: ComparisonSource | None = None
    model: str | None = None
    prompt_version: str | None = None
    created_at: datetime


class AttemptView(AttemptModel):
    """What the candidate sees. Model and prompt metadata stay on the server."""

    id: UUID
    session_id: UUID
    question_turn_id: UUID
    original_turn_id: UUID
    sequence: int
    question_text: str
    original_answer: str
    answer_text: str
    area_key: str | None = None
    area_title: str | None = None
    comparison: AttemptComparisonView | None = None
    created_at: datetime


def attempt_view(record: AttemptRecord) -> AttemptView:
    return AttemptView(
        **record.model_dump(include={
            "id", "session_id", "question_turn_id", "original_turn_id", "sequence", "question_text",
            "original_answer", "answer_text", "area_key", "area_title", "created_at",
        }),
        comparison=comparison_view(record.comparison) if record.comparison else None,
    )
