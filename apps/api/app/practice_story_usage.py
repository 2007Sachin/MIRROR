"""Which practice sessions actually used a story, and exactly which version of it.

A story counts as used only when the candidate chose it for a practice: the session is
created with that story, its current version is pinned here, and the practice plan is
built from that pinned version. Matching a theme or appearing on the Interview Map never
creates a row. Rows are history and are never rewritten, so a later edit, archive or
restore of the story leaves every earlier practice pointing at what was practised.

Nothing here scores a story. A count is how many times it was practised, nothing more.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .http_pool import pooled
from .story_models import StoryVersion
from .story_repository import StoriesUnavailable, StoryRepository

USAGE_COLUMNS = "id,session_id,story_id,story_version_id,role_profile_id,position,created_at"
# Resource embedding over the usage table's foreign keys: the version number practised and
# what became of the session, read in the same owner-scoped query.
HISTORY_SELECT = f"{USAGE_COLUMNS},story_versions(version),sessions(status,practice_mode,created_at,started_at)"


class UsageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PracticeStoryUsage(UsageModel):
    """One story in one practice session. `position` is its order in the practice plan."""

    id: UUID
    session_id: UUID
    story_id: UUID
    story_version_id: UUID
    role_profile_id: UUID | None = None
    position: int = Field(ge=1, le=4)
    created_at: datetime


class StoryPracticeRecord(PracticeStoryUsage):
    """A practice of a story, with the version practised and what became of the session."""

    story_version: int = Field(ge=1)
    session_status: str
    practice_mode: str
    session_created_at: datetime
    session_started_at: datetime | None = None


class StoryPracticeSummary(UsageModel):
    """How often a story has been practised. Only started sessions count."""

    story_id: UUID
    practice_count: int = Field(ge=0)
    last_practiced_at: datetime | None = None


class PracticeStoryNotFound(Exception):
    pass


class PracticeStoryArchived(Exception):
    pass


class UsageRejected(Exception):
    """A usage that would link records across people, stories or roles."""


def practice_summaries(records: Sequence[StoryPracticeRecord]) -> list[StoryPracticeSummary]:
    """Per story: practices that were actually started, and the most recent one."""
    started: dict[UUID, list[datetime]] = {}
    for record in records:
        started.setdefault(record.story_id, [])
        if record.session_started_at is not None:
            started[record.story_id].append(record.session_started_at)
    return [
        StoryPracticeSummary(story_id=story_id, practice_count=len(days), last_practiced_at=max(days, default=None))
        for story_id, days in started.items()
    ]


# ------------------------------------------------------------------ selection and planning


async def pin_story_versions(stories: StoryRepository, user_id: UUID, story_ids: Sequence[UUID]) -> list[StoryVersion]:
    """The current version of each chosen story. Only the person's own, active stories."""
    pinned: list[StoryVersion] = []
    for story_id in story_ids:
        story = await stories.get(story_id, user_id)
        if story is None:
            raise PracticeStoryNotFound
        if story.archived_at is not None:
            raise PracticeStoryArchived
        versions = await stories.versions(story_id, user_id) or []
        current = next((item for item in versions if item.version == story.current_version), None)
        if current is None:
            raise StoriesUnavailable  # every story has its current version recorded
        pinned.append(current)
    return pinned


async def practice_story_versions(
    usages: PracticeStoryUsageRepository, stories: StoryRepository, session_id: UUID, user_id: UUID
) -> list[StoryVersion]:
    """The exact story versions a session's plan is built from, in plan order."""
    versions: list[StoryVersion] = []
    for usage in sorted(await usages.for_session(session_id, user_id), key=lambda item: item.position):
        version = await stories.version(usage.story_id, usage.story_version_id, user_id)
        if version is not None:
            versions.append(version)
    return versions


# ------------------------------------------------------------------ storage


class PracticeStoryUsageRepository(Protocol):
    async def record(
        self, user_id: UUID, session_id: UUID, role_profile_id: UUID | None, versions: Sequence[StoryVersion]
    ) -> list[PracticeStoryUsage]: ...
    async def for_session(self, session_id: UUID, user_id: UUID) -> list[PracticeStoryUsage]: ...
    async def history_for_story(self, story_id: UUID, user_id: UUID) -> list[StoryPracticeRecord]: ...
    async def history_for_user(self, user_id: UUID) -> list[StoryPracticeRecord]: ...


class SupabasePracticeStoryUsageRepository:
    """Service-role access; every query filters by user_id, and the table's trigger re-checks
    that session, story, version and role all belong together."""

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise StoriesUnavailable("Supabase story storage is not configured")
        self._url = f"{settings.next_public_supabase_url.rstrip('/')}/rest/v1/practice_story_usages"
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, params: dict[str, str], json: Any = None, prefer: str | None = None) -> list[dict[str, Any]]:
        headers = {**self._headers, **({"Prefer": prefer} if prefer else {})}
        try:
            async with pooled(10) as client:
                response = await client.request(method, self._url, headers=headers, params=params, json=json)
                response.raise_for_status()
                return response.json() if response.content else []
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise StoriesUnavailable from exc

    async def record(
        self, user_id: UUID, session_id: UUID, role_profile_id: UUID | None, versions: Sequence[StoryVersion]
    ) -> list[PracticeStoryUsage]:
        existing = await self.for_session(session_id, user_id)
        if existing or not versions:
            return existing  # a replayed request never adds or changes stories
        rows = [
            {
                "user_id": str(user_id),
                "session_id": str(session_id),
                "story_id": str(version.story_id),
                "story_version_id": str(version.id),
                "role_profile_id": str(role_profile_id) if role_profile_id else None,
                "position": index,
            }
            for index, version in enumerate(versions, start=1)
        ]
        await self._request(
            "POST",
            {"on_conflict": "session_id,story_id", "select": USAGE_COLUMNS},
            json=rows,
            prefer="resolution=ignore-duplicates,return=representation",
        )
        return await self.for_session(session_id, user_id)

    async def for_session(self, session_id: UUID, user_id: UUID) -> list[PracticeStoryUsage]:
        rows = await self._request(
            "GET", {"session_id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": USAGE_COLUMNS, "order": "position.asc"}
        )
        return [PracticeStoryUsage.model_validate(row) for row in rows]

    async def _history(self, params: dict[str, str]) -> list[StoryPracticeRecord]:
        rows = await self._request("GET", {**params, "select": HISTORY_SELECT, "order": "created_at.desc", "limit": "500"})
        records = []
        for row in rows:
            version, session = row.pop("story_versions") or {}, row.pop("sessions") or {}
            records.append(
                StoryPracticeRecord(
                    **row,
                    story_version=version["version"],
                    session_status=session["status"],
                    practice_mode=session["practice_mode"],
                    session_created_at=session["created_at"],
                    session_started_at=session.get("started_at"),
                )
            )
        return records

    async def history_for_story(self, story_id: UUID, user_id: UUID) -> list[StoryPracticeRecord]:
        return await self._history({"story_id": f"eq.{story_id}", "user_id": f"eq.{user_id}"})

    async def history_for_user(self, user_id: UUID) -> list[StoryPracticeRecord]:
        return await self._history({"user_id": f"eq.{user_id}"})


class MemoryPracticeStoryUsageRepository:
    """In-process usage for tests. Applies the same checks as the database trigger."""

    def __init__(self, sessions: Any, stories: StoryRepository) -> None:
        self._sessions = sessions
        self._stories = stories
        self.rows: list[tuple[UUID, PracticeStoryUsage]] = []

    async def record(
        self, user_id: UUID, session_id: UUID, role_profile_id: UUID | None, versions: Sequence[StoryVersion]
    ) -> list[PracticeStoryUsage]:
        existing = await self.for_session(session_id, user_id)
        if existing or not versions:
            return existing
        session = await self._sessions.get(session_id, user_id)
        if session is None or session.role_profile_id != role_profile_id:
            raise UsageRejected
        for version in versions:
            story = await self._stories.get(version.story_id, user_id)
            owned = await self._stories.version(version.story_id, version.id, user_id)
            if story is None or story.archived_at is not None or owned is None:
                raise UsageRejected
        now = datetime.now(UTC)
        for index, version in enumerate(versions, start=1):
            self.rows.append((user_id, PracticeStoryUsage(
                id=uuid4(), session_id=session_id, story_id=version.story_id, story_version_id=version.id,
                role_profile_id=role_profile_id, position=index, created_at=now,
            )))
        return await self.for_session(session_id, user_id)

    async def for_session(self, session_id: UUID, user_id: UUID) -> list[PracticeStoryUsage]:
        found = [row for owner, row in self.rows if owner == user_id and row.session_id == session_id]
        return sorted(found, key=lambda row: row.position)

    async def _history(self, user_id: UUID, story_id: UUID | None) -> list[StoryPracticeRecord]:
        records = []
        for owner, row in self.rows:
            if owner != user_id or (story_id is not None and row.story_id != story_id):
                continue
            session = await self._sessions.get(row.session_id, user_id)
            version = await self._stories.version(row.story_id, row.story_version_id, user_id)
            if session is None or version is None:
                continue
            records.append(StoryPracticeRecord(
                **row.model_dump(),
                story_version=version.version,
                session_status=session.status.value if hasattr(session.status, "value") else session.status,
                practice_mode=session.practice_mode,
                session_created_at=session.created_at,
                session_started_at=session.started_at,
            ))
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    async def history_for_story(self, story_id: UUID, user_id: UUID) -> list[StoryPracticeRecord]:
        return await self._history(user_id, story_id)

    async def history_for_user(self, user_id: UUID) -> list[StoryPracticeRecord]:
        return await self._history(user_id, None)
