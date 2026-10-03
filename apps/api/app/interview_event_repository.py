"""Storage for interview events and debriefs. Every method is owner-scoped by user_id."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

import httpx

from .config import Settings
from .http_pool import pooled
from .interview_event_models import (
    InterviewDebrief,
    InterviewDebriefWrite,
    InterviewEventCreate,
    InterviewEventRecord,
    InterviewEventUpdate,
)


class InterviewEventsUnavailable(Exception):
    pass


class InterviewEventRepository(Protocol):
    async def list_for_role(self, user_id: UUID, role_profile_id: UUID) -> list[InterviewEventRecord]: ...
    async def list_for_user(self, user_id: UUID) -> list[InterviewEventRecord]: ...
    async def get(self, event_id: UUID, user_id: UUID) -> InterviewEventRecord | None: ...
    async def create(self, user_id: UUID, role_profile_id: UUID, values: InterviewEventCreate) -> InterviewEventRecord: ...
    async def update(self, event_id: UUID, user_id: UUID, values: InterviewEventUpdate) -> InterviewEventRecord | None: ...
    async def delete(self, event_id: UUID, user_id: UUID) -> bool: ...
    async def get_debrief(self, event_id: UUID, user_id: UUID) -> InterviewDebrief | None: ...
    async def put_debrief(self, event_id: UUID, user_id: UUID, values: InterviewDebriefWrite) -> InterviewDebrief: ...


class MemoryInterviewEventRepository:
    def __init__(self) -> None:
        self.events: dict[UUID, InterviewEventRecord] = {}
        self.debriefs: dict[UUID, tuple[UUID, InterviewDebrief]] = {}  # event id -> (owner, debrief)

    def _view(self, row: InterviewEventRecord) -> InterviewEventRecord:
        return row.model_copy(update={"has_debrief": row.id in self.debriefs})

    def _owned(self, event_id: UUID, user_id: UUID) -> InterviewEventRecord | None:
        row = self.events.get(event_id)
        return row if row is not None and row.user_id == user_id else None

    async def list_for_role(self, user_id, role_profile_id):
        rows = [r for r in self.events.values() if r.user_id == user_id and r.role_profile_id == role_profile_id]
        return [self._view(r) for r in sorted(rows, key=lambda r: r.scheduled_for)]

    async def list_for_user(self, user_id: UUID) -> list[InterviewEventRecord]:
        rows = [r for r in self.events.values() if r.user_id == user_id]
        return [self._view(r) for r in sorted(rows, key=lambda r: r.scheduled_for)]

    async def get(self, event_id, user_id):
        row = self._owned(event_id, user_id)
        return self._view(row) if row else None

    async def create(self, user_id, role_profile_id, values):
        now = datetime.now(UTC)
        row = InterviewEventRecord(
            id=uuid4(), user_id=user_id, role_profile_id=role_profile_id, created_at=now, updated_at=now, **values.model_dump()
        )
        self.events[row.id] = row
        return self._view(row)

    async def update(self, event_id, user_id, values):
        row = self._owned(event_id, user_id)
        if row is None:
            return None
        changes = {key: value for key, value in values.model_dump(exclude_unset=True).items()
                   if value is not None or key == "company_label"}
        row = row.model_copy(update={**changes, "updated_at": datetime.now(UTC)})
        self.events[event_id] = row
        return self._view(row)

    async def delete(self, event_id, user_id):
        if self._owned(event_id, user_id) is None:
            return False
        del self.events[event_id]
        self.debriefs.pop(event_id, None)  # cascade, as the foreign key does
        return True

    async def get_debrief(self, event_id, user_id):
        found = self.debriefs.get(event_id)
        return found[1] if found and found[0] == user_id else None

    async def put_debrief(self, event_id, user_id, values):
        now = datetime.now(UTC)
        old = await self.get_debrief(event_id, user_id)
        debrief = InterviewDebrief(
            id=old.id if old else uuid4(), interview_event_id=event_id,
            created_at=old.created_at if old else now, updated_at=now, **values.model_dump(),
        )
        self.debriefs[event_id] = (user_id, debrief)
        return debrief


EVENT_SELECT = "id,user_id,role_profile_id,scheduled_for,round_kind,company_label,created_at,updated_at,interview_debriefs(id)"
DEBRIEF_SELECT = "id,interview_event_id,questions_asked,feeling,outcome,notes,created_at,updated_at"


def _event(row: dict[str, Any]) -> InterviewEventRecord:
    embedded = row.pop("interview_debriefs", None)
    return InterviewEventRecord.model_validate({**row, "has_debrief": bool(embedded)})


class SupabaseInterviewEventRepository:
    """Service-role access. Every query also filters by user_id."""

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise InterviewEventsUnavailable("Supabase interview storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, table: str, params: dict[str, str], json: Any = None, prefer: str | None = None) -> list[dict[str, Any]]:
        headers = {**self._headers, **({"Prefer": prefer} if prefer else {})}
        try:
            async with pooled(10) as client:
                response = await client.request(method, f"{self._url}/rest/v1/{table}", headers=headers, params=params, json=json)
                response.raise_for_status()
                return response.json() if response.content else []
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise InterviewEventsUnavailable from exc

    async def list_for_role(self, user_id, role_profile_id):
        rows = await self._request("GET", "interview_events", {
            "user_id": f"eq.{user_id}", "role_profile_id": f"eq.{role_profile_id}",
            "select": EVENT_SELECT, "order": "scheduled_for.asc",
        })
        return [_event(row) for row in rows]

    async def list_for_user(self, user_id: UUID) -> list[InterviewEventRecord]:
        rows = await self._request("GET", "interview_events", {
            "user_id": f"eq.{user_id}", "select": EVENT_SELECT, "order": "scheduled_for.asc",
        })
        return [_event(row) for row in rows]

    async def get(self, event_id, user_id):
        rows = await self._request("GET", "interview_events", {"id": f"eq.{event_id}", "user_id": f"eq.{user_id}", "select": EVENT_SELECT})
        return _event(rows[0]) if rows else None

    async def create(self, user_id, role_profile_id, values):
        body = {"user_id": str(user_id), "role_profile_id": str(role_profile_id), **values.model_dump(mode="json")}
        rows = await self._request("POST", "interview_events", {"select": EVENT_SELECT}, body, "return=representation")
        return _event(rows[0])

    async def update(self, event_id, user_id, values):
        changes = {key: value for key, value in values.model_dump(mode="json", exclude_unset=True).items()
                   if value is not None or key == "company_label"}
        if not changes:
            return await self.get(event_id, user_id)
        rows = await self._request(
            "PATCH", "interview_events", {"id": f"eq.{event_id}", "user_id": f"eq.{user_id}", "select": EVENT_SELECT},
            changes, "return=representation",
        )
        return _event(rows[0]) if rows else None

    async def delete(self, event_id, user_id):
        rows = await self._request(
            "DELETE", "interview_events", {"id": f"eq.{event_id}", "user_id": f"eq.{user_id}", "select": "id"},
            prefer="return=representation",
        )
        return bool(rows)

    async def get_debrief(self, event_id, user_id):
        rows = await self._request("GET", "interview_debriefs", {
            "interview_event_id": f"eq.{event_id}", "user_id": f"eq.{user_id}", "select": DEBRIEF_SELECT,
        })
        return InterviewDebrief.model_validate(rows[0]) if rows else None

    async def put_debrief(self, event_id, user_id, values):
        body = {"user_id": str(user_id), "interview_event_id": str(event_id), **values.model_dump(mode="json")}
        rows = await self._request(
            "POST", "interview_debriefs", {"on_conflict": "interview_event_id", "select": DEBRIEF_SELECT},
            body, "resolution=merge-duplicates,return=representation",
        )
        return InterviewDebrief.model_validate(rows[0])
