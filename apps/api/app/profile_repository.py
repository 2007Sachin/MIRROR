from __future__ import annotations

from typing import Protocol
from uuid import UUID

import httpx

from .http_pool import pooled

from .auth import AuthenticatedUser
from .config import Settings
from .schemas import ProfileRead


class ProfileUnavailable(Exception):
    pass


class ProfileRepository(Protocol):
    async def reconcile(self, identity: AuthenticatedUser) -> ProfileRead: ...
    async def get(self, user_id: UUID) -> ProfileRead | None: ...
    async def update_full_name(self, user_id: UUID, full_name: str) -> ProfileRead: ...


class SupabaseProfileRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise ProfileUnavailable("Supabase profile storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def reconcile(self, identity: AuthenticatedUser) -> ProfileRead:
        params = {"id": f"eq.{identity.id}", "select": "id,full_name,email"}
        try:
            async with pooled(10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/profiles",
                    headers=self._headers,
                    params=params,
                )
                response.raise_for_status()
                rows = response.json()
                if rows:
                    profile = ProfileRead.model_validate(rows[0])
                    if profile.email != identity.email:
                        updated = await client.patch(
                            f"{self._url}/rest/v1/profiles",
                            headers={
                                **self._headers,
                                "Prefer": "return=representation",
                            },
                            params=params,
                            json={"email": identity.email},
                        )
                        updated.raise_for_status()
                        return ProfileRead.model_validate(updated.json()[0])
                    return profile

                created = await client.post(
                    f"{self._url}/rest/v1/profiles",
                    headers={**self._headers, "Prefer": "return=representation"},
                    json={
                        "id": str(identity.id),
                        "email": identity.email,
                        "full_name": identity.full_name,
                    },
                )
                created.raise_for_status()
                return ProfileRead.model_validate(created.json()[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise ProfileUnavailable from exc

    async def get(self, user_id: UUID) -> ProfileRead | None:
        try:
            async with pooled(10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/profiles",
                    headers=self._headers,
                    params={"id": f"eq.{user_id}", "select": "id,full_name,email", "limit": "1"},
                )
                response.raise_for_status()
                rows = response.json()
                return ProfileRead.model_validate(rows[0]) if rows else None
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise ProfileUnavailable from exc

    async def update_full_name(self, user_id: UUID, full_name: str) -> ProfileRead:
        try:
            async with pooled(10) as client:
                response = await client.patch(
                    f"{self._url}/rest/v1/profiles",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"id": f"eq.{user_id}", "select": "id,full_name,email"},
                    json={"full_name": full_name},
                )
                response.raise_for_status()
                rows = response.json()
                if not rows:
                    raise ProfileUnavailable
                return ProfileRead.model_validate(rows[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise ProfileUnavailable from exc

