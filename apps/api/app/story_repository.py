from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

import httpx

from .config import Settings
from .http_pool import pooled
from .story_models import StoryCreate, StoryRead, StoryUpdate

STORY_COLUMNS = (
    "id,user_id,title,themes,role_profile_id,source_claim_id,source_document_id,source_text,"
    "origin,situation,ownership,actions,reasoning,trade_offs,outcome,measurable_result,"
    "learning,do_differently,created_at,updated_at"
)


class StoriesUnavailable(Exception):
    pass


class StoryRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[StoryRead]: ...
    async def get(self, story_id: UUID, user_id: UUID) -> StoryRead | None: ...
    async def create(self, user_id: UUID, values: StoryCreate) -> StoryRead: ...
    async def update(self, story_id: UUID, user_id: UUID, values: StoryUpdate) -> StoryRead | None: ...
    async def delete(self, story_id: UUID, user_id: UUID) -> bool: ...


def _payload(values: StoryCreate | StoryUpdate, *, partial: bool) -> dict[str, Any]:
    data = values.model_dump(mode="json", exclude_unset=partial)
    return data


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

    async def _request(self, method: str, params: dict[str, str], json: Any = None, prefer: str | None = None) -> list[dict[str, Any]]:
        headers = {**self._headers, **({"Prefer": prefer} if prefer else {})}
        try:
            async with pooled(10) as client:
                response = await client.request(
                    method, f"{self._url}/rest/v1/{self.table}", headers=headers, params=params, json=json
                )
                response.raise_for_status()
                return response.json() if response.content else []
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise StoriesUnavailable from exc


class SupabaseStoryRepository(_SupabaseTable):
    table = "stories"

    async def list_for_user(self, user_id: UUID) -> list[StoryRead]:
        rows = await self._request(
            "GET",
            {"user_id": f"eq.{user_id}", "select": STORY_COLUMNS, "order": "updated_at.desc", "limit": "200"},
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
        payload = _payload(values, partial=True)
        if not payload:
            return await self.get(story_id, user_id)
        rows = await self._request(
            "PATCH",
            {"id": f"eq.{story_id}", "user_id": f"eq.{user_id}", "select": STORY_COLUMNS},
            json=payload,
            prefer="return=representation",
        )
        return StoryRead.model_validate(rows[0]) if rows else None

    async def delete(self, story_id: UUID, user_id: UUID) -> bool:
        rows = await self._request(
            "DELETE",
            {"id": f"eq.{story_id}", "user_id": f"eq.{user_id}", "select": "id"},
            prefer="return=representation",
        )
        return bool(rows)


class MemoryStoryRepository:
    """In-process stories for tests and for running without Supabase."""

    def __init__(self) -> None:
        self.rows: dict[UUID, StoryRead] = {}

    async def list_for_user(self, user_id: UUID) -> list[StoryRead]:
        owned = [row for row in self.rows.values() if row.user_id == user_id]
        return sorted(owned, key=lambda row: row.updated_at, reverse=True)

    async def get(self, story_id: UUID, user_id: UUID) -> StoryRead | None:
        row = self.rows.get(story_id)
        return row if row and row.user_id == user_id else None

    async def create(self, user_id: UUID, values: StoryCreate) -> StoryRead:
        now = datetime.now(UTC)
        story = StoryRead(id=uuid4(), user_id=user_id, created_at=now, updated_at=now, **values.model_dump())
        self.rows[story.id] = story
        return story

    async def update(self, story_id: UUID, user_id: UUID, values: StoryUpdate) -> StoryRead | None:
        current = await self.get(story_id, user_id)
        if current is None:
            return None
        changes = values.model_dump(exclude_unset=True)
        story = current.model_copy(update={**changes, "updated_at": datetime.now(UTC)})
        self.rows[story_id] = story
        return story

    async def delete(self, story_id: UUID, user_id: UUID) -> bool:
        if await self.get(story_id, user_id) is None:
            return False
        del self.rows[story_id]
        return True


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
