from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .assessment_pipeline_repository import SupabaseAssessmentPipelineRepository
from .config import Settings
from .dashboard_models import DashboardDiagnostic
from .skeptic_repository import SkepticPersistenceUnavailable, SupabaseSkepticRepository


class DashboardUnavailable(Exception):
    pass


class DashboardRepository(Protocol):
    async def list_for_user(
        self, user_id: UUID, *, limit: int = 25
    ) -> list[DashboardDiagnostic]: ...


class SupabaseDashboardRepository(SupabaseSkepticRepository):
    def __init__(self, settings: Settings) -> None:
        try:
            super().__init__(settings)
        except SkepticPersistenceUnavailable as exc:
            raise DashboardUnavailable("dashboard persistence is not configured") from exc

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 25
    ) -> list[DashboardDiagnostic]:
        try:
            sessions = await self._get(
                "sessions",
                {
                    "user_id": f"eq.{user_id}",
                    "select": "id,target_role,status,phase,created_at,updated_at,completed_at",
                    "order": "updated_at.desc",
                    "limit": str(limit),
                },
            )
            if not sessions:
                return []
            session_ids = [UUID(str(row["id"])) for row in sessions]
            profiles = await self._get(
                "profiles",
                {
                    "id": f"eq.{user_id}",
                    "select": "target_company,onboarding_session_id",
                    "limit": "1",
                },
            )
            keys = ",".join(f"{session_id}:v1" for session_id in session_ids)
            jobs = await self._get(
                "jobs",
                {
                    "job_type": "eq.POST_SESSION_ASSESSMENT",
                    "dedupe_key": f"in.({keys})",
                    "select": "*",
                    "limit": str(limit),
                },
            )
            results = await self._get(
                "session_results",
                {
                    "session_id": f"in.({','.join(str(value) for value in session_ids)})",
                    "select": "session_id",
                    "limit": str(limit),
                },
            )
        except Exception as exc:
            raise DashboardUnavailable("dashboard data could not be loaded") from exc

        jobs_by_key = {str(row.get("dedupe_key")): row for row in jobs}
        result_ids = {UUID(str(row["session_id"])) for row in results}
        profile = profiles[0] if profiles else {}
        onboarding_session_id = str(profile.get("onboarding_session_id") or "")
        diagnostics: list[DashboardDiagnostic] = []
        for row, session_id in zip(sessions, session_ids, strict=True):
            job = jobs_by_key.get(f"{session_id}:v1")
            diagnostics.append(
                DashboardDiagnostic(
                    id=session_id,
                    target_role=row["target_role"],
                    company=(
                        str(profile["target_company"])
                        if str(session_id) == onboarding_session_id
                        and profile.get("target_company")
                        else None
                    ),
                    interview_status=row["status"],
                    phase=row["phase"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    completed_at=row.get("completed_at"),
                    assessment=(
                        SupabaseAssessmentPipelineRepository._state(job, session_id)
                        if job
                        else None
                    ),
                    diagnostic_available=session_id in result_ids,
                )
            )
        return diagnostics


class MemoryDashboardRepository:
    def __init__(self, diagnostics: list[DashboardDiagnostic] | None = None) -> None:
        self.diagnostics = diagnostics or []

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 25
    ) -> list[DashboardDiagnostic]:
        del user_id
        return self.diagnostics[:limit]
