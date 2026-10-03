from __future__ import annotations
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4
from .config import Settings
from .dig_deeper_models import DigDeeperResponseCreate, DigDeeperResponseRead

class DigDeeperRepository(Protocol):
    async def list_for_context(self, user_id: UUID, role_profile_id: UUID, claim_id: UUID) -> list[DigDeeperResponseRead]: ...
    async def upsert(self, user_id: UUID, value: DigDeeperResponseCreate) -> DigDeeperResponseRead: ...

class MemoryDigDeeperRepository:
    def __init__(self) -> None: self.rows: dict[tuple[UUID, UUID, str], DigDeeperResponseRead] = {}
    async def list_for_context(self, user_id, role_profile_id, claim_id):
        return [r for r in self.rows.values() if r.user_id == user_id and r.role_profile_id == role_profile_id and r.claim_id == claim_id]
    async def upsert(self, user_id, value):
        key = (user_id, value.claim_id, value.question_kind)
        now = datetime.now(UTC); old = self.rows.get(key)
        row = DigDeeperResponseRead(id=old.id if old else uuid4(), user_id=user_id, story_id=old.story_id if old else None, created_at=old.created_at if old else now, updated_at=now, **value.model_dump())
        self.rows[key] = row
        return row

class SupabaseDigDeeperRepository:
    def __init__(self, settings: Settings) -> None:
        self.url = settings.next_public_supabase_url.rstrip("/")
        self.headers = {"apikey": settings.supabase_service_role_key, "Authorization": f"Bearer {settings.supabase_service_role_key}", "Content-Type": "application/json"}
    async def list_for_context(self, user_id, role_profile_id, claim_id):
        from .http_pool import pooled
        async with pooled(10) as client:
            response = await client.get(f"{self.url}/rest/v1/dig_deeper_responses", headers=self.headers, params={"user_id": f"eq.{user_id}", "role_profile_id": f"eq.{role_profile_id}", "claim_id": f"eq.{claim_id}", "select": "*", "order": "created_at.asc"})
            response.raise_for_status(); return [DigDeeperResponseRead.model_validate(r) for r in response.json()]
    async def upsert(self, user_id, value):
        from .http_pool import pooled
        body = {"user_id": str(user_id), **value.model_dump(mode="json")}
        async with pooled(10) as client:
            response = await client.post(f"{self.url}/rest/v1/dig_deeper_responses", headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}, params={"on_conflict": "user_id,role_profile_id,claim_id,question_kind", "select": "*"}, json=body)
            response.raise_for_status(); return DigDeeperResponseRead.model_validate(response.json()[0])
