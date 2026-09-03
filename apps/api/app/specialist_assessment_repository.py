from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from .specialist_assessor_models import (
    AssessorType, SpecialistAssessmentContext, SpecialistAssessmentOutput,
    SpecialistStatus, StoredSpecialistAssessment,
)
from .config import Settings
from .skeptic_repository import SkepticPersistenceUnavailable, SupabaseSkepticRepository


class SpecialistAssessmentRepository(Protocol):
    async def get_latest(self, session_id: UUID, user_id: UUID, assessor_type: AssessorType) -> StoredSpecialistAssessment | None: ...
    async def load_context(
        self, session_id: UUID, user_id: UUID, assessor_type: AssessorType
    ) -> SpecialistAssessmentContext | None: ...
    async def store(
        self, session_id: UUID, assessor_type: AssessorType, status: SpecialistStatus,
        result: SpecialistAssessmentOutput, model: str, model_version: str,
        prompt_version: str, rubric_version: str,
    ) -> StoredSpecialistAssessment: ...


class SpecialistAssessmentUnavailable(Exception):
    pass


class SupabaseSpecialistAssessmentRepository(SupabaseSkepticRepository):
    def __init__(self, settings: Settings) -> None:
        try:
            super().__init__(settings)
        except SkepticPersistenceUnavailable as exc:
            raise SpecialistAssessmentUnavailable from exc

    async def load_context(self, session_id: UUID, user_id: UUID, assessor_type: AssessorType) -> SpecialistAssessmentContext | None:
        sessions = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not sessions:
            return None
        turns = await self._get("turns", {"session_id": f"eq.{session_id}", "select": "id,speaker,text,turn_type,phase", "order": "turn_index.asc", "limit": "100"})
        claims = await self._get("claims", {"user_id": f"eq.{user_id}", "or": f"(session_id.eq.{session_id},session_id.is.null)", "select": "id,claim_text,status,confidence,verification_priority", "limit": "100"})
        evidence = await self._get("claim_evidence", {"user_id": f"eq.{user_id}", "validated": "eq.true", "select": "claim_id,turn_id,quote_text,evidence_direction,strength,evidence_strength", "limit": "200"})
        flags = await self._get("flags", {"session_id": f"eq.{session_id}", "select": "flag_type,severity,confidence,reason", "limit": "100"})
        return SpecialistAssessmentContext(
            session_id=session_id, assessor_type=assessor_type,
            transcript_turns=[{**row, "speaker": str(row["speaker"]).upper(), "turn_type": str(row["turn_type"]).upper(), "phase": str(row["phase"]).upper()} for row in turns],
            claims=claims, validated_evidence=evidence, skeptic_observations=flags,
        )

    async def get_latest(self, session_id: UUID, user_id: UUID, assessor_type: AssessorType) -> StoredSpecialistAssessment | None:
        owned = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not owned:
            return None
        rows = await self._get("specialist_assessments", {"session_id": f"eq.{session_id}", "assessor_type": f"eq.{assessor_type.value}", "select": "*", "order": "created_at.desc", "limit": "1"})
        if not rows:
            return None
        row: dict[str, Any] = rows[0]
        return StoredSpecialistAssessment.model_validate({**row, "assessor_type": str(row["assessor_type"]).upper(), "status": str(row["status"]).upper()})

    async def store(self, session_id: UUID, assessor_type: AssessorType, status: SpecialistStatus,
                    result: SpecialistAssessmentOutput, model: str, model_version: str,
                    prompt_version: str, rubric_version: str) -> StoredSpecialistAssessment:
        rows = await self._post("specialist_assessments", {
            "session_id": str(session_id), "assessor_type": assessor_type.value,
            "status": status.value, "result_json": result.model_dump(mode="json"),
            "model": model, "model_version": model_version,
            "prompt_version": prompt_version, "rubric_version": rubric_version,
        }, prefer="return=representation")
        row: dict[str, Any] = rows[0]
        return StoredSpecialistAssessment.model_validate({
            **row, "assessor_type": str(row["assessor_type"]).upper(),
            "status": str(row["status"]).upper(), "result_json": row["result_json"],
        })

