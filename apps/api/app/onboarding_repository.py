from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import httpx

from .http_pool import pooled

from .config import Settings
from .schemas import OnboardingRead, onboarding_is_complete


def ready_to_complete(onboarding: OnboardingRead) -> bool:
    """Setup can finish once a role and a resume are in place.

    A practice session is never required: one is created only when the person
    chooses to start practising from their plan.
    """
    return onboarding_is_complete(onboarding) or bool(
        onboarding.target_role
        and onboarding.onboarding_role_profile_id
        and onboarding.onboarding_resume_document_id
    )


ONBOARDING_COLUMNS = (
    "career_stage,career_intent,target_role,interview_timeline,"
    "preferred_language,college_id,target_company,onboarding_step,"
    "onboarding_resume_document_id,onboarding_role_brief_document_id,"
    "onboarding_role_brief_skipped,onboarding_role_profile_id,"
    "onboarding_session_id,inquiry_depth,onboarding_completed"
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
            async with pooled(10) as client:
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

    async def role_preference(self, user_id: UUID) -> tuple[UUID | None, UUID | None]:
        """(current_role_profile_id, onboarding_role_profile_id) for this person; either may be null."""
        try:
            async with pooled(10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/profiles",
                    headers=self._headers,
                    params={"id": f"eq.{user_id}", "select": "current_role_profile_id,onboarding_role_profile_id"},
                )
                response.raise_for_status()
                rows = response.json()
            if not rows:
                return None, None
            row = rows[0]
            return (
                UUID(row["current_role_profile_id"]) if row.get("current_role_profile_id") else None,
                UUID(row["onboarding_role_profile_id"]) if row.get("onboarding_role_profile_id") else None,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise OnboardingUnavailable from exc

    async def set_current_role(self, user_id: UUID, role_profile_id: UUID) -> None:
        """Store the active role. The caller has already checked the role is this person's."""
        try:
            async with pooled(10) as client:
                response = await client.patch(
                    f"{self._url}/rest/v1/profiles",
                    headers={**self._headers, "Prefer": "return=minimal"},
                    params={"id": f"eq.{user_id}"},
                    json={"current_role_profile_id": str(role_profile_id)},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
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
            async with pooled(10) as client:
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

