"""Try again: record another attempt at an answered question and compare it with the first.

Deterministic around one bounded model call:
- ownership, eligibility and sequencing are decided here, never by the model
- the original answer is read from the transcript and copied into the attempt; the
  transcript itself is never written to
- one retry-comparison call per attempt; on any failure the deterministic presence
  checks are used instead, and the attempt is saved either way
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

import httpx

from .agents.definitions import AgentExecutionContext
from .agents.retry_comparison import RETRY_COMPARISON_AGENT_NAME, RETRY_COMPARISON_PROMPT_VERSION
from .agents.runner import AgentRunner
from .attempt_models import (
    Aspect,
    AspectChange,
    AttemptComparison,
    AttemptCreate,
    AttemptRecord,
    ComparisonSource,
    Presence,
    RetryComparisonInput,
    RetryComparisonOutput,
)
from .config import Settings
from .copy_guard import clean_or_fallback
from .http_pool import pooled
from .pressure_test import answer_features
from .schemas import SessionStatus

ATTEMPT_COLUMNS = (
    "id,user_id,session_id,question_turn_id,original_turn_id,sequence,question_text,original_answer,"
    "answer_text,area_key,area_title,role_profile_id,idempotency_key,comparison,comparison_source,model,prompt_version,created_at"
)
MAX_ATTEMPTS_PER_ANSWER = 10


class AttemptNotFound(Exception):
    pass


class AttemptNotAllowed(Exception):
    """This answer cannot take another attempt right now."""


class AttemptIdempotencyConflict(AttemptNotAllowed):
    """A replay key was reused for a different answer."""


class AttemptNotFinished(AttemptNotAllowed):
    """Retries are only for a finished practice, so the live transcript is never touched."""


class AttemptsUnavailable(Exception):
    pass


# ------------------------------------------------------------------ persistence


class AttemptRepository(Protocol):
    async def list_for_session(self, session_id: UUID, user_id: UUID) -> list[AttemptRecord]: ...
    async def create(self, values: dict[str, Any]) -> AttemptRecord: ...


class SupabaseAttemptRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise AttemptsUnavailable("Supabase attempt storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def list_for_session(self, session_id: UUID, user_id: UUID) -> list[AttemptRecord]:
        try:
            async with pooled(10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/answer_attempts",
                    headers=self._headers,
                    params={
                        "session_id": f"eq.{session_id}",
                        "user_id": f"eq.{user_id}",
                        "select": ATTEMPT_COLUMNS,
                        "order": "created_at.asc",
                        "limit": "500",
                    },
                )
                response.raise_for_status()
                return [AttemptRecord.model_validate(row) for row in response.json()]
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise AttemptsUnavailable from exc

    async def create(self, values: dict[str, Any]) -> AttemptRecord:
        try:
            async with pooled(10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/answer_attempts",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"select": ATTEMPT_COLUMNS},
                    json=values,
                )
                if response.status_code == 409:
                    raise AttemptNotAllowed("another attempt was saved at the same time")
                response.raise_for_status()
                return AttemptRecord.model_validate(response.json()[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise AttemptsUnavailable from exc


class MemoryAttemptRepository:
    def __init__(self) -> None:
        self.rows: list[AttemptRecord] = []
        self.idempotency: dict[tuple[UUID, UUID], AttemptRecord] = {}

    async def list_for_session(self, session_id: UUID, user_id: UUID) -> list[AttemptRecord]:
        return [row for row in self.rows if row.session_id == session_id and row.user_id == user_id]

    async def create(self, values: dict[str, Any]) -> AttemptRecord:
        key = values.get("idempotency_key")
        if key:
            existing = self.idempotency.get((UUID(str(values["user_id"])), UUID(str(key))))
            if existing:
                return existing
        clash = any(
            str(row.original_turn_id) == str(values["original_turn_id"]) and row.sequence == values["sequence"]
            for row in self.rows
        )
        if clash:
            raise AttemptNotAllowed("another attempt was saved at the same time")
        record = AttemptRecord.model_validate({**values, "id": uuid4(), "created_at": datetime.now(UTC)})
        self.rows.append(record)
        if key:
            self.idempotency[(record.user_id, UUID(str(key)))] = record
        return record


# ------------------------------------------------------------------ comparison

_FEATURE_ASPECT = {
    "own_part": Aspect.OWNERSHIP,
    "reason": Aspect.REASONING,
    "result": Aspect.RESULT,
    "number": Aspect.MEASURE,
    "detail": Aspect.SPECIFIC_EXAMPLE,
}

# Fixed sentences for the deterministic fallback. Plain, kind, and never a number.
_NEXT_FOR: dict[Aspect, str] = {
    Aspect.SITUATION: "Next time, start with one sentence on what was going on.",
    Aspect.OWNERSHIP: "Next time, say clearly which part you did yourself.",
    Aspect.ACTIONS: "Next time, walk through the steps you took.",
    Aspect.REASONING: "Next time, add why you chose that approach.",
    Aspect.RESULT: "Next time, finish with what happened afterwards.",
    Aspect.MEASURE: "Next time, say roughly how big the change was. An estimate is fine if you say so.",
    Aspect.SPECIFIC_EXAMPLE: "Next time, add one concrete detail only you would know.",
}
SAFE_SUMMARY = "Your latest answer is saved next to your first one, so you can compare them."
SAFE_NEXT = "Try saying your latest answer out loud once more."


def checks_comparison(first: str, latest: str) -> AttemptComparison:
    """What the presence checks can see in both answers. Used when the model is unavailable."""
    before, after = answer_features(first), answer_features(latest)
    changes = [
        AspectChange(
            aspect=aspect,
            first=Presence.PRESENT if before[key] else Presence.ABSENT,
            latest=Presence.PRESENT if after[key] else Presence.ABSENT,
        )
        for key, aspect in _FEATURE_ASPECT.items()
    ]
    gained = [c for c in changes if c.first == Presence.ABSENT and c.latest == Presence.PRESENT]
    missing = [c.aspect for c in changes if c.latest == Presence.ABSENT]
    summary = (
        "Your latest answer includes something your first one didn't."
        if gained
        else "Your two answers cover much the same ground."
    )
    return AttemptComparison(
        source=ComparisonSource.CHECKS,
        changes=changes,
        summary=summary,
        next_suggestion=_NEXT_FOR[missing[0]] if missing else SAFE_NEXT,
    )


def model_comparison(output: RetryComparisonOutput, requested: list[Aspect]) -> AttemptComparison:
    """Keep only requested aspects, in a fixed order, and screen the two sentences."""
    by_aspect = {change.aspect: change for change in output.changes if change.aspect in requested}
    changes = [by_aspect[aspect] for aspect in Aspect if aspect in by_aspect]
    missing = [c.aspect for c in changes if c.latest == Presence.ABSENT]
    return AttemptComparison(
        source=ComparisonSource.MODEL,
        changes=changes,
        summary=clean_or_fallback(output.summary, SAFE_SUMMARY, field="retry.summary"),
        next_suggestion=clean_or_fallback(
            output.next_suggestion, _NEXT_FOR[missing[0]] if missing else SAFE_NEXT, field="retry.next_suggestion"
        ),
    )


# ------------------------------------------------------------------ service


class TranscriptReader(Protocol):
    async def list_public_turns(self, session_id: UUID, user_id: UUID) -> list[Any]: ...


class SessionReader(Protocol):
    async def get(self, session_id: UUID, user_id: UUID) -> Any: ...


class AttemptService:
    def __init__(
        self,
        sessions: SessionReader,
        transcript: TranscriptReader,
        attempts: AttemptRepository,
        runner: AgentRunner | None,
        *,
        model: str,
    ) -> None:
        self._sessions = sessions
        self._transcript = transcript
        self._attempts = attempts
        self._runner = runner
        self._model = model

    async def list_for_session(self, session_id: UUID, user_id: UUID) -> list[AttemptRecord]:
        if await self._sessions.get(session_id, user_id) is None:
            raise AttemptNotFound
        return await self._attempts.list_for_session(session_id, user_id)

    async def compare(self, question: str, first: str, latest: str, *, role: str | None, practising: str | None, user_id: UUID, session_id: UUID) -> tuple[AttemptComparison, str | None]:
        requested = list(Aspect)
        if self._runner is None:
            return checks_comparison(first, latest), None
        try:
            result = await self._runner.run(
                RETRY_COMPARISON_AGENT_NAME,
                RetryComparisonInput(
                    question=question, first_answer=first, latest_answer=latest,
                    target_role=role, practising=practising, aspects=requested,
                ),
                context=AgentExecutionContext(session_id=session_id, user_id=user_id),
            )
        except Exception:  # noqa: BLE001 - any provider problem falls back to the checks
            return checks_comparison(first, latest), None
        if not result.success or result.output is None:
            return checks_comparison(first, latest), None
        try:
            output = RetryComparisonOutput.model_validate(result.output)
        except ValueError:
            return checks_comparison(first, latest), None
        compared = model_comparison(output, requested)
        if not compared.changes:
            return checks_comparison(first, latest), None
        return compared, self._model

    async def create(self, session_id: UUID, answer_turn_id: UUID, user_id: UUID, payload: AttemptCreate) -> AttemptRecord:
        session = await self._sessions.get(session_id, user_id)
        if session is None:
            raise AttemptNotFound
        if session.status != SessionStatus.COMPLETED:
            raise AttemptNotFinished

        turns = sorted(await self._transcript.list_public_turns(session_id, user_id), key=lambda turn: turn.turn_index)
        index = next((i for i, turn in enumerate(turns) if turn.id == answer_turn_id), None)
        if index is None or turns[index].speaker != "CANDIDATE":
            raise AttemptNotFound
        question = next((turn for turn in reversed(turns[:index]) if turn.speaker == "INTERVIEWER"), None)
        if question is None:
            raise AttemptNotFound

        earlier = [row for row in await self._attempts.list_for_session(session_id, user_id) if row.original_turn_id == answer_turn_id]
        if payload.idempotency_key:
            replay = next((row for row in earlier if row.idempotency_key == payload.idempotency_key), None)
            if replay:
                if replay.answer_text != payload.answer or replay.area_key != payload.area_key:
                    raise AttemptIdempotencyConflict("this retry key was already used for another answer")
                return replay
        if len(earlier) >= MAX_ATTEMPTS_PER_ANSWER:
            raise AttemptNotAllowed("this answer already has many attempts")
        sequence = max((row.sequence for row in earlier), default=0) + 1

        original = turns[index].text
        comparison, model = await self.compare(
            question.text, original, payload.answer,
            role=session.target_role, practising=payload.area_title, user_id=user_id, session_id=session_id,
        )
        return await self._attempts.create({
            "user_id": str(user_id),
            "session_id": str(session_id),
            "question_turn_id": str(question.id),
            "original_turn_id": str(answer_turn_id),
            "sequence": sequence,
            "question_text": question.text,
            "original_answer": original,
            "answer_text": payload.answer,
            "area_key": payload.area_key,
            "area_title": payload.area_title,
            "role_profile_id": str(session.role_profile_id) if session.role_profile_id else None,
            "idempotency_key": str(payload.idempotency_key) if payload.idempotency_key else None,
            "comparison": comparison.model_dump(mode="json"),
            "comparison_source": comparison.source.value,
            "model": model,
            "prompt_version": RETRY_COMPARISON_PROMPT_VERSION if model else None,
        })
