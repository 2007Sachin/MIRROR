from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from .assessment_pipeline_models import AssessmentJob, AssessmentPipelineState, AssessmentPipelineStatus
from .config import Settings
from .skeptic_repository import SkepticPersistenceUnavailable, SupabaseSkepticRepository
from .verdict_models import AggregatedAssessment, VerdictLanguageOutput


class AssessmentPipelineUnavailable(Exception):
    pass


class AssessmentPipelineRepository(Protocol):
    async def enqueue(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState: ...
    async def status(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState | None: ...
    async def claim(self, worker_id: str, max_attempts: int) -> AssessmentJob | None: ...
    async def has_result(self, session_id: UUID, user_id: UUID) -> bool: ...
    async def complete(self, job_id: UUID) -> None: ...
    async def fail(self, job: AssessmentJob, failure_code: str, *, retry: bool, retry_base_seconds: int) -> None: ...
    async def persist_result(self, session_id: UUID, user_id: UUID, aggregate: AggregatedAssessment, language: VerdictLanguageOutput, *, model: str, prompt_version: str) -> None: ...


class SupabaseAssessmentPipelineRepository(SupabaseSkepticRepository):
    JOB_TYPE = "POST_SESSION_ASSESSMENT"

    def __init__(self, settings: Settings) -> None:
        try:
            super().__init__(settings)
        except SkepticPersistenceUnavailable as exc:
            raise AssessmentPipelineUnavailable("assessment persistence is not configured") from exc

    async def enqueue(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState:
        rows = await self._post("rpc/enqueue_post_session_assessment", {"p_session_id": str(session_id), "p_user_id": str(user_id)})
        return self._state(rows[0], session_id)

    async def status(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState | None:
        owned = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not owned:
            return None
        rows = await self._get("jobs", {"job_type": f"eq.{self.JOB_TYPE}", "dedupe_key": f"eq.{session_id}:v1", "select": "*", "limit": "1"})
        return self._state(rows[0], session_id) if rows else None

    async def claim(self, worker_id: str, max_attempts: int) -> AssessmentJob | None:
        rows = await self._post("rpc/claim_post_session_assessment", {"p_worker_id": worker_id, "p_max_attempts": max_attempts})
        if not rows:
            return None
        row = rows[0]
        payload = row.get("payload") if isinstance(row, dict) else None
        if not isinstance(payload, dict):
            raise AssessmentPipelineUnavailable("assessment job payload is invalid")
        return AssessmentJob(id=row["id"], session_id=payload["session_id"], user_id=payload["user_id"], attempts=row["attempts"])

    async def has_result(self, session_id: UUID, user_id: UUID) -> bool:
        owned = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not owned:
            return False
        rows = await self._get("session_results", {"session_id": f"eq.{session_id}", "select": "session_id", "limit": "1"})
        return bool(rows)

    async def complete(self, job_id: UUID) -> None:
        await self._patch("jobs", {"id": f"eq.{job_id}"}, {"status": "complete", "completed_at": datetime.now(UTC).isoformat(), "locked_at": None, "locked_by": None, "error": None})

    async def fail(self, job: AssessmentJob, failure_code: str, *, retry: bool, retry_base_seconds: int) -> None:
        values: dict[str, Any] = {"status": "pending" if retry else "failed", "error": failure_code[:500], "locked_at": None, "locked_by": None}
        if retry:
            values["run_after"] = (datetime.now(UTC) + timedelta(seconds=retry_base_seconds * (2 ** max(0, job.attempts - 1)))).isoformat()
        else:
            values["completed_at"] = datetime.now(UTC).isoformat()
        await self._patch("jobs", {"id": f"eq.{job.id}"}, values)

    async def persist_result(self, session_id: UUID, user_id: UUID, aggregate: AggregatedAssessment, language: VerdictLanguageOutput, *, model: str, prompt_version: str) -> None:
        owned = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not owned:
            raise AssessmentPipelineUnavailable("session is not owned")
        await self._post("session_results", {
            "session_id": str(session_id),
            "role_readiness_low": aggregate.role_readiness_low, "role_readiness_high": aggregate.role_readiness_high,
            "interview_readiness_low": aggregate.interview_readiness_low, "interview_readiness_high": aggregate.interview_readiness_high,
            "role_readiness_internal": aggregate.role_readiness_internal, "interview_readiness_internal": aggregate.interview_readiness_internal,
            "verdict_word": aggregate.verdict_code.value, "verdict_code": aggregate.verdict_code.value,
            "root_cause": aggregate.root_cause_code.value, "root_cause_code": aggregate.root_cause_code.value,
            "prescribed_fix": language.root_cause_explanation, "summary": language.verdict_summary,
            "root_cause_explanation": language.root_cause_explanation, "confidence_note": language.confidence_note,
            "assessment_confidence": aggregate.overall_signal_confidence,
            "replay_markers": [], "model_provider": "groq", "model_name": model, "model_version": model,
            "prompt_version": prompt_version, "rubric_version": "v1",
        }, prefer="resolution=merge-duplicates,return=minimal")

    @staticmethod
    def _state(row: dict[str, Any], session_id: UUID) -> AssessmentPipelineState:
        raw = str(row.get("status", "pending")).upper()
        status = {"PENDING": AssessmentPipelineStatus.PENDING, "RUNNING": AssessmentPipelineStatus.PROCESSING, "COMPLETE": AssessmentPipelineStatus.COMPLETED, "FAILED": AssessmentPipelineStatus.FAILED}.get(raw, AssessmentPipelineStatus.PENDING)
        return AssessmentPipelineState(session_id=session_id, status=status, retry_count=int(row.get("attempts") or 0), failure_code=row.get("error"), queued_at=row.get("created_at"), started_at=row.get("locked_at"), completed_at=row.get("completed_at"))


class MemoryAssessmentPipelineRepository:
    """Local/test implementation; production processing always uses Supabase jobs."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, tuple[AssessmentJob, AssessmentPipelineState]] = {}
        self._keys: dict[tuple[UUID, UUID], UUID] = {}
        self._results: set[tuple[UUID, UUID]] = set()

    async def enqueue(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState:
        key = (session_id, user_id)
        job_id = self._keys.get(key)
        if job_id is None:
            job_id = uuid4()
            self._keys[key] = job_id
            job = AssessmentJob(id=job_id, session_id=session_id, user_id=user_id, attempts=1)
            state = AssessmentPipelineState(session_id=session_id, status=AssessmentPipelineStatus.PENDING, retry_count=0, queued_at=datetime.now(UTC))
            self._jobs[job_id] = (job, state)
        return self._jobs[job_id][1]

    async def status(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState | None:
        job_id = self._keys.get((session_id, user_id))
        return self._jobs[job_id][1] if job_id else None

    async def claim(self, worker_id: str, max_attempts: int) -> AssessmentJob | None:
        for job_id, (job, state) in list(self._jobs.items()):
            if state.status == AssessmentPipelineStatus.PENDING:
                next_state = state.model_copy(update={"status": AssessmentPipelineStatus.PROCESSING, "started_at": datetime.now(UTC)})
                self._jobs[job_id] = (job, next_state)
                return job
        return None

    async def has_result(self, session_id: UUID, user_id: UUID) -> bool:
        return (session_id, user_id) in self._results

    async def complete(self, job_id: UUID) -> None:
        job, state = self._jobs[job_id]
        self._jobs[job_id] = (job, state.model_copy(update={"status": AssessmentPipelineStatus.COMPLETED, "completed_at": datetime.now(UTC), "failure_code": None}))

    async def fail(self, job: AssessmentJob, failure_code: str, *, retry: bool, retry_base_seconds: int) -> None:
        _, state = self._jobs[job.id]
        if retry:
            next_job = job.model_copy(update={"attempts": job.attempts + 1})
            next_state = state.model_copy(update={"status": AssessmentPipelineStatus.PENDING, "retry_count": job.attempts, "failure_code": failure_code, "started_at": None})
            self._jobs[job.id] = (next_job, next_state)
        else:
            self._jobs[job.id] = (job, state.model_copy(update={"status": AssessmentPipelineStatus.FAILED, "failure_code": failure_code, "completed_at": datetime.now(UTC)}))

    async def persist_result(self, session_id: UUID, user_id: UUID, aggregate: AggregatedAssessment, language: VerdictLanguageOutput, *, model: str, prompt_version: str) -> None:
        self._results.add((session_id, user_id))
