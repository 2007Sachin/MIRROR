from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

from .flag_activation import FlagEligibilityService
from .agents import AgentRunner
from .agents.definitions import AgentExecutionContext, AgentExecutionResult
from .agents.interviewer import INTERVIEWER_AGENT_NAME
from .interview_engine import (
    InterviewFlowRejected,
    InterviewStateMachine,
    PHASE_ORDER,
)
from .interviewer_context import InterviewerContextBuilder
from .interviewer_models import (
    InterviewerAction,
    InterviewerContext,
    InterviewerDecision,
    InterviewerObjective,
    InterviewerReasonCode,
    InterviewerTurnType,
    InterviewStartResponse,
    PublicTurn,
    StoredInterviewTurn,
    TextTurnRequest,
    TextTurnResponse,
)
from .interviewer_repository import InterviewTurnRepository
from .planner_models import InterviewObjective, InterviewPlan
from .schemas import Phase, SessionStatus


logger = logging.getLogger("mirror.interviewer")


class CandidateTurnCompletedPublisher(Protocol):
    async def publish_candidate_turn_completed(
        self, session_id: UUID, user_id: UUID, turn_id: UUID
    ) -> None: ...

PROBE_TYPES = frozenset(
    {
        InterviewerTurnType.DEPTH_PROBE,
        InterviewerTurnType.CONTRADICTION_PROBE,
        InterviewerTurnType.LADDER_UP,
        InterviewerTurnType.LADDER_DOWN,
    }
)

UNSAFE_FEEDBACK_PHRASES = (
    "great answer",
    "excellent answer",
    "that's correct",
    "that is correct",
    "that's wrong",
    "that is wrong",
    "i caught you",
    "you're doing well",
    "you are doing well",
    "your score",
    "readiness score",
    "contradict",
    "you lied",
    " lying",
    "dishonest",
    "not truthful",
    "not telling the truth",
)


class InterviewerOutputRejected(Exception):
    pass


class TextInterviewService:
    """Coordinates text turns while leaving lifecycle authority in the state machine."""

    def __init__(
        self,
        state: InterviewStateMachine,
        context_builder: InterviewerContextBuilder,
        turns: InterviewTurnRepository,
        runner: AgentRunner,
        turn_completed_publisher: CandidateTurnCompletedPublisher | None = None,
        flag_eligibility: FlagEligibilityService | None = None,
    ) -> None:
        self._state = state
        self._context = context_builder
        self._turns = turns
        self._runner = runner
        self._turn_completed_publisher = turn_completed_publisher
        self._flag_eligibility = flag_eligibility

    async def start(self, session_id: UUID, user_id: UUID) -> InterviewStartResponse:
        session = await self._state.get_state(session_id, user_id)
        existing = await self._turns.list_turns(session_id)
        if session.status == SessionStatus.ACTIVE and existing:
            latest_interviewer = next(
                (turn for turn in reversed(existing) if turn.speaker.value == "INTERVIEWER"),
                None,
            )
            if latest_interviewer:
                _, remaining = self._state.remaining_times(session)
                return self._start_response(latest_interviewer, remaining)

        objective = await self._context.opening_objective(session_id, user_id)
        if session.status == SessionStatus.READY:
            session = await self._state.start(session_id, user_id)
        if session.current_primary_question_id != objective.objective_id:
            session = await self._state.register_primary_question(
                session_id, user_id, objective.objective_id
            )
        opening = await self._turns.create_interviewer_turn(
            session_id,
            user_id,
            response_to_turn_id=None,
            text=objective.initial_question,
            turn_type=InterviewerTurnType.PLANNED,
            phase=session.phase,
            primary_thread_id=objective.objective_id,
            agent_execution_id=None,
            model=None,
            prompt_version=None,
            latency_ms=None,
            retry_count=None,
            target_claim_ids=objective.target_claim_ids,
            target_competency_ids=objective.target_competency_ids,
        )
        await self._state.record_event(
            session_id,
            user_id,
            "INTERVIEW_OPENING_ASKED",
            {"objective_id": objective.objective_id, "turn_index": opening.turn_index},
        )
        _, remaining = self._state.remaining_times(session)
        return self._start_response(opening, remaining)

    async def submit(
        self,
        session_id: UUID,
        user_id: UUID,
        request: TextTurnRequest,
        *,
        on_candidate_ready: Callable[[StoredInterviewTurn], Awaitable[None]] | None = None,
    ) -> TextTurnResponse:
        session = await self._state.get_state(session_id, user_id)
        if session.status != SessionStatus.ACTIVE:
            raise InterviewFlowRejected("session is not accepting candidate turns")

        existing_candidate = await self._turns.get_candidate_by_client_id(
            session_id, request.client_turn_id
        )
        if existing_candidate:
            existing_response = await self._turns.get_response(
                session_id, existing_candidate.id
            )
            if existing_response:
                if on_candidate_ready:
                    await on_candidate_ready(existing_candidate)
                return await self._response(existing_candidate, existing_response, user_id)

        recent = await self._turns.list_turns(session_id, limit=1)
        previous = recent[-1] if recent else None
        candidate = existing_candidate or await self._turns.create_candidate_turn(
            session_id,
            user_id,
            text=request.text,
            client_turn_id=request.client_turn_id,
            turn_type=(previous.turn_type if previous else InterviewerTurnType.PLANNED),
            phase=session.phase,
            primary_thread_id=session.current_primary_question_id,
        )
        if self._turn_completed_publisher:
            try:
                await self._turn_completed_publisher.publish_candidate_turn_completed(
                    session_id, user_id, candidate.id
                )
            except Exception:
                logger.exception(
                    "candidate turn event enqueue failed",
                    extra={"session_id": str(session_id), "turn_id": str(candidate.id)},
                )
        if on_candidate_ready:
            await on_candidate_ready(candidate)

        _, remaining = self._state.remaining_times(session)
        if remaining == 0:
            interviewer = await self._store_close(
                candidate, session_id, user_id, reason=InterviewerReasonCode.TIME_LIMIT
            )
            return await self._response(candidate, interviewer, user_id)

        context = await self._context.build(session_id, user_id, candidate.turn_index)
        execution = await self._runner.run(
            INTERVIEWER_AGENT_NAME,
            context,
            context=AgentExecutionContext(session_id=session_id, user_id=user_id),
        )

        try:
            decision = self._validated_decision(execution, context)
            interviewer = await self._apply_decision(
                candidate, decision, context, execution, user_id
            )
        except InterviewerOutputRejected as exc:
            await self._state.record_event(
                session_id,
                user_id,
                "INTERVIEWER_AGENT_FAILED",
                {
                    "execution_id": str(execution.execution_id),
                    "error_type": str(execution.error_type or "output_rejected"),
                },
            )
            logger.warning(
                "interviewer fallback used",
                extra={
                    "session_id": str(session_id),
                    "user_id": str(user_id),
                    "execution_id": str(execution.execution_id),
                    "reason": type(exc).__name__,
                },
            )
            interviewer = await self._fallback(candidate, context, execution, user_id)

        await self._state.record_event(
            session_id,
            user_id,
            "TEXT_TURN_COMPLETED",
            {
                "candidate_turn_index": candidate.turn_index,
                "interviewer_turn_index": interviewer.turn_index,
            },
        )
        return await self._response(candidate, interviewer, user_id)

    async def list_public_turns(
        self, session_id: UUID, user_id: UUID
    ) -> list[PublicTurn]:
        await self._state.get_state(session_id, user_id)
        return [
            PublicTurn(
                id=turn.id,
                session_id=turn.session_id,
                turn_index=turn.turn_index,
                speaker=turn.speaker,
                text=turn.text,
                turn_type=turn.turn_type,
                phase=turn.phase,
                created_at=turn.created_at,
            )
            for turn in await self._turns.list_turns(session_id)
        ]

    def _validated_decision(
        self, execution: AgentExecutionResult, context: InterviewerContext
    ) -> InterviewerDecision:
        if not execution.success or execution.output is None:
            raise InterviewerOutputRejected
        try:
            decision = InterviewerDecision.model_validate(execution.output)
        except ValueError as exc:
            raise InterviewerOutputRejected from exc
        if decision.primary_thread_id != context.objective.objective_id:
            raise InterviewerOutputRejected
        if not set(decision.target_claim_ids) <= set(context.objective.target_claim_ids):
            raise InterviewerOutputRejected
        if not set(decision.target_competency_ids) <= set(
            context.objective.target_competency_ids
        ):
            raise InterviewerOutputRejected
        lowered = decision.question_text.casefold()
        if any(phrase in lowered for phrase in UNSAFE_FEEDBACK_PHRASES):
            raise InterviewerOutputRejected
        if decision.question_text.count("?") > 1:
            raise InterviewerOutputRejected
        pending = context.pending_flag
        if decision.used_flag_id is not None:
            if (
                pending is None
                or decision.used_flag_id != pending.flag_id
                or decision.action != InterviewerAction.ASK
                or decision.turn_type != pending.recommended_turn_type
                or decision.reason_code != InterviewerReasonCode.SKEPTIC_FLAG_PROBE
            ):
                raise InterviewerOutputRejected
        if decision.turn_type == InterviewerTurnType.CONTRADICTION_PROBE and (
            pending is None or decision.used_flag_id != pending.flag_id
        ):
            raise InterviewerOutputRejected
        return decision

    async def _apply_decision(
        self,
        candidate: StoredInterviewTurn,
        decision: InterviewerDecision,
        context: InterviewerContext,
        execution: AgentExecutionResult,
        user_id: UUID,
    ) -> StoredInterviewTurn:
        if decision.action == InterviewerAction.CLOSE:
            return await self._store_close(
                candidate,
                candidate.session_id,
                user_id,
                reason=decision.reason_code,
                text=decision.question_text,
                execution=execution,
            )
        if decision.action in {InterviewerAction.TRANSITION, InterviewerAction.RECOVERY}:
            return await self._move_on(
                candidate, context, execution, user_id, recovery=decision.action == InterviewerAction.RECOVERY
            )
        if decision.turn_type not in PROBE_TYPES:
            raise InterviewerOutputRejected
        if not await self._state.can_ask_question(
            candidate.session_id, user_id, probe=True
        ):
            return await self._move_on(candidate, context, execution, user_id, recovery=True)
        session = await self._state.register_probe(candidate.session_id, user_id)
        interviewer = await self._store(
            candidate,
            user_id,
            decision.question_text,
            decision.turn_type,
            session.phase,
            context.objective,
            execution,
        )
        if decision.used_flag_id and self._flag_eligibility:
            try:
                consumed = await self._flag_eligibility.consume(
                    decision.used_flag_id,
                    candidate.session_id,
                    user_id,
                    candidate.turn_index,
                    interviewer.id,
                )
                if not consumed:
                    logger.warning(
                        "skeptic flag consumption rejected",
                        extra={"session_id": str(candidate.session_id), "flag_id": str(decision.used_flag_id)},
                    )
            except Exception:
                # The accepted live question must not fail because an asynchronous
                # audit write is unavailable. Conditional consumption prevents races.
                logger.exception(
                    "skeptic flag consumption failed",
                    extra={"session_id": str(candidate.session_id), "flag_id": str(decision.used_flag_id)},
                )
        return interviewer

    async def _fallback(
        self,
        candidate: StoredInterviewTurn,
        context: InterviewerContext,
        execution: AgentExecutionResult,
        user_id: UUID,
    ) -> StoredInterviewTurn:
        if await self._state.can_ask_question(
            candidate.session_id, user_id, probe=True
        ):
            session = await self._state.register_probe(candidate.session_id, user_id)
            return await self._store(
                candidate,
                user_id,
                context.objective.initial_question,
                InterviewerTurnType.DEPTH_PROBE,
                session.phase,
                context.objective,
                execution,
            )
        return await self._move_on(candidate, context, execution, user_id, recovery=True)

    async def _move_on(
        self,
        candidate: StoredInterviewTurn,
        context: InterviewerContext,
        execution: AgentExecutionResult,
        user_id: UUID,
        *,
        recovery: bool,
    ) -> StoredInterviewTurn:
        session = await self._state.get_state(candidate.session_id, user_id)
        if recovery and await self._state.must_recover(
            candidate.session_id, user_id, repeated_inability=session.current_probe_count < 2
        ):
            session = await self._state.trigger_recovery(
                candidate.session_id,
                user_id,
                repeated_inability=session.current_probe_count < 2,
            )
        plan = await self._context.get_plan(candidate.session_id, user_id)
        objective = self._next_objective(plan, context.objective, session.phase, context.remaining_phase_time_seconds == 0)
        if objective is None or objective.phase == Phase.CLOSING:
            return await self._store_close(
                candidate,
                candidate.session_id,
                user_id,
                reason=InterviewerReasonCode.SESSION_COMPLETE,
                execution=execution,
            )
        session = await self._advance_to_phase(
            candidate.session_id, user_id, session.phase, objective.phase
        )
        session = await self._state.register_primary_question(
            candidate.session_id, user_id, objective.objective_id
        )
        return await self._store(
            candidate,
            user_id,
            objective.initial_question,
            InterviewerTurnType.RECOVERY if recovery else InterviewerTurnType.TRANSITION,
            session.phase,
            objective,
            execution,
        )

    async def _advance_to_phase(
        self, session_id: UUID, user_id: UUID, current: Phase, target: Phase
    ):
        session = await self._state.get_state(session_id, user_id)
        while PHASE_ORDER.index(session.phase) < PHASE_ORDER.index(target):
            session = await self._state.advance_phase(session_id, user_id)
        return session

    @staticmethod
    def _next_objective(
        plan: InterviewPlan,
        current: InterviewerObjective,
        phase: Phase,
        phase_expired: bool,
    ) -> InterviewObjective | None:
        ordered = InterviewerContextBuilder.ordered_objectives(plan)
        try:
            current_index = next(
                index
                for index, objective in enumerate(ordered)
                if objective.objective_id == current.objective_id
            )
            candidates = ordered[current_index + 1 :]
        except StopIteration:
            candidates = ordered
        if phase_expired:
            candidates = [item for item in candidates if item.phase != phase]
        return candidates[0] if candidates else None

    async def _store_close(
        self,
        candidate: StoredInterviewTurn,
        session_id: UUID,
        user_id: UUID,
        *,
        reason: InterviewerReasonCode,
        text: str = "That concludes the interview. Thank you for your time.",
        execution: AgentExecutionResult | None = None,
    ) -> StoredInterviewTurn:
        session = await self._state.get_state(session_id, user_id)
        turn = await self._turns.create_interviewer_turn(
            session_id,
            user_id,
            response_to_turn_id=candidate.id,
            text=text,
            turn_type=InterviewerTurnType.CLOSING,
            phase=Phase.CLOSING,
            primary_thread_id=session.current_primary_question_id or "closing",
            agent_execution_id=execution.execution_id if execution else None,
            model=execution.model if execution else None,
            prompt_version=execution.prompt_version if execution else None,
            latency_ms=execution.latency_ms if execution else None,
            retry_count=execution.retry_count if execution else None,
            target_claim_ids=[],
            target_competency_ids=[],
        )
        await self._state.request_close(session_id, user_id)
        await self._state.record_event(
            session_id, user_id, "INTERVIEWER_CLOSE_REQUESTED", {"reason": reason.value}
        )
        return turn

    async def _store(
        self,
        candidate: StoredInterviewTurn,
        user_id: UUID,
        text: str,
        turn_type: InterviewerTurnType,
        phase: Phase,
        objective: InterviewObjective | InterviewerObjective,
        execution: AgentExecutionResult,
    ) -> StoredInterviewTurn:
        return await self._turns.create_interviewer_turn(
            candidate.session_id,
            user_id,
            response_to_turn_id=candidate.id,
            text=text,
            turn_type=turn_type,
            phase=phase,
            primary_thread_id=objective.objective_id,
            agent_execution_id=execution.execution_id,
            model=execution.model,
            prompt_version=execution.prompt_version,
            latency_ms=execution.latency_ms,
            retry_count=execution.retry_count,
            target_claim_ids=objective.target_claim_ids,
            target_competency_ids=objective.target_competency_ids,
        )

    async def _response(
        self,
        candidate: StoredInterviewTurn,
        interviewer: StoredInterviewTurn,
        user_id: UUID,
    ) -> TextTurnResponse:
        session = await self._state.get_state(candidate.session_id, user_id)
        _, remaining = self._state.remaining_times(session)
        return TextTurnResponse(
            session_id=candidate.session_id,
            candidate_turn_index=candidate.turn_index,
            interviewer_turn_index=interviewer.turn_index,
            question_text=interviewer.text,
            phase=interviewer.phase,
            turn_type=interviewer.turn_type,
            remaining_time_seconds=remaining,
        )

    @staticmethod
    def _start_response(
        opening: StoredInterviewTurn, remaining: int
    ) -> InterviewStartResponse:
        return InterviewStartResponse(
            session_id=opening.session_id,
            interviewer_turn_index=opening.turn_index,
            question_text=opening.text,
            phase=opening.phase,
            turn_type=opening.turn_type,
            remaining_time_seconds=remaining,
        )

