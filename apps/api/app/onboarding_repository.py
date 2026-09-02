from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import httpx

from .config import Settings
from .schemas import OnboardingRead


ONBOARDING_COLUMNS = (
    "career_stage,career_intent,target_role,interview_timeline,"
    "preferred_language,college_id,onboarding_completed"
)


class OnboardingUnavailable(Exception):
    pass


class OnboardingRepository(Protocol):
    async def get(self, user_id: UUID) -> OnboardingRead: ...
    async def update(self, user_id: UUID, values: dict[str, Any]) -> OnboardingRead: ...


class SupabaseOnboardingRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise OnboardingUnavailable("Supabase onboarding storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def get(self, user_id: UUID) -> OnboardingRead:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/profiles",
                    headers=self._headers,
                    params={"id": f"eq.{user_id}", "select": ONBOARDING_COLUMNS},
                )
                response.raise_for_status()
                rows = response.json()
                if not rows:
                    raise OnboardingUnavailable
                return OnboardingRead.model_validate(rows[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable from exc

    async def update(self, user_id: UUID, values: dict[str, Any]) -> OnboardingRead:
        serialised = {
            key: value.value
            if hasattr(value, "value")
            else str(value)
            if isinstance(value, UUID)
            else value
            for key, value in values.items()
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.patch(
                    f"{self._url}/rest/v1/profiles",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"id": f"eq.{user_id}", "select": ONBOARDING_COLUMNS},
                    json=serialised,
                )
                response.raise_for_status()
                rows = response.json()
                if not rows:
                    raise OnboardingUnavailable
                return OnboardingRead.model_validate(rows[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable from exc

