from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from .agents import AgentRunner
from .agents.definitions import (
    AgentErrorType,
    AgentExecutionContext,
    AgentExecutionResult,
)
from .agents.skeptic import SKEPTIC_AGENT_NAME, SKEPTIC_PROMPT_VERSION
from .skeptic_context import SkepticContextBuilder
from .skeptic_models import SkepticAnalysis, SkepticProcessSummary
from .skeptic_processor import SkepticOutputRejected, SkepticResultProcessor
from .skeptic_repository import SkepticRepository


logger = logging.getLogger("mirror.skeptic")


class SkepticWorkerResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    processed: bool
    success: bool
    retry_scheduled: bool = False


class SkepticWorker:
    def __init__(
        self,
        repository: SkepticRepository,
        context_builder: SkepticContextBuilder,
        runner: AgentRunner,
        processor: SkepticResultProcessor,
        *,
        model: str,
        shadow_mode: bool,
        max_attempts: int,
        retry_base_seconds: int,
    ) -> None:
        self._repository = repository
        self._context = context_builder
        self._runner = runner
        self._processor = processor
        self._model = model
        self._shadow_mode = shadow_mode
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds

    async def run_once(self, worker_id: str) -> SkepticWorkerResult:
        job = await self._repository.claim_job(worker_id, self._max_attempts)
        if job is None:
            return SkepticWorkerResult(processed=False, success=True)

        execution: AgentExecutionResult | None = None
        analysis: SkepticAnalysis | None = None
        summary = SkepticProcessSummary(
            flags_created=0,
            new_claims_created=0,
            claim_update_proposals_created=0,
            observations_created=0,
        )
        try:
            context = await self._context.build(job.turn_id)
            if context.session_id != job.session_id:
                raise SkepticOutputRejected("job and context session do not match")
            execution = await self._runner.run(
                SKEPTIC_AGENT_NAME,
                context,
                context=AgentExecutionContext(
                    session_id=job.session_id, user_id=job.user_id
                ),
            )
            if not execution.success or execution.output is None:
                failure = execution.error_type or AgentErrorType.INTERNAL_FAILURE
                await self._repository.record_analysis(
                    job, execution, None, summary, self._shadow_mode
                )
                return await self._fail(job, failure.value, self._retryable(failure))
            analysis = SkepticAnalysis.model_validate(execution.output)
            summary = await self._processor.process(
                analysis,
                context,
                job.user_id,
                execution.execution_id,
                shadow_mode=self._shadow_mode,
            )
            await self._repository.record_analysis(
                job, execution, analysis, summary, self._shadow_mode
            )
            await self._repository.complete_job(job.id)
            logger.info(
                "skeptic shadow analysis completed",
                extra={
                    "skeptic_execution_id": str(execution.execution_id),
                    "session_id": str(job.session_id),
                    "turn_id": str(job.turn_id),
                    "model": execution.model,
                    "prompt_version": execution.prompt_version,
                    "latency_ms": execution.latency_ms,
                    "flags_created": summary.flags_created,
                    "new_claims_created": summary.new_claims_created,
                    "retry_count": execution.retry_count,
                },
            )
            return SkepticWorkerResult(processed=True, success=True)
        except Exception as exc:
            failure_type = (
                "validation_failure"
                if isinstance(exc, (ValueError, SkepticOutputRejected))
                else "worker_failure"
            )
            if execution is None:
                execution = AgentExecutionResult(
                    execution_id=uuid4(),
                    agent_name=SKEPTIC_AGENT_NAME,
                    model=self._model,
                    prompt_version=SKEPTIC_PROMPT_VERSION,
                    success=False,
                    latency_ms=0,
                    retry_count=0,
                    error_type=(
                        AgentErrorType.VALIDATION_FAILURE
                        if failure_type == "validation_failure"
                        else AgentErrorType.INTERNAL_FAILURE
                    ),
                )
            try:
                await self._repository.record_analysis(
                    job, execution, analysis, summary, self._shadow_mode
                )
            except Exception:
                logger.exception(
                    "skeptic failure metadata persistence failed",
                    extra={"session_id": str(job.session_id), "turn_id": str(job.turn_id)},
                )
            logger.warning(
                "skeptic shadow analysis failed",
                extra={
                    "skeptic_execution_id": str(execution.execution_id),
                    "session_id": str(job.session_id),
                    "turn_id": str(job.turn_id),
                    "model": execution.model,
                    "prompt_version": execution.prompt_version,
                    "retry_count": execution.retry_count,
                    "failure_type": failure_type,
                },
            )
            return await self._fail(job, failure_type, retry=True)

    async def run_forever(self, worker_id: str, *, poll_seconds: float = 1.0) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        while True:
            result = await self.run_once(worker_id)
            if not result.processed:
                await asyncio.sleep(poll_seconds)

    async def _fail(
        self, job, failure_type: str, retry: bool
    ) -> SkepticWorkerResult:
        should_retry = retry and job.attempts < self._max_attempts
        await self._repository.fail_job(
            job,
            failure_type,
            retry=should_retry,
            retry_base_seconds=self._retry_base_seconds,
        )
        return SkepticWorkerResult(
            processed=True, success=False, retry_scheduled=should_retry
        )

    @staticmethod
    def _retryable(error: AgentErrorType) -> bool:
        return error in {
            AgentErrorType.PROVIDER_FAILURE,
            AgentErrorType.TIMEOUT,
            AgentErrorType.INVALID_STRUCTURED_OUTPUT,
            AgentErrorType.VALIDATION_FAILURE,
        }

