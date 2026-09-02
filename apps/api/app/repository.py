from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

import httpx

from .config import Settings
from .schemas import Phase, SessionCreate, SessionEventRead, SessionRead, SessionStatus


class SessionRepository(Protocol):
    async def create(
        self,
        user_id: UUID,
        payload: SessionCreate,
        *,
        total_time_budget_seconds: int = 1200,
        phase_time_budget_seconds: int = 180,
    ) -> SessionRead: ...
    async def get(self, session_id: UUID, user_id: UUID) -> SessionRead | None: ...
    async def update(
        self, session_id: UUID, user_id: UUID, values: dict
    ) -> SessionRead | None: ...
    async def apply_state_change(
        self,
        session: SessionRead,
        values: dict,
        event_type: str,
        payload: dict,
    ) -> SessionRead | None: ...
    async def record_event(
        self, session_id: UUID, user_id: UUID, event_type: str, payload: dict
    ) -> SessionEventRead: ...
    async def list_events(
        self, session_id: UUID, user_id: UUID
    ) -> list[SessionEventRead]: ...


class MemorySessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, SessionRead] = {}

        self.events: dict[UUID, list[SessionEventRead]] = {}

    async def create(
        self,
        user_id: UUID,
        payload: SessionCreate,
        *,
        total_time_budget_seconds: int = 1200,
        phase_time_budget_seconds: int = 180,
    ) -> SessionRead:
        now = datetime.now(UTC)
        session = SessionRead(
            id=uuid4(),
            user_id=user_id,
            target_role=payload.target_role,
            jd_text=payload.jd_text,
            status=SessionStatus.CREATED,
            phase=Phase.INTRO,
            completion_pct=0,
            synthetic=False,
            created_at=now,
            updated_at=now,
            phase_started_at=now,
            phase_time_budget_seconds=phase_time_budget_seconds,
            total_time_budget_seconds=total_time_budget_seconds,
            elapsed_seconds=0,
            current_probe_count=0,
            total_questions=0,
            recovery_count=0,
        )
        self.sessions[session.id] = session
        await self.record_event(session.id, user_id, "SESSION_CREATED", {})
        return session

    async def get(self, session_id: UUID, user_id: UUID) -> SessionRead | None:
        session = self.sessions.get(session_id)
        return session if session and session.user_id == user_id else None

    async def update(
        self, session_id: UUID, user_id: UUID, values: dict
    ) -> SessionRead | None:
        session = await self.get(session_id, user_id)
        if not session:
            return None
        updated = session.model_copy(update={**values, "updated_at": datetime.now(UTC)})
        self.sessions[session_id] = updated
        return updated

    async def apply_state_change(
        self,
        session: SessionRead,
        values: dict,
        event_type: str,
        payload: dict,
    ) -> SessionRead | None:
        current = await self.get(session.id, session.user_id)
        if current is None or current.updated_at != session.updated_at:
            return None
        updated = await self.update(session.id, session.user_id, values)
        if updated:
            await self.record_event(session.id, session.user_id, event_type, payload)
        return updated

    async def record_event(
        self, session_id: UUID, user_id: UUID, event_type: str, payload: dict
    ) -> SessionEventRead:
        event = SessionEventRead(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            event_type=event_type,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        self.events.setdefault(session_id, []).append(event)
        return event

    async def list_events(
        self, session_id: UUID, user_id: UUID
    ) -> list[SessionEventRead]:
        session = await self.get(session_id, user_id)
        return list(self.events.get(session_id, [])) if session else []


class SupabaseSessionRepository:
    def __init__(self, settings: Settings) -> None:
        self.url = settings.next_public_supabase_url.rstrip("/")
        self.headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def create(
        self,
        user_id: UUID,
        payload: SessionCreate,
        *,
        total_time_budget_seconds: int = 1200,
        phase_time_budget_seconds: int = 180,
    ) -> SessionRead:
        body = {
            "user_id": str(user_id),
            **payload.model_dump(),
            "phase": "INTRO",
            "status": "CREATED",
            "total_time_budget_seconds": total_time_budget_seconds,
            "phase_time_budget_seconds": phase_time_budget_seconds,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.url}/rest/v1/sessions",
                headers={**self.headers, "Prefer": "return=representation"},
                json=body,
            )
            response.raise_for_status()
            session = SessionRead.model_validate(response.json()[0])
        await self.record_event(session.id, user_id, "SESSION_CREATED", {})
        return session

    async def get(self, session_id: UUID, user_id: UUID) -> SessionRead | None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.url}/rest/v1/sessions",
                headers=self.headers,
                params={
                    "id": f"eq.{session_id}",
                    "user_id": f"eq.{user_id}",
                    "select": "*",
                },
            )
            response.raise_for_status()
            rows = response.json()
            return SessionRead.model_validate(rows[0]) if rows else None

    async def update(
        self, session_id: UUID, user_id: UUID, values: dict
    ) -> SessionRead | None:
        serialised = {
            key: value.value
            if hasattr(value, "value")
            else value.model_dump(mode="json")
            if hasattr(value, "model_dump")
            else value
            for key, value in values.items()
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.patch(
                f"{self.url}/rest/v1/sessions",
                headers={**self.headers, "Prefer": "return=representation"},
                params={"id": f"eq.{session_id}", "user_id": f"eq.{user_id}"},
                json=serialised,
            )
            response.raise_for_status()
            rows = response.json()
            return SessionRead.model_validate(rows[0]) if rows else None

    async def apply_state_change(
        self,
        session: SessionRead,
        values: dict,
        event_type: str,
        payload: dict,
    ) -> SessionRead | None:
        serialised = {
            key: value.value
            if hasattr(value, "value")
            else value.isoformat()
            if isinstance(value, datetime)
            else value
            for key, value in values.items()
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.url}/rest/v1/rpc/apply_interview_state_change",
                headers=self.headers,
                json={
                    "p_session_id": str(session.id),
                    "p_user_id": str(session.user_id),
                    "p_expected_updated_at": session.updated_at.isoformat(),
                    "p_values": serialised,
                    "p_event_type": event_type,
                    "p_event_payload": payload,
                },
            )
            if response.status_code == 400:
                return None
            response.raise_for_status()
            rows = response.json()
            return SessionRead.model_validate(rows[0]) if rows else None

    async def record_event(
        self, session_id: UUID, user_id: UUID, event_type: str, payload: dict
    ) -> SessionEventRead:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.url}/rest/v1/session_events",
                headers={**self.headers, "Prefer": "return=representation"},
                json={
                    "session_id": str(session_id),
                    "user_id": str(user_id),
                    "event_type": event_type,
                    "payload": payload,
                },
            )
            response.raise_for_status()
            return SessionEventRead.model_validate(response.json()[0])

    async def list_events(
        self, session_id: UUID, user_id: UUID
    ) -> list[SessionEventRead]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.url}/rest/v1/session_events",
                headers=self.headers,
                params={
                    "session_id": f"eq.{session_id}",
                    "user_id": f"eq.{user_id}",
                    "select": "*",
                    "order": "created_at.asc",
                },
            )
            response.raise_for_status()
            return [SessionEventRead.model_validate(row) for row in response.json()]

