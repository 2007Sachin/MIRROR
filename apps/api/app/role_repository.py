from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import httpx

from .config import Settings
from .role_models import (
    RoleAgentOutput,
    RoleAnalysisResponse,
    RoleAnalysisVersion,
    RoleProfileRead,
    RoleSourceType,
    StoredRoleCompetency,
)


PROFILE_COLUMNS = (
    "id,user_id,target_role,canonical_role,seniority,source_type,source_document_id,"
    "current_analysis_version_id,created_at,updated_at"
)
VERSION_COLUMNS = (
    "id,role_profile_id,user_id,version,status,source_type,source_document_id,model,"
    "prompt_version,analysis_version,output,execution_id,error_type,created_at,completed_at"
)
COMPETENCY_COLUMNS = (
    "id,role_profile_id,analysis_version_id,name,category,importance_weight,"
    "expected_level,source_type,source_reference,confidence"
)


class RoleAnalysisUnavailable(Exception):
    pass


class RoleProfileNotFound(Exception):
    pass


class RoleAnalysisRepository(Protocol):
    async def create_profile(
        self,
        user_id: UUID,
        target_role: str,
        source_type: RoleSourceType,
        source_document_id: UUID | None,
    ) -> RoleProfileRead: ...

    async def get_profile(
        self, profile_id: UUID, user_id: UUID
    ) -> RoleProfileRead | None: ...

    async def begin(
        self,
        profile_id: UUID,
        user_id: UUID,
        *,
        source_type: RoleSourceType,
        source_document_id: UUID | None,
        model: str,
        prompt_version: str,
        analysis_version: str,
    ) -> tuple[RoleAnalysisVersion, bool]: ...

    async def complete(
        self,
        analysis_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        output: RoleAgentOutput,
    ) -> RoleAnalysisResponse: ...

    async def fail(
        self,
        analysis_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        error_type: str,
    ) -> RoleAnalysisResponse: ...

    async def get(
        self, profile_id: UUID, user_id: UUID
    ) -> RoleAnalysisResponse | None: ...

    async def competencies(
        self, profile_id: UUID, user_id: UUID
    ) -> list[StoredRoleCompetency] | None: ...


class SupabaseRoleAnalysisRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise RoleAnalysisUnavailable(
                "Supabase role analysis storage is not configured"
            )
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def create_profile(
        self,
        user_id: UUID,
        target_role: str,
        source_type: RoleSourceType,
        source_document_id: UUID | None,
    ) -> RoleProfileRead:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/role_profiles",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"select": PROFILE_COLUMNS},
                    json={
                        "user_id": str(user_id),
                        "target_role": target_role,
                        "source_type": source_type.value,
                        "source_document_id": (
                            str(source_document_id) if source_document_id else None
                        ),
                    },
                )
                response.raise_for_status()
                return RoleProfileRead.model_validate(response.json()[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise RoleAnalysisUnavailable from exc

    async def get_profile(
        self, profile_id: UUID, user_id: UUID
    ) -> RoleProfileRead | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/role_profiles",
                    headers=self._headers,
                    params={
                        "id": f"eq.{profile_id}",
                        "user_id": f"eq.{user_id}",
                        "select": PROFILE_COLUMNS,
                    },
                )
                response.raise_for_status()
                rows = response.json()
                return RoleProfileRead.model_validate(rows[0]) if rows else None
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise RoleAnalysisUnavailable from exc

    async def begin(
        self,
        profile_id: UUID,
        user_id: UUID,
        *,
        source_type: RoleSourceType,
        source_document_id: UUID | None,
        model: str,
        prompt_version: str,
        analysis_version: str,
    ) -> tuple[RoleAnalysisVersion, bool]:
        processing = await self._get_version(profile_id, user_id, status="PROCESSING")
        if processing:
            return processing, False
        latest = await self._get_version(profile_id, user_id)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/role_analysis_versions",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"select": VERSION_COLUMNS},
                    json={
                        "role_profile_id": str(profile_id),
                        "user_id": str(user_id),
                        "version": (latest.version if latest else 0) + 1,
                        "status": "PROCESSING",
                        "source_type": source_type.value,
                        "source_document_id": (
                            str(source_document_id) if source_document_id else None
                        ),
                        "model": model,
                        "prompt_version": prompt_version,
                        "analysis_version": analysis_version,
                    },
                )
                if response.status_code == 409:
                    concurrent = await self._get_version(
                        profile_id, user_id, status="PROCESSING"
                    )
                    if concurrent:
                        return concurrent, False
                response.raise_for_status()
                return RoleAnalysisVersion.model_validate(response.json()[0]), True
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise RoleAnalysisUnavailable from exc

    async def complete(
        self,
        analysis_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        output: RoleAgentOutput,
    ) -> RoleAnalysisResponse:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/rpc/complete_role_analysis",
                    headers=self._headers,
                    json={
                        "p_analysis_id": str(analysis_id),
                        "p_user_id": str(user_id),
                        "p_execution_id": str(execution_id),
                        "p_output": output.model_dump(mode="json"),
                    },
                )
                response.raise_for_status()
                version = RoleAnalysisVersion.model_validate(response.json()[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise RoleAnalysisUnavailable from exc
        hydrated = await self.get(version.role_profile_id, user_id)
        if hydrated is None:
            raise RoleAnalysisUnavailable("completed role analysis could not be read")
        return hydrated

    async def fail(
        self,
        analysis_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        error_type: str,
    ) -> RoleAnalysisResponse:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.patch(
                    f"{self._url}/rest/v1/role_analysis_versions",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={
                        "id": f"eq.{analysis_id}",
                        "user_id": f"eq.{user_id}",
                        "status": "eq.PROCESSING",
                        "select": VERSION_COLUMNS,
                    },
                    json={
                        "status": "FAILED",
                        "execution_id": str(execution_id),
                        "error_type": error_type,
                        "completed_at": datetime.now(UTC).isoformat(),
                    },
                )
                response.raise_for_status()
                version = RoleAnalysisVersion.model_validate(response.json()[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise RoleAnalysisUnavailable from exc
        profile = await self.get_profile(version.role_profile_id, user_id)
        if profile is None:
            raise RoleProfileNotFound
        return RoleAnalysisResponse(
            **profile.model_dump(), latest_analysis=version, competencies=[]
        )

    async def get(self, profile_id: UUID, user_id: UUID) -> RoleAnalysisResponse | None:
        profile = await self.get_profile(profile_id, user_id)
        if profile is None:
            return None
        latest = await self._get_version(profile_id, user_id)
        competencies = (
            await self._competencies_for_version(profile_id, latest.id, user_id)
            if latest and latest.status == "COMPLETED"
            else []
        )
        return RoleAnalysisResponse(
            **profile.model_dump(), latest_analysis=latest, competencies=competencies
        )

    async def competencies(
        self, profile_id: UUID, user_id: UUID
    ) -> list[StoredRoleCompetency] | None:
        profile = await self.get_profile(profile_id, user_id)
        if profile is None:
            return None
        if profile.current_analysis_version_id is None:
            return []
        return await self._competencies_for_version(
            profile_id, profile.current_analysis_version_id, user_id
        )

    async def _get_version(
        self, profile_id: UUID, user_id: UUID, *, status: str | None = None
    ) -> RoleAnalysisVersion | None:
        params = {
            "role_profile_id": f"eq.{profile_id}",
            "user_id": f"eq.{user_id}",
            "select": VERSION_COLUMNS,
            "order": "version.desc",
            "limit": "1",
        }
        if status:
            params["status"] = f"eq.{status}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/role_analysis_versions",
                    headers=self._headers,
                    params=params,
                )
                response.raise_for_status()
                rows = response.json()
                return RoleAnalysisVersion.model_validate(rows[0]) if rows else None
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise RoleAnalysisUnavailable from exc

    async def _competencies_for_version(
        self, profile_id: UUID, version_id: UUID, user_id: UUID
    ) -> list[StoredRoleCompetency]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/role_competencies",
                    headers=self._headers,
                    params={
                        "role_profile_id": f"eq.{profile_id}",
                        "analysis_version_id": f"eq.{version_id}",
                        "user_id": f"eq.{user_id}",
                        "select": COMPETENCY_COLUMNS,
                        "order": "importance_weight.desc",
                    },
                )
                response.raise_for_status()
                return [
                    StoredRoleCompetency.model_validate(row) for row in response.json()
                ]
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise RoleAnalysisUnavailable from exc

