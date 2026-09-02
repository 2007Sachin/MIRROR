from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import httpx

from .config import Settings
from .planner_models import (
    ExistingEvidenceSummary,
    InterviewPlan,
    InterviewPlannerInput,
    InterviewPlanRecord,
    PlannerCandidateProfile,
    PlannerClaimSummary,
    PlannerCompetencySummary,
    PlannerProjectSummary,
    PlanningContext,
    PlanningStatus,
)


PLAN_COLUMNS = (
    "id,session_id,user_id,version,status,plan_json,planner_model,prompt_version,"
    "planning_version,execution_id,error_type,created_at,completed_at,active"
)


class InterviewPlanningUnavailable(Exception):
    pass


class ResumeAnalysisRequired(Exception):
    pass


class RoleAnalysisRequired(Exception):
    pass


class InterviewPlanRepository(Protocol):
    async def load_context(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        target_role: str,
        duration_seconds: int,
    ) -> PlanningContext: ...

    async def begin(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        model: str,
        prompt_version: str,
        planning_version: str,
    ) -> tuple[InterviewPlanRecord, bool]: ...

    async def complete(
        self,
        plan_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        plan: InterviewPlan,
    ) -> InterviewPlanRecord: ...

    async def fail(
        self,
        plan_id: UUID,
        user_id: UUID,
        execution_id: UUID | None,
        error_type: str,
    ) -> InterviewPlanRecord: ...

    async def get_active(
        self, session_id: UUID, user_id: UUID
    ) -> InterviewPlanRecord | None: ...


def _record(row: dict[str, Any]) -> InterviewPlanRecord:
    normalized = dict(row)
    normalized["plan"] = normalized.pop("plan_json", None)
    return InterviewPlanRecord.model_validate(normalized)


class SupabaseInterviewPlanRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise InterviewPlanningUnavailable(
                "Supabase interview-plan storage is not configured"
            )
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def load_context(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        target_role: str,
        duration_seconds: int,
    ) -> PlanningContext:
        profile_rows = await self._get(
            "profiles",
            {
                "id": f"eq.{user_id}",
                "select": (
                    "career_stage,career_intent,interview_timeline,preferred_language,"
                    "current_role_profile_id"
                ),
            },
        )
        if not profile_rows or not profile_rows[0].get("current_role_profile_id"):
            raise RoleAnalysisRequired
        profile = profile_rows[0]
        role_profile_id = profile["current_role_profile_id"]
        role_rows = await self._get(
            "role_profiles",
            {
                "id": f"eq.{role_profile_id}",
                "user_id": f"eq.{user_id}",
                "select": "id,current_analysis_version_id,target_role",
            },
        )
        if not role_rows or not role_rows[0].get("current_analysis_version_id"):
            raise RoleAnalysisRequired
        if (
            role_rows[0]["target_role"].strip().casefold()
            != target_role.strip().casefold()
        ):
            raise RoleAnalysisRequired
        role_analysis_id = UUID(role_rows[0]["current_analysis_version_id"])
        competency_rows = await self._get(
            "role_competencies",
            {
                "analysis_version_id": f"eq.{role_analysis_id}",
                "user_id": f"eq.{user_id}",
                "select": "id,name,category,importance_weight,expected_level",
                "order": "importance_weight.desc",
            },
        )
        if not competency_rows:
            raise RoleAnalysisRequired

        link_rows = await self._get(
            "session_document_links",
            {"session_id": f"eq.{session_id}", "select": "document_id"},
        )
        linked_document_ids = [row["document_id"] for row in link_rows]
        resume_document_ids: list[str] = []
        if linked_document_ids:
            document_rows = await self._get(
                "documents",
                {
                    "id": f"in.({','.join(linked_document_ids)})",
                    "user_id": f"eq.{user_id}",
                    "document_type": "eq.RESUME",
                    "select": "id",
                },
            )
            resume_document_ids = [row["id"] for row in document_rows]
        resume_params = {
            "user_id": f"eq.{user_id}",
            "status": "eq.COMPLETED",
            "select": "id,document_id",
            "order": "created_at.desc,version.desc",
            "limit": "1",
        }
        if resume_document_ids:
            resume_params["document_id"] = f"in.({','.join(resume_document_ids)})"
        resume_rows = await self._get("resume_analyses", resume_params)
        if not resume_rows:
            raise ResumeAnalysisRequired
        resume_analysis_id = UUID(resume_rows[0]["id"])
        document_id = resume_rows[0]["document_id"]
        claim_rows = await self._get(
            "claims",
            {
                "user_id": f"eq.{user_id}",
                "source_document_id": f"eq.{document_id}",
                "select": (
                    "id,claim_text,claim_type,source,confidence,verification_priority"
                ),
                "order": "created_at.asc",
            },
        )
        claim_ids = [row["id"] for row in claim_rows]
        entity_rows: list[dict[str, Any]] = []
        relation_rows: list[dict[str, Any]] = []
        evidence_rows: list[dict[str, Any]] = []
        if claim_ids:
            relation_rows = await self._get(
                "claim_relations",
                {
                    "user_id": f"eq.{user_id}",
                    "source_entity_type": "eq.CLAIM",
                    "source_entity_id": f"in.({','.join(claim_ids)})",
                    "target_entity_type": "eq.ENTITY",
                    "select": "source_entity_id,target_entity_id",
                },
            )
            entity_ids = sorted({row["target_entity_id"] for row in relation_rows})
            if entity_ids:
                entity_rows = await self._get(
                    "claim_entities",
                    {
                        "user_id": f"eq.{user_id}",
                        "id": f"in.({','.join(entity_ids)})",
                        "select": "id,entity_type,canonical_name",
                    },
                )
            evidence_rows = await self._get(
                "claim_evidence",
                {
                    "user_id": f"eq.{user_id}",
                    "claim_id": f"in.({','.join(claim_ids)})",
                    "select": "claim_id,evidence_direction",
                },
            )

        entities = {row["id"]: row for row in entity_rows}
        claim_entities: dict[str, list[str]] = {}
        for relation in relation_rows:
            entity = entities.get(relation["target_entity_id"])
            if entity:
                claim_entities.setdefault(relation["source_entity_id"], []).append(
                    entity["canonical_name"]
                )
        evidence_counts: dict[str, Counter[str]] = {}
        for evidence in evidence_rows:
            evidence_counts.setdefault(evidence["claim_id"], Counter())[
                evidence["evidence_direction"]
            ] += 1

        claims = [
            PlannerClaimSummary(
                **row,
                claim_type=row["claim_type"].upper(),
                source=row["source"].upper(),
                entity_names=claim_entities.get(row["id"], []),
            )
            for row in claim_rows
        ]
        projects = [
            PlannerProjectSummary(id=row["id"], name=row["canonical_name"])
            for row in entity_rows
            if row["entity_type"] == "PROJECT"
        ]
        skills = sorted(
            {
                row["canonical_name"]
                for row in entity_rows
                if row["entity_type"] == "SKILL"
            }
        )
        evidence = [
            ExistingEvidenceSummary(
                claim_id=claim_id,
                supports_count=counts["SUPPORTS"],
                weakens_count=counts["WEAKENS"],
                context_only_count=counts["CONTEXT_ONLY"],
            )
            for claim_id, counts in evidence_counts.items()
        ]
        planner_input = InterviewPlannerInput(
            session_id=session_id,
            candidate_profile=PlannerCandidateProfile(
                career_stage=profile.get("career_stage"),
                career_intent=profile.get("career_intent"),
                interview_timeline=profile.get("interview_timeline"),
                preferred_language=profile.get("preferred_language"),
            ),
            target_role=target_role,
            career_stage=profile.get("career_stage"),
            interview_duration_seconds=duration_seconds,
            claims_summary=claims,
            role_competencies=[
                PlannerCompetencySummary.model_validate(row) for row in competency_rows
            ],
            projects=projects,
            skills=skills,
            high_verification_priority_claims=[
                claim.id for claim in claims if claim.verification_priority == "HIGH"
            ],
            existing_evidence_summary=evidence,
        )
        return PlanningContext(
            resume_analysis_id=resume_analysis_id,
            role_analysis_id=role_analysis_id,
            planner_input=planner_input,
        )

    async def begin(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        model: str,
        prompt_version: str,
        planning_version: str,
    ) -> tuple[InterviewPlanRecord, bool]:
        processing = await self._query_one(
            {
                "session_id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.PROCESSING",
            }
        )
        if processing:
            return processing, False
        try:
            rows = await self._post(
                "rpc/begin_interview_plan",
                {
                    "p_session_id": str(session_id),
                    "p_user_id": str(user_id),
                    "p_planner_model": model,
                    "p_prompt_version": prompt_version,
                    "p_planning_version": planning_version,
                },
            )
            return _record(rows[0]), True
        except (IndexError, TypeError, ValueError) as exc:
            raise InterviewPlanningUnavailable from exc

    async def complete(
        self,
        plan_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        plan: InterviewPlan,
    ) -> InterviewPlanRecord:
        rows = await self._post(
            "rpc/complete_interview_plan",
            {
                "p_plan_id": str(plan_id),
                "p_user_id": str(user_id),
                "p_execution_id": str(execution_id),
                "p_plan": plan.model_dump(mode="json"),
            },
        )
        try:
            return _record(rows[0])
        except (IndexError, TypeError, ValueError) as exc:
            raise InterviewPlanningUnavailable from exc

    async def fail(
        self,
        plan_id: UUID,
        user_id: UUID,
        execution_id: UUID | None,
        error_type: str,
    ) -> InterviewPlanRecord:
        rows = await self._patch(
            "interview_plans",
            {
                "id": f"eq.{plan_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.PROCESSING",
                "select": PLAN_COLUMNS,
            },
            {
                "status": PlanningStatus.FAILED.value,
                "execution_id": str(execution_id) if execution_id else None,
                "error_type": error_type,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        try:
            return _record(rows[0])
        except (IndexError, TypeError, ValueError) as exc:
            raise InterviewPlanningUnavailable from exc

    async def get_active(
        self, session_id: UUID, user_id: UUID
    ) -> InterviewPlanRecord | None:
        return await self._query_one(
            {
                "session_id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "active": "eq.true",
            }
        )

    async def _query_one(self, params: dict[str, str]) -> InterviewPlanRecord | None:
        rows = await self._get(
            "interview_plans",
            {**params, "select": PLAN_COLUMNS, "order": "version.desc", "limit": "1"},
        )
        return _record(rows[0]) if rows else None

    async def _get(self, resource: str, params: dict[str, str]) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/{resource}",
                    headers=self._headers,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise InterviewPlanningUnavailable from exc

    async def _post(
        self, resource: str, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/{resource}",
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise InterviewPlanningUnavailable from exc

    async def _patch(
        self, resource: str, params: dict[str, str], payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.patch(
                    f"{self._url}/rest/v1/{resource}",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params=params,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise InterviewPlanningUnavailable from exc

