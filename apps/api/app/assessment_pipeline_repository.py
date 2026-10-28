from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from .assessment_pipeline_models import AssessmentJob, AssessmentPipelineState, AssessmentPipelineStatus
from .config import Settings, get_settings
from .skeptic_repository import SkepticPersistenceUnavailable, SupabaseSkepticRepository
from .verdict_models import AggregatedAssessment, VerdictLanguageOutput


class AssessmentPipelineUnavailable(Exception):
    pass


# A queued or locked job that nobody finishes. Distinct from a worker's own error code.
STALE_FAILURE_CODE = "assessment_stale"


def assessment_stale_after(settings: Settings | None = None) -> timedelta:
    """How long a job may sit queued or locked before it is a retryable failure.

    Derived from the existing attempt and backoff settings. The wait is the sum
    of the geometric backoff (base * (2^n - 1)) plus the last gap again, so one
    slow live attempt can finish and a worker that never returns still ends.
    Defaults (3 attempts, 30s base) are 330 seconds. There is no separate setting.
    """
    current = settings or get_settings()
    attempts = max(1, current.assessment_job_max_attempts)
    base = max(1, current.assessment_job_retry_base_seconds)
    seconds = base * ((1 << attempts) - 1) + base * (1 << (attempts - 1))
    return timedelta(seconds=seconds)


def _utc(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class AssessmentPipelineRepository(Protocol):
    async def enqueue(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState: ...
    async def status(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState | None: ...
    async def retry(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState: ...
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
        self._stale_after = assessment_stale_after(settings)

    def _public_state(self, row: dict[str, Any], session_id: UUID) -> AssessmentPipelineState:
        return self._state(row, session_id, now=datetime.now(UTC), stale_after=self._stale_after)

    async def enqueue(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState:
        rows = await self._post("rpc/enqueue_post_session_assessment", {"p_session_id": str(session_id), "p_user_id": str(user_id)})
        return self._public_state(rows[0], session_id)

    async def status(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState | None:
        owned = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not owned:
            return None
        rows = await self._get("jobs", {"job_type": f"eq.{self.JOB_TYPE}", "dedupe_key": f"eq.{session_id}:v1", "select": "*", "limit": "1"})
        return self._public_state(rows[0], session_id) if rows else None

    async def retry(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState:
        owned = await self._get(
            "sessions",
            {
                "id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.COMPLETED",
                "select": "id",
                "limit": "1",
            },
        )
        if not owned:
            raise AssessmentPipelineUnavailable(
                "completed owned session not found for assessment retry"
            )
        rows = await self._get(
            "jobs",
            {
                "job_type": f"eq.{self.JOB_TYPE}",
                "dedupe_key": f"eq.{session_id}:v1",
                "select": "*",
                "limit": "1",
            },
        )
        if not rows:
            return await self.enqueue(session_id, user_id)
        row = rows[0]
        visible = self._public_state(row, session_id)
        if visible.status == AssessmentPipelineStatus.FAILED:
            await self._patch(
                "jobs",
                {"id": f"eq.{row['id']}"},
                {
                    "status": "pending",
                    "attempts": 0,
                    "run_after": datetime.now(UTC).isoformat(),
                    "locked_at": None,
                    "locked_by": None,
                    "completed_at": None,
                    "error": None,
                },
            )
            refreshed = await self._get(
                "jobs",
                {"id": f"eq.{row['id']}", "select": "*", "limit": "1"},
            )
            if not refreshed:
                raise AssessmentPipelineUnavailable(
                    "assessment retry did not return a job"
                )
            row = refreshed[0]
        return self._public_state(row, session_id)

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
            "replay_markers": [], "model_provider": "sarvam", "model_name": model, "model_version": model,
            "prompt_version": prompt_version, "rubric_version": aggregate.rubric_version,
        }, prefer="resolution=merge-duplicates,return=minimal")

    @staticmethod
    def _state(
        row: dict[str, Any],
        session_id: UUID,
        *,
        now: datetime | None = None,
        stale_after: timedelta | None = None,
    ) -> AssessmentPipelineState:
        raw = str(row.get("status", "pending")).upper()
        status = {"PENDING": AssessmentPipelineStatus.PENDING, "RUNNING": AssessmentPipelineStatus.PROCESSING, "COMPLETE": AssessmentPipelineStatus.COMPLETED, "FAILED": AssessmentPipelineStatus.FAILED}.get(raw, AssessmentPipelineStatus.PENDING)
        state = AssessmentPipelineState(
            session_id=session_id,
            status=status,
            retry_count=int(row.get("attempts") or 0),
            failure_code=row.get("error") or None,
            queued_at=row.get("created_at"),
            started_at=row.get("locked_at"),
            completed_at=row.get("completed_at"),
        )
        return _stale_state(
            state,
            now=now or datetime.now(UTC),
            stale_after=assessment_stale_after() if stale_after is None else stale_after,
            run_after=row.get("run_after"),
        )


def _stale_state(
    state: AssessmentPipelineState,
    *,
    now: datetime,
    stale_after: timedelta,
    run_after: Any = None,
) -> AssessmentPipelineState:
    """Report PENDING/PROCESSING as FAILED once the worker has had long enough."""
    if state.status not in (AssessmentPipelineStatus.PENDING, AssessmentPipelineStatus.PROCESSING):
        return state
    moment = _utc(now) or datetime.now(UTC)
    scheduled = _utc(run_after)
    if state.status == AssessmentPipelineStatus.PENDING and scheduled is not None and scheduled > moment:
        return state
    if state.status == AssessmentPipelineStatus.PROCESSING:
        anchor = _utc(state.started_at) or _utc(state.queued_at)
    else:
        anchor = scheduled or _utc(state.queued_at)
    if anchor is None or moment - anchor < stale_after:
        return state
    return state.model_copy(update={"status": AssessmentPipelineStatus.FAILED, "failure_code": STALE_FAILURE_CODE})


class MemoryAssessmentPipelineRepository:
    """Local/test implementation; production processing always uses Supabase jobs."""

    def __init__(
        self,
        *,
        stale_after: timedelta | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._jobs: dict[UUID, tuple[AssessmentJob, AssessmentPipelineState]] = {}
        self._keys: dict[tuple[UUID, UUID], UUID] = {}
        self._results: set[tuple[UUID, UUID]] = set()
        # When the job may be claimed again. Public queued_at stays the first enqueue,
        # matching jobs.created_at, which retry does not rewrite.
        self._available_at: dict[UUID, datetime] = {}
        self._stale_after = assessment_stale_after() if stale_after is None else stale_after
        self._clock = clock or (lambda: datetime.now(UTC))

    def _visible(self, job_id: UUID, state: AssessmentPipelineState) -> AssessmentPipelineState:
        return _stale_state(
            state,
            now=self._clock(),
            stale_after=self._stale_after,
            run_after=self._available_at.get(job_id),
        )

    async def enqueue(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState:
        key = (session_id, user_id)
        job_id = self._keys.get(key)
        if job_id is None:
            job_id = uuid4()
            self._keys[key] = job_id
            job = AssessmentJob(id=job_id, session_id=session_id, user_id=user_id, attempts=1)
            state = AssessmentPipelineState(session_id=session_id, status=AssessmentPipelineStatus.PENDING, retry_count=0, queued_at=self._clock())
            self._jobs[job_id] = (job, state)
            self._available_at[job_id] = state.queued_at
        return self._visible(job_id, self._jobs[job_id][1])

    async def status(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState | None:
        job_id = self._keys.get((session_id, user_id))
        return self._visible(job_id, self._jobs[job_id][1]) if job_id else None

    async def retry(self, session_id: UUID, user_id: UUID) -> AssessmentPipelineState:
        key = (session_id, user_id)
        job_id = self._keys.get(key)
        if job_id is None:
            return await self.enqueue(session_id, user_id)
        job, state = self._jobs[job_id]
        if self._visible(job_id, state).status == AssessmentPipelineStatus.FAILED:
            job = job.model_copy(update={"attempts": 1})
            now = self._clock()
            state = state.model_copy(
                update={
                    "status": AssessmentPipelineStatus.PENDING,
                    "retry_count": 0,
                    "failure_code": None,
                    "started_at": None,
                    "completed_at": None,
                }
            )
            self._jobs[job_id] = (job, state)
            self._available_at[job_id] = now
        return self._visible(job_id, state)

    async def claim(self, worker_id: str, max_attempts: int) -> AssessmentJob | None:
        for job_id, (job, state) in list(self._jobs.items()):
            if state.status == AssessmentPipelineStatus.PENDING:
                next_state = state.model_copy(update={"status": AssessmentPipelineStatus.PROCESSING, "started_at": self._clock()})
                self._jobs[job_id] = (job, next_state)
                return job
        return None

    async def has_result(self, session_id: UUID, user_id: UUID) -> bool:
        return (session_id, user_id) in self._results

    async def complete(self, job_id: UUID) -> None:
        job, state = self._jobs[job_id]
        self._jobs[job_id] = (job, state.model_copy(update={"status": AssessmentPipelineStatus.COMPLETED, "completed_at": self._clock(), "failure_code": None}))

    async def fail(self, job: AssessmentJob, failure_code: str, *, retry: bool, retry_base_seconds: int) -> None:
        _, state = self._jobs[job.id]
        if retry:
            next_job = job.model_copy(update={"attempts": job.attempts + 1})
            next_state = state.model_copy(update={"status": AssessmentPipelineStatus.PENDING, "retry_count": job.attempts, "failure_code": failure_code, "started_at": None})
            self._available_at[job.id] = self._clock()
            self._jobs[job.id] = (next_job, next_state)
        else:
            self._jobs[job.id] = (job, state.model_copy(update={"status": AssessmentPipelineStatus.FAILED, "failure_code": failure_code, "completed_at": self._clock()}))

    async def persist_result(self, session_id: UUID, user_id: UUID, aggregate: AggregatedAssessment, language: VerdictLanguageOutput, *, model: str, prompt_version: str) -> None:
        self._results.add((session_id, user_id))
