from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

import httpx

from .config import Settings
from .http_pool import pooled
from .story_models import (
    StoryChangeReason,
    StoryCreate,
    StoryRead,
    StoryRoleFraming,
    StoryRoleFramingInput,
    StoryUpdate,
    StoryVersion,
    story_content,
)

STORY_COLUMNS = (
    "id,user_id,title,themes,role_profile_id,source_claim_id,source_document_id,source_text,"
    "origin,situation,ownership,actions,reasoning,trade_offs,outcome,measurable_result,"
    "learning,do_differently,created_at,updated_at,archived_at,current_version"
)
VERSION_COLUMNS = (
    "id,story_id,version,title,themes,situation,ownership,actions,reasoning,trade_offs,outcome,"
    "measurable_result,learning,do_differently,change_reason,restored_from_version,created_at"
)
FRAMING_COLUMNS = "id,story_id,role_profile_id,themes,emphasis,created_at,updated_at"


class StoriesUnavailable(Exception):
    pass


class StoryArchived(Exception):
    """An archived story is read-only until it is restored."""


class StoryRepository(Protocol):
    """Every method is owner-scoped: another person's story reads as not found."""

    async def list_for_user(self, user_id: UUID, *, archived: bool = False) -> list[StoryRead]: ...
    async def get(self, story_id: UUID, user_id: UUID) -> StoryRead | None: ...
    async def create(self, user_id: UUID, values: StoryCreate) -> StoryRead: ...
    async def update(self, story_id: UUID, user_id: UUID, values: StoryUpdate) -> StoryRead | None: ...
    async def archive(self, story_id: UUID, user_id: UUID) -> StoryRead | None: ...
    async def restore(self, story_id: UUID, user_id: UUID) -> StoryRead | None: ...
    async def versions(self, story_id: UUID, user_id: UUID) -> list[StoryVersion] | None: ...
    async def version(self, story_id: UUID, version_id: UUID, user_id: UUID) -> StoryVersion | None: ...
    async def restore_version(self, story_id: UUID, version_id: UUID, user_id: UUID) -> StoryRead | None: ...
    # Role framings: which exact roles a story is useful for. Never part of its versions.
    async def framings(self, story_id: UUID, user_id: UUID) -> list[StoryRoleFraming] | None: ...
    async def framings_for_user(self, user_id: UUID, role_profile_id: UUID | None = None) -> list[StoryRoleFraming]: ...
    async def set_framing(
        self, story_id: UUID, role_profile_id: UUID, user_id: UUID, values: StoryRoleFramingInput
    ) -> StoryRoleFraming | None: ...
    async def remove_framing(self, story_id: UUID, role_profile_id: UUID, user_id: UUID) -> bool | None: ...


def _payload(values: StoryCreate | StoryUpdate, *, partial: bool) -> dict[str, Any]:
    data = values.model_dump(mode="json", exclude_unset=partial)
    return data


def _unchanged(current: StoryRead, changes: dict[str, Any]) -> bool:
    return all(getattr(current, key) == value for key, value in changes.items())


class _SupabaseTable:
    """Service-role access to one table. Every query below also filters by user_id."""

    table = ""

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise StoriesUnavailable("Supabase story storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self, method: str, params: dict[str, str], json: Any = None, prefer: str | None = None, *, path: str | None = None
    ) -> list[dict[str, Any]]:
        headers = {**self._headers, **({"Prefer": prefer} if prefer else {})}
        try:
            async with pooled(10) as client:
                response = await client.request(
                    method, f"{self._url}/rest/v1/{path or self.table}", headers=headers, params=params, json=json
                )
                response.raise_for_status()
                return response.json() if response.content else []
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise StoriesUnavailable from exc


class SupabaseStoryRepository(_SupabaseTable):
    """Versions are written by database triggers in the same transaction as the story change
    (see 202609240004_story_history_archive.sql), so an edit can never land without its version."""

    table = "stories"

    async def list_for_user(self, user_id: UUID, *, archived: bool = False) -> list[StoryRead]:
        rows = await self._request(
            "GET",
            {
                "user_id": f"eq.{user_id}",
                "archived_at": "not.is.null" if archived else "is.null",
                "select": STORY_COLUMNS,
                "order": "updated_at.desc",
                "limit": "200",
            },
        )
        return [StoryRead.model_validate(row) for row in rows]

    async def get(self, story_id: UUID, user_id: UUID) -> StoryRead | None:
        rows = await self._request(
            "GET", {"id": f"eq.{story_id}", "user_id": f"eq.{user_id}", "select": STORY_COLUMNS}
        )
        return StoryRead.model_validate(rows[0]) if rows else None

    async def create(self, user_id: UUID, values: StoryCreate) -> StoryRead:
        rows = await self._request(
            "POST",
            {"select": STORY_COLUMNS},
            json={**_payload(values, partial=False), "user_id": str(user_id)},
            prefer="return=representation",
        )
        if not rows:
            raise StoriesUnavailable
        return StoryRead.model_validate(rows[0])

    async def update(self, story_id: UUID, user_id: UUID, values: StoryUpdate) -> StoryRead | None:
        current = await self.get(story_id, user_id)
        if current is None:
            return None
        if current.archived_at is not None:
            raise StoryArchived
        changes = values.model_dump(exclude_unset=True)
        if _unchanged(current, changes):
            return current  # nothing to save, so no new version
        rows = await self._request(
            "PATCH",
            {"id": f"eq.{story_id}", "user_id": f"eq.{user_id}", "archived_at": "is.null", "select": STORY_COLUMNS},
            json=_payload(values, partial=True),
            prefer="return=representation",
        )
        if not rows:
            raise StoryArchived  # archived between the read and the write
        return StoryRead.model_validate(rows[0])

    async def _set_archived(self, story_id: UUID, user_id: UUID, *, archived: bool) -> StoryRead | None:
        rows = await self._request(
            "PATCH",
            {
                "id": f"eq.{story_id}",
                "user_id": f"eq.{user_id}",
                "archived_at": "is.null" if archived else "not.is.null",
                "select": STORY_COLUMNS,
            },
            json={"archived_at": datetime.now(UTC).isoformat() if archived else None},
            prefer="return=representation",
        )
        if rows:
            return StoryRead.model_validate(rows[0])
        return await self.get(story_id, user_id)  # already in that state, or not theirs

    async def archive(self, story_id: UUID, user_id: UUID) -> StoryRead | None:
        return await self._set_archived(story_id, user_id, archived=True)

    async def restore(self, story_id: UUID, user_id: UUID) -> StoryRead | None:
        return await self._set_archived(story_id, user_id, archived=False)

    async def versions(self, story_id: UUID, user_id: UUID) -> list[StoryVersion] | None:
        if await self.get(story_id, user_id) is None:
            return None
        rows = await self._request(
            "GET",
            {"story_id": f"eq.{story_id}", "user_id": f"eq.{user_id}", "select": VERSION_COLUMNS, "order": "version.desc"},
            path="story_versions",
        )
        return [StoryVersion.model_validate(row) for row in rows]

    async def version(self, story_id: UUID, version_id: UUID, user_id: UUID) -> StoryVersion | None:
        rows = await self._request(
            "GET",
            {"id": f"eq.{version_id}", "story_id": f"eq.{story_id}", "user_id": f"eq.{user_id}", "select": VERSION_COLUMNS},
            path="story_versions",
        )
        return StoryVersion.model_validate(rows[0]) if rows else None

    async def restore_version(self, story_id: UUID, version_id: UUID, user_id: UUID) -> StoryRead | None:
        current = await self.get(story_id, user_id)
        if current is None or await self.version(story_id, version_id, user_id) is None:
            return None
        if current.archived_at is not None:
            raise StoryArchived
        rows = await self._request(
            "POST",
            {"select": STORY_COLUMNS},
            json={"p_story_id": str(story_id), "p_user_id": str(user_id), "p_version_id": str(version_id)},
            path="rpc/restore_story_version",
        )
        if not rows:
            raise StoriesUnavailable
        return StoryRead.model_validate(rows[0])


    async def framings(self, story_id: UUID, user_id: UUID) -> list[StoryRoleFraming] | None:
        if await self.get(story_id, user_id) is None:
            return None
        rows = await self._request(
            "GET",
            {"story_id": f"eq.{story_id}", "user_id": f"eq.{user_id}", "select": FRAMING_COLUMNS, "order": "created_at.asc"},
            path="story_role_framings",
        )
        return [StoryRoleFraming.model_validate(row) for row in rows]

    async def framings_for_user(self, user_id: UUID, role_profile_id: UUID | None = None) -> list[StoryRoleFraming]:
        params = {"user_id": f"eq.{user_id}", "select": FRAMING_COLUMNS, "order": "created_at.asc", "limit": "1000"}
        if role_profile_id is not None:
            params["role_profile_id"] = f"eq.{role_profile_id}"
        rows = await self._request("GET", params, path="story_role_framings")
        return [StoryRoleFraming.model_validate(row) for row in rows]

    async def set_framing(
        self, story_id: UUID, role_profile_id: UUID, user_id: UUID, values: StoryRoleFramingInput
    ) -> StoryRoleFraming | None:
        story = await self.get(story_id, user_id)
        if story is None:
            return None
        if story.archived_at is not None:
            raise StoryArchived
        rows = await self._request(
            "POST",
            {"on_conflict": "story_id,role_profile_id", "select": FRAMING_COLUMNS},
            json={
                "user_id": str(user_id),
                "story_id": str(story_id),
                "role_profile_id": str(role_profile_id),
                **values.model_dump(mode="json"),
            },
            prefer="resolution=merge-duplicates,return=representation",
            path="story_role_framings",
        )
        if not rows:
            raise StoriesUnavailable
        return StoryRoleFraming.model_validate(rows[0])

    async def remove_framing(self, story_id: UUID, role_profile_id: UUID, user_id: UUID) -> bool | None:
        story = await self.get(story_id, user_id)
        if story is None:
            return None
        if story.archived_at is not None:
            raise StoryArchived
        rows = await self._request(
            "DELETE",
            {"story_id": f"eq.{story_id}", "role_profile_id": f"eq.{role_profile_id}", "user_id": f"eq.{user_id}", "select": "id"},
            prefer="return=representation",
            path="story_role_framings",
        )
        return bool(rows)


class MemoryStoryRepository:
    """In-process stories for tests and for running without Supabase.

    Mirrors the database: a version is appended whenever content changes, never rewritten.
    """

    def __init__(self) -> None:
        self.rows: dict[UUID, StoryRead] = {}
        self.history: dict[UUID, list[StoryVersion]] = {}
        self.role_framings: dict[tuple[UUID, UUID], StoryRoleFraming] = {}

    async def list_for_user(self, user_id: UUID, *, archived: bool = False) -> list[StoryRead]:
        owned = [
            row for row in self.rows.values()
            if row.user_id == user_id and (row.archived_at is not None) == archived
        ]
        return sorted(owned, key=lambda row: row.updated_at, reverse=True)

    async def get(self, story_id: UUID, user_id: UUID) -> StoryRead | None:
        row = self.rows.get(story_id)
        return row if row and row.user_id == user_id else None

    async def create(self, user_id: UUID, values: StoryCreate) -> StoryRead:
        now = datetime.now(UTC)
        story = StoryRead(id=uuid4(), user_id=user_id, created_at=now, updated_at=now, **values.model_dump())
        self.rows[story.id] = story
        self.history[story.id] = [self._snapshot(story, StoryChangeReason.CREATED)]
        if story.role_profile_id is not None:  # the role it was written for, as the database does
            self._frame(story.id, story.role_profile_id, StoryRoleFramingInput())
        return story

    async def update(self, story_id: UUID, user_id: UUID, values: StoryUpdate) -> StoryRead | None:
        current = await self.get(story_id, user_id)
        if current is None:
            return None
        if current.archived_at is not None:
            raise StoryArchived
        changes = values.model_dump(exclude_unset=True)
        if _unchanged(current, changes):
            return current
        return self._write(current, changes, StoryChangeReason.MANUAL_EDIT)

    async def archive(self, story_id: UUID, user_id: UUID) -> StoryRead | None:
        current = await self.get(story_id, user_id)
        if current is None or current.archived_at is not None:
            return current
        return self._write(current, {"archived_at": datetime.now(UTC)}, StoryChangeReason.MANUAL_EDIT)

    async def restore(self, story_id: UUID, user_id: UUID) -> StoryRead | None:
        current = await self.get(story_id, user_id)
        if current is None or current.archived_at is None:
            return current
        return self._write(current, {"archived_at": None}, StoryChangeReason.MANUAL_EDIT)

    async def versions(self, story_id: UUID, user_id: UUID) -> list[StoryVersion] | None:
        if await self.get(story_id, user_id) is None:
            return None
        return sorted(self.history.get(story_id, []), key=lambda item: item.version, reverse=True)

    async def version(self, story_id: UUID, version_id: UUID, user_id: UUID) -> StoryVersion | None:
        return next((item for item in await self.versions(story_id, user_id) or [] if item.id == version_id), None)

    async def restore_version(self, story_id: UUID, version_id: UUID, user_id: UUID) -> StoryRead | None:
        current = await self.get(story_id, user_id)
        source = await self.version(story_id, version_id, user_id)
        if current is None or source is None:
            return None
        if current.archived_at is not None:
            raise StoryArchived
        return self._write(current, story_content(source), StoryChangeReason.RESTORED, restored_from=source.version)

    async def framings(self, story_id: UUID, user_id: UUID) -> list[StoryRoleFraming] | None:
        if await self.get(story_id, user_id) is None:
            return None
        return sorted(
            (item for (story, _), item in self.role_framings.items() if story == story_id),
            key=lambda item: item.created_at,
        )

    async def framings_for_user(self, user_id: UUID, role_profile_id: UUID | None = None) -> list[StoryRoleFraming]:
        return [
            item for (story, role), item in self.role_framings.items()
            if self.rows[story].user_id == user_id and (role_profile_id is None or role == role_profile_id)
        ]

    async def set_framing(
        self, story_id: UUID, role_profile_id: UUID, user_id: UUID, values: StoryRoleFramingInput
    ) -> StoryRoleFraming | None:
        story = await self.get(story_id, user_id)
        if story is None:
            return None
        if story.archived_at is not None:
            raise StoryArchived
        return self._frame(story_id, role_profile_id, values)

    async def remove_framing(self, story_id: UUID, role_profile_id: UUID, user_id: UUID) -> bool | None:
        story = await self.get(story_id, user_id)
        if story is None:
            return None
        if story.archived_at is not None:
            raise StoryArchived
        return self.role_framings.pop((story_id, role_profile_id), None) is not None

    def _frame(self, story_id: UUID, role_profile_id: UUID, values: StoryRoleFramingInput) -> StoryRoleFraming:
        now = datetime.now(UTC)
        existing = self.role_framings.get((story_id, role_profile_id))
        framing = StoryRoleFraming(
            id=existing.id if existing else uuid4(),
            story_id=story_id,
            role_profile_id=role_profile_id,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            **values.model_dump(),
        )
        self.role_framings[(story_id, role_profile_id)] = framing
        return framing

    def _write(
        self, current: StoryRead, changes: dict[str, Any], reason: StoryChangeReason, *, restored_from: int | None = None
    ) -> StoryRead:
        story = current.model_copy(update={**changes, "updated_at": datetime.now(UTC)})
        if story_content(story) != story_content(current):
            story = story.model_copy(update={"current_version": current.current_version + 1})
            self.history[story.id].append(self._snapshot(story, reason, restored_from))
        self.rows[story.id] = story
        return story

    @staticmethod
    def _snapshot(story: StoryRead, reason: StoryChangeReason, restored_from: int | None = None) -> StoryVersion:
        return StoryVersion(
            id=uuid4(),
            story_id=story.id,
            version=story.current_version,
            change_reason=reason,
            restored_from_version=restored_from,
            created_at=story.updated_at,
            **story_content(story),
        )


# ------------------------------------------------------------------ pressure-test readiness

class PressureResponseRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> dict[UUID, str]: ...
    async def upsert(self, user_id: UUID, claim_id: UUID, readiness: str) -> datetime: ...


class SupabasePressureResponseRepository(_SupabaseTable):
    table = "pressure_test_responses"

    async def list_for_user(self, user_id: UUID) -> dict[UUID, str]:
        rows = await self._request("GET", {"user_id": f"eq.{user_id}", "select": "claim_id,readiness"})
        return {UUID(row["claim_id"]): row["readiness"] for row in rows}

    async def upsert(self, user_id: UUID, claim_id: UUID, readiness: str) -> datetime:
        rows = await self._request(
            "POST",
            {"on_conflict": "user_id,claim_id", "select": "updated_at"},
            json={"user_id": str(user_id), "claim_id": str(claim_id), "readiness": readiness},
            prefer="resolution=merge-duplicates,return=representation",
        )
        if not rows:
            raise StoriesUnavailable
        return datetime.fromisoformat(rows[0]["updated_at"])


class MemoryPressureResponseRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, UUID], str] = {}

    async def list_for_user(self, user_id: UUID) -> dict[UUID, str]:
        return {claim: value for (owner, claim), value in self.rows.items() if owner == user_id}

    async def upsert(self, user_id: UUID, claim_id: UUID, readiness: str) -> datetime:
        self.rows[(user_id, claim_id)] = readiness
        return datetime.now(UTC)
