"""Review -> story improvement suggestions. Review suggests; only the candidate edits a story.

A suggestion is created only when every link is exact:

    Skeptic observation (typed, confident, about one candidate answer)
    -> that answer's turn -> its plan objective "story-<position>-<n>"
    -> the practice usage at that position -> the exact story, version and role practised

Only observation types that name one story part are used. Anything that cannot be attributed
exactly creates nothing: a missing suggestion is better than feedback on the wrong story.
No model is called here, the Skeptic's own wording is never shown, and nothing is scored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict

from .config import Settings
from .http_pool import pooled
from .practice_modes import story_position
from .practice_story_usage import PracticeStoryUsageRepository
from .schemas import SessionStatus
from .story_repository import StoriesUnavailable, StoryArchived, StoryRepository


class IssueType(StrEnum):
    OWNERSHIP_UNCLEAR = "OWNERSHIP_UNCLEAR"
    RESULT_UNSUPPORTED = "RESULT_UNSUPPORTED"


class SuggestionStatus(StrEnum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    DISMISSED = "DISMISSED"


# The only Review findings that can become a story suggestion: each names exactly one story part.
# Vagueness, contradictions and the rest do not say which part to work on, so they create nothing.
ISSUES: dict[str, tuple[IssueType, str]] = {
    "OWNERSHIP_DRIFT": (IssueType.OWNERSHIP_UNCLEAR, "ownership"),
    "UNSUPPORTED_SCALE": (IssueType.RESULT_UNSUPPORTED, "measurable_result"),
}


class SuggestionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StorySuggestion(SuggestionModel):
    id: UUID
    session_id: UUID
    usage_id: UUID
    story_id: UUID
    story_version_id: UUID
    role_profile_id: UUID | None = None
    source_turn_id: UUID
    source_observation_id: UUID
    issue_type: IssueType
    story_part: str
    status: SuggestionStatus = SuggestionStatus.OPEN
    resolved_by_story_version_id: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class StorySuggestionView(SuggestionModel):
    """What the candidate sees. Titles come from the version practised; no internal reasoning."""

    id: UUID
    session_id: UUID
    story_id: UUID
    story_title: str
    practised_version: int
    current_version: int
    story_archived: bool
    role_profile_id: UUID | None = None
    issue_type: IssueType
    story_part: str
    status: SuggestionStatus
    resolved_version: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime


@dataclass(frozen=True)
class Observation:
    id: UUID
    source_turn_id: UUID
    observation_type: str
    confidence: float


class SuggestionNotFound(Exception):
    pass


class SuggestionClosed(Exception):
    """Only an open suggestion can be accepted or dismissed."""


class SuggestionNotAddressed(Exception):
    """The saved version did not change the part the suggestion is about."""


# ------------------------------------------------------------------ what Review found


class ReviewFindingSource(Protocol):
    async def observations(self, session_id: UUID, user_id: UUID, min_confidence: float) -> list[Observation]: ...
    async def answer_threads(self, session_id: UUID, turn_ids: list[UUID]) -> dict[UUID, str | None]: ...


class StorySuggestionRepository(Protocol):
    async def add_missing(self, user_id: UUID, rows: list[StorySuggestion]) -> None: ...
    async def for_session(self, session_id: UUID, user_id: UUID) -> list[StorySuggestion]: ...
    async def for_story(self, story_id: UUID, user_id: UUID) -> list[StorySuggestion]: ...
    async def open_for_user(self, user_id: UUID) -> list[StorySuggestion]: ...
    async def get(self, suggestion_id: UUID, user_id: UUID) -> StorySuggestion | None: ...
    async def close(
        self, suggestion_id: UUID, user_id: UUID, status: SuggestionStatus, resolved_version_id: UUID | None
    ) -> StorySuggestion | None: ...


class StorySuggestionService:
    def __init__(
        self,
        suggestions: StorySuggestionRepository,
        findings: ReviewFindingSource,
        usages: PracticeStoryUsageRepository,
        stories: StoryRepository,
        sessions: Any,
        *,
        min_confidence: float,
    ) -> None:
        self._suggestions = suggestions
        self._findings = findings
        self._usages = usages
        self._stories = stories
        self._sessions = sessions
        self._min_confidence = min_confidence

    async def sync_session(self, session_id: UUID, user_id: UUID) -> None:
        """Derive suggestions for one finished practice. Safe to repeat: rows are keyed by source."""
        session = await self._sessions.get(session_id, user_id)
        if session is None:
            raise SuggestionNotFound
        if session.status != SessionStatus.COMPLETED:
            return  # no review yet
        usages = {usage.position: usage for usage in await self._usages.for_session(session_id, user_id)}
        if not usages:
            return  # no story was chosen for this practice
        observations = [
            item for item in await self._findings.observations(session_id, user_id, self._min_confidence)
            if item.observation_type in ISSUES and item.confidence >= self._min_confidence
        ]
        if not observations:
            return
        threads = await self._findings.answer_threads(session_id, sorted({item.source_turn_id for item in observations}))
        rows: dict[tuple[UUID, IssueType], StorySuggestion] = {}
        now = datetime.now(UTC)
        for item in observations:
            usage = usages.get(story_position(threads.get(item.source_turn_id)))
            if usage is None:
                continue  # the answer was not about a chosen story, or cannot be tied to one
            issue, part = ISSUES[item.observation_type]
            rows.setdefault((item.source_turn_id, issue), StorySuggestion(
                id=uuid4(), session_id=session_id, usage_id=usage.id, story_id=usage.story_id,
                story_version_id=usage.story_version_id, role_profile_id=usage.role_profile_id,
                source_turn_id=item.source_turn_id, source_observation_id=item.id,
                issue_type=issue, story_part=part, created_at=now,
            ))
        if rows:
            await self._suggestions.add_missing(user_id, list(rows.values()))

    async def for_session(self, session_id: UUID, user_id: UUID) -> list[StorySuggestionView]:
        await self.sync_session(session_id, user_id)
        return await self._views(await self._suggestions.for_session(session_id, user_id), user_id)

    async def for_story(self, story_id: UUID, user_id: UUID) -> list[StorySuggestionView] | None:
        if await self._stories.get(story_id, user_id) is None:
            return None
        # A finished practice whose review was never opened still gets its suggestions here.
        for record in await self._usages.history_for_story(story_id, user_id):
            if record.session_status == SessionStatus.COMPLETED:
                await self.sync_session(record.session_id, user_id)
        return await self._views(await self._suggestions.for_story(story_id, user_id), user_id)

    async def open_for_user(self, user_id: UUID) -> list[StorySuggestion]:
        return await self._suggestions.open_for_user(user_id)

    async def dismiss(self, suggestion_id: UUID, user_id: UUID) -> StorySuggestionView:
        suggestion = await self._open(suggestion_id, user_id)
        closed = await self._suggestions.close(suggestion.id, user_id, SuggestionStatus.DISMISSED, None)
        return (await self._views([closed or suggestion], user_id))[0]

    async def accept(self, suggestion_id: UUID, user_id: UUID, saved_version: int) -> StorySuggestionView:
        """Accepted only when the candidate's save produced `saved_version`, it is newer than the
        version practised, and that save changed the part the suggestion is about."""
        suggestion = await self._open(suggestion_id, user_id)
        story = await self._stories.get(suggestion.story_id, user_id)
        if story is None:
            raise SuggestionNotFound
        if story.archived_at is not None:
            raise StoryArchived
        versions = {item.version: item for item in await self._stories.versions(story.id, user_id) or []}
        practised = next((item for item in versions.values() if item.id == suggestion.story_version_id), None)
        saved, before = versions.get(saved_version), versions.get(saved_version - 1)
        if (
            practised is None or saved is None or before is None
            or saved_version != story.current_version or saved.version <= practised.version
            or getattr(saved, suggestion.story_part) == getattr(before, suggestion.story_part)
        ):
            raise SuggestionNotAddressed
        closed = await self._suggestions.close(suggestion.id, user_id, SuggestionStatus.ACCEPTED, saved.id)
        return (await self._views([closed or suggestion], user_id))[0]

    async def _open(self, suggestion_id: UUID, user_id: UUID) -> StorySuggestion:
        suggestion = await self._suggestions.get(suggestion_id, user_id)
        if suggestion is None:
            raise SuggestionNotFound
        if suggestion.status != SuggestionStatus.OPEN:
            raise SuggestionClosed
        return suggestion

    async def _views(self, rows: list[StorySuggestion], user_id: UUID) -> list[StorySuggestionView]:
        views: list[StorySuggestionView] = []
        for row in rows:
            story = await self._stories.get(row.story_id, user_id)
            practised = await self._stories.version(row.story_id, row.story_version_id, user_id)
            if story is None or practised is None:
                continue
            resolved = (
                await self._stories.version(row.story_id, row.resolved_by_story_version_id, user_id)
                if row.resolved_by_story_version_id else None
            )
            views.append(StorySuggestionView(
                id=row.id, session_id=row.session_id, story_id=row.story_id, story_title=practised.title,
                practised_version=practised.version, current_version=story.current_version,
                story_archived=story.archived_at is not None, role_profile_id=row.role_profile_id,
                issue_type=row.issue_type, story_part=row.story_part, status=row.status,
                resolved_version=resolved.version if resolved else None, resolved_at=row.resolved_at,
                created_at=row.created_at,
            ))
        return views


# ------------------------------------------------------------------ storage


def _service_headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


async def _call(method: str, url: str, headers: dict[str, str], params: dict[str, str], json: Any = None) -> list[dict[str, Any]]:
    try:
        async with pooled(10) as client:
            response = await client.request(method, url, headers=headers, params=params, json=json)
            response.raise_for_status()
            return response.json() if response.content else []
    except (httpx.HTTPError, TypeError, ValueError) as exc:
        raise StoriesUnavailable from exc


SUGGESTION_COLUMNS = (
    "id,session_id,usage_id,story_id,story_version_id,role_profile_id,source_turn_id,source_observation_id,"
    "issue_type,story_part,status,resolved_by_story_version_id,resolved_at,created_at"
)


class SupabaseReviewFindingSource:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise StoriesUnavailable("Supabase is not configured")
        self._url = f"{settings.next_public_supabase_url.rstrip('/')}/rest/v1"
        self._headers = _service_headers(settings)

    async def observations(self, session_id: UUID, user_id: UUID, min_confidence: float) -> list[Observation]:
        rows = await _call("GET", f"{self._url}/skeptic_observations", self._headers, {
            "session_id": f"eq.{session_id}", "user_id": f"eq.{user_id}",
            "observation_type": f"in.({','.join(ISSUES)})", "confidence": f"gte.{min_confidence}",
            "select": "id,source_turn_id,observation_type,confidence",
        })
        return [
            Observation(UUID(row["id"]), UUID(row["source_turn_id"]), row["observation_type"], float(row["confidence"]))
            for row in rows
        ]

    async def answer_threads(self, session_id: UUID, turn_ids: list[UUID]) -> dict[UUID, str | None]:
        if not turn_ids:
            return {}
        rows = await _call("GET", f"{self._url}/turns", self._headers, {
            "session_id": f"eq.{session_id}", "speaker": "eq.candidate",
            "id": f"in.({','.join(str(item) for item in turn_ids)})", "select": "id,primary_thread_id",
        })
        return {UUID(row["id"]): row.get("primary_thread_id") for row in rows}


class SupabaseStorySuggestionRepository:
    """Service-role access; every query filters by user_id, and the table's triggers re-check every link."""

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise StoriesUnavailable("Supabase is not configured")
        self._url = f"{settings.next_public_supabase_url.rstrip('/')}/rest/v1/story_improvement_suggestions"
        self._headers = _service_headers(settings)

    async def _rows(self, params: dict[str, str]) -> list[StorySuggestion]:
        rows = await _call("GET", self._url, self._headers, {**params, "select": SUGGESTION_COLUMNS, "order": "created_at.desc"})
        return [StorySuggestion.model_validate(row) for row in rows]

    async def add_missing(self, user_id: UUID, rows: list[StorySuggestion]) -> None:
        body = [
            {**row.model_dump(mode="json", exclude={"id", "status", "resolved_by_story_version_id", "resolved_at", "created_at"}),
             "user_id": str(user_id)}
            for row in rows
        ]
        await _call(
            "POST", self._url, {**self._headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            {"on_conflict": "session_id,source_turn_id,issue_type"}, body,
        )

    async def for_session(self, session_id: UUID, user_id: UUID) -> list[StorySuggestion]:
        return await self._rows({"session_id": f"eq.{session_id}", "user_id": f"eq.{user_id}"})

    async def for_story(self, story_id: UUID, user_id: UUID) -> list[StorySuggestion]:
        return await self._rows({"story_id": f"eq.{story_id}", "user_id": f"eq.{user_id}"})

    async def open_for_user(self, user_id: UUID) -> list[StorySuggestion]:
        return await self._rows({"user_id": f"eq.{user_id}", "status": "eq.OPEN", "limit": "500"})

    async def get(self, suggestion_id: UUID, user_id: UUID) -> StorySuggestion | None:
        rows = await self._rows({"id": f"eq.{suggestion_id}", "user_id": f"eq.{user_id}"})
        return rows[0] if rows else None

    async def close(
        self, suggestion_id: UUID, user_id: UUID, status: SuggestionStatus, resolved_version_id: UUID | None
    ) -> StorySuggestion | None:
        rows = await _call(
            "PATCH", self._url, {**self._headers, "Prefer": "return=representation"},
            {"id": f"eq.{suggestion_id}", "user_id": f"eq.{user_id}", "status": "eq.OPEN", "select": SUGGESTION_COLUMNS},
            {
                "status": status.value,
                "resolved_at": datetime.now(UTC).isoformat(),
                "resolved_by_story_version_id": str(resolved_version_id) if resolved_version_id else None,
            },
        )
        return StorySuggestion.model_validate(rows[0]) if rows else None


class MemoryReviewFindingSource:
    """Test double: observations and the thread each candidate answer belonged to."""

    def __init__(self) -> None:
        self.rows: list[tuple[UUID, UUID, Observation]] = []  # (session, user, observation)
        self.threads: dict[UUID, tuple[UUID, str | None]] = {}  # turn -> (session, thread)

    def answer(self, session_id: UUID, thread: str | None) -> UUID:
        turn = uuid4()
        self.threads[turn] = (session_id, thread)
        return turn

    def observe(self, session_id: UUID, user_id: UUID, turn: UUID, kind: str, confidence: float = 0.9) -> UUID:
        observation = Observation(uuid4(), turn, kind, confidence)
        self.rows.append((session_id, user_id, observation))
        return observation.id

    async def observations(self, session_id: UUID, user_id: UUID, min_confidence: float) -> list[Observation]:
        return [item for session, user, item in self.rows if session == session_id and user == user_id and item.confidence >= min_confidence]

    async def answer_threads(self, session_id: UUID, turn_ids: list[UUID]) -> dict[UUID, str | None]:
        return {turn: thread for turn, (session, thread) in self.threads.items() if session == session_id and turn in turn_ids}


class MemoryStorySuggestionRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, tuple[UUID, StorySuggestion]] = {}

    async def add_missing(self, user_id: UUID, rows: list[StorySuggestion]) -> None:
        existing = {(row.session_id, row.source_turn_id, row.issue_type) for _, row in self.rows.values()}
        for row in rows:
            if (row.session_id, row.source_turn_id, row.issue_type) not in existing:
                self.rows[row.id] = (user_id, row)

    def _owned(self, user_id: UUID) -> list[StorySuggestion]:
        return sorted((row for owner, row in self.rows.values() if owner == user_id), key=lambda row: row.created_at, reverse=True)

    async def for_session(self, session_id: UUID, user_id: UUID) -> list[StorySuggestion]:
        return [row for row in self._owned(user_id) if row.session_id == session_id]

    async def for_story(self, story_id: UUID, user_id: UUID) -> list[StorySuggestion]:
        return [row for row in self._owned(user_id) if row.story_id == story_id]

    async def open_for_user(self, user_id: UUID) -> list[StorySuggestion]:
        return [row for row in self._owned(user_id) if row.status == SuggestionStatus.OPEN]

    async def get(self, suggestion_id: UUID, user_id: UUID) -> StorySuggestion | None:
        found = self.rows.get(suggestion_id)
        return found[1] if found and found[0] == user_id else None

    async def close(
        self, suggestion_id: UUID, user_id: UUID, status: SuggestionStatus, resolved_version_id: UUID | None
    ) -> StorySuggestion | None:
        current = await self.get(suggestion_id, user_id)
        if current is None or current.status != SuggestionStatus.OPEN:
            return None
        closed = current.model_copy(update={
            "status": status, "resolved_at": datetime.now(UTC), "resolved_by_story_version_id": resolved_version_id,
        })
        self.rows[suggestion_id] = (user_id, closed)
        return closed
