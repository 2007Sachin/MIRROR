from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .assessment_adjudication_service import AssessmentAdjudicator
from .assessment_orchestrator import AssessmentOrchestrator
from .assessment_pipeline_repository import AssessmentPipelineRepository
from .claim_resolution_service import ClaimsAuditService
from .final_assessment_aggregator import FinalAssessmentAggregator
from .verdict_models import VerdictLanguageInput
from .verdict_service import VerdictLanguageService


logger = logging.getLogger("mirror.assessment")


class AssessmentWorkerResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    processed: bool
    success: bool
    retry_scheduled: bool = False


class AssessmentWorker:
    def __init__(self, repository: AssessmentPipelineRepository, orchestrator: AssessmentOrchestrator, adjudicator: AssessmentAdjudicator, aggregator: FinalAssessmentAggregator, verdict: VerdictLanguageService, claims_audit: ClaimsAuditService, *, max_attempts: int, retry_base_seconds: int) -> None:
        self._repository, self._orchestrator, self._adjudicator = repository, orchestrator, adjudicator
        self._aggregator, self._verdict, self._claims_audit = aggregator, verdict, claims_audit
        self._max_attempts, self._retry_base_seconds = max_attempts, retry_base_seconds

    async def run_once(self, worker_id: str) -> AssessmentWorkerResult:
        job = await self._repository.claim(worker_id, self._max_attempts)
        if job is None:
            return AssessmentWorkerResult(processed=False, success=True)
        try:
            logger.info(
                "assessment job started",
                extra={
                    "assessment_job_id": str(job.id),
                    "session_id": str(job.session_id),
                    "user_id": str(job.user_id),
                },
            )
            # A crash after persistence but before acknowledgement remains idempotent.
            if await self._repository.has_result(job.session_id, job.user_id):
                await self._repository.complete(job.id)
                return AssessmentWorkerResult(processed=True, success=True)
            bundle = await self._orchestrator.assess(job.session_id, job.user_id)
            adjudications = await self._adjudicator.adjudicate(job.session_id, job.user_id, bundle)
            if self._adjudicator.requires_adjudication(bundle) and not adjudications:
                raise RuntimeError("adjudication_failed")
            aggregate = self._aggregator.aggregate(bundle)
            audit = await self._claims_audit.audit(job.user_id)
            language = await self._verdict.write(VerdictLanguageInput(aggregate=aggregate, specialist_summaries={kind: row.result_json.reason_summary for kind, row in {"technical": bundle.technical, "behaviour": bundle.behaviour, "claims": bundle.claims}.items() if row}, claims_audit=audit), session_id=job.session_id, user_id=job.user_id)
            if language is None:
                raise RuntimeError("verdict_generation_failed")
            await self._repository.persist_result(job.session_id, job.user_id, aggregate, language, model="assessment_pipeline", prompt_version="v1")
            await self._repository.complete(job.id)
            logger.info(
                "assessment job completed",
                extra={
                    "assessment_job_id": str(job.id),
                    "session_id": str(job.session_id),
                    "user_id": str(job.user_id),
                    "diagnostic_id": str(job.session_id),
                },
            )
            return AssessmentWorkerResult(processed=True, success=True)
        except Exception as exc:
            retry = job.attempts < self._max_attempts
            await self._repository.fail(job, type(exc).__name__, retry=retry, retry_base_seconds=self._retry_base_seconds)
            logger.exception(
                "assessment job failed",
                extra={
                    "assessment_job_id": str(job.id),
                    "session_id": str(job.session_id),
                    "user_id": str(job.user_id),
                    "failure_code": type(exc).__name__,
                    "retry_scheduled": retry,
                },
            )
            return AssessmentWorkerResult(processed=True, success=False, retry_scheduled=retry)

    async def run_forever(self, worker_id: str, *, poll_seconds: float = 2.0) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        failure_delay = max(poll_seconds, 2.0)
        while True:
            try:
                result = await self.run_once(worker_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                # A transient database or network outage must not terminate the
                # durable worker process. The locked job remains reclaimable by
                # the database lease and the loop resumes after backoff.
                logger.exception(
                    "assessment worker polling failed",
                    extra={"worker_id": worker_id},
                )
                await asyncio.sleep(failure_delay)
                failure_delay = min(60.0, failure_delay * 2)
                continue
            failure_delay = max(poll_seconds, 2.0)
            if not result.processed:
                await asyncio.sleep(poll_seconds)
