from __future__ import annotations

import logging
from typing import Protocol
from uuid import UUID

from .assessment_pipeline_repository import SupabaseAssessmentPipelineRepository
from .config import Settings
from .dashboard_models import DashboardDiagnostic
from .skeptic_repository import SkepticPersistenceUnavailable, SupabaseSkepticRepository


logger = logging.getLogger("mirror.dashboard")


class DashboardUnavailable(Exception):
    pass


class DashboardRepository(Protocol):
    async def list_for_user(
        self, user_id: UUID, *, limit: int = 25
    ) -> list[DashboardDiagnostic]: ...

    async def answered_counts(self, user_id: UUID, session_ids: list[UUID]) -> dict[UUID, int]: ...


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
                    "select": "id,target_role,role_profile_id,status,phase,created_at,updated_at,completed_at,practice_mode,practice_focus,practice_theme,total_questions",
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
            logger.exception("dashboard data could not be loaded", extra={"user_id": str(user_id)})
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
                    role_profile_id=row.get("role_profile_id"),
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
                    practice_mode=row.get("practice_mode") or "FULL_INTERVIEW",
                    practice_focus=row.get("practice_focus"),
                    practice_theme=row.get("practice_theme"),
                    total_questions=row.get("total_questions") or 0,
                )
            )
        return diagnostics

    async def answered_counts(self, user_id: UUID, session_ids: list[UUID]) -> dict[UUID, int]:
        """How many answers the candidate gave in each of this person's sessions, in two reads.

        Ownership is checked here rather than trusted from the caller: ids that are not
        this person's sessions are dropped before any turn is read.
        """
        if not session_ids:
            return {}
        listed = ",".join(str(value) for value in session_ids)
        try:
            owned = await self._get("sessions", {"id": f"in.({listed})", "user_id": f"eq.{user_id}", "select": "id"})
            mine = ",".join(str(row["id"]) for row in owned)
            if not mine:
                return {}
            rows = await self._get(
                "turns",
                {"session_id": f"in.({mine})", "speaker": "eq.candidate", "select": "session_id", "limit": "5000"},
            )
        except Exception as exc:
            logger.exception("answer counts could not be loaded")
            raise DashboardUnavailable("answer counts could not be loaded") from exc
        counts: dict[UUID, int] = {}
        for row in rows:
            key = UUID(str(row["session_id"]))
            counts[key] = counts.get(key, 0) + 1
        return counts


class MemoryDashboardRepository:
    def __init__(self, diagnostics: list[DashboardDiagnostic] | None = None) -> None:
        self.diagnostics = diagnostics or []

    async def answered_counts(self, user_id: UUID, session_ids: list[UUID]) -> dict[UUID, int]:
        return {}

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 25
    ) -> list[DashboardDiagnostic]:
        del user_id
        return self.diagnostics[:limit]
