from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import UUID

from .config import get_settings
from .deferred_writes import get_deferred_writes
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
from .schemas import Phase, SessionRead, SessionStatus


logger = logging.getLogger("mirror.interviewer")


class CandidateTurnCompletedPublisher(Protocol):
    async def publish_candidate_turn_completed(
        self, session_id: UUID, user_id: UUID, turn_id: UUID
    ) -> None: ...


class OpeningProfileReader(Protocol):
    """Only the candidate's name is needed, so the greeting stays decoupled."""

    async def get(self, user_id: UUID) -> object | None: ...

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


# The opening turn carries a short spoken welcome before the first question so the
# interview begins like a conversation rather than an interrogation. It is composed
# deterministically here rather than by the agent: a greeting is lifecycle framing,
# not interview content, and it must never vary in a way that implies evaluation.
GREETING_SEPARATOR = "\n\n"


def _first_name(full_name: str | None) -> str:
    cleaned = " ".join((full_name or "").split())
    if not cleaned:
        return ""
    first = cleaned.split(" ")[0]
    return first if 1 < len(first) <= 24 and first.replace("-", "").isalpha() else ""


def compose_opening_greeting(
    *, full_name: str | None, target_role: str | None, total_time_budget_seconds: int
) -> str:
    """Build the welcome that precedes the first question."""
    name = _first_name(full_name)
    minutes = max(1, round((total_time_budget_seconds or 0) / 60))
    role = " ".join((target_role or "").split())

    opener = f"Hi {name}, I'm Mirror." if name else "Hi, I'm Mirror."
    who = (
        f"This is your {role} conversation."
        if role
        else "This is your practice conversation."
    )
    shape = (
        "There are no trick questions, just your experience in your own words. "
        f"We have about {minutes} minutes, so take your time."
    )
    return " ".join([opener, who, shape])


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
        profiles: OpeningProfileReader | None = None,
    ) -> None:
        self._state = state
        self._context = context_builder
        self._turns = turns
        self._runner = runner
        self._turn_completed_publisher = turn_completed_publisher
        self._flag_eligibility = flag_eligibility
        self._profiles = profiles

    async def _candidate_first_name(self, user_id: UUID) -> str | None:
        """A missing name only makes the greeting less personal, never blocks it."""
        if self._profiles is None:
            return None
        try:
            profile = await self._profiles.get(user_id)
        except Exception:  # noqa: BLE001 - greeting must not fail the interview
            logger.warning("Could not read profile for interview greeting", exc_info=True)
            return None
        return getattr(profile, "full_name", None) if profile else None

    async def start(self, session_id: UUID, user_id: UUID) -> InterviewStartResponse:
        session = await self._state.get_state(session_id, user_id)
        existing = await self._turns.list_turns(session_id)
        resumed = False
        if session.status == SessionStatus.ACTIVE and self._state.is_paused(session):
            # Coming back to a saved conversation picks the timer up where it stopped.
            session = await self._state.resume(session_id, user_id)
            resumed = True
        elif session.status == SessionStatus.ACTIVE:
            # A tab that closed without saving must not eat the interview's time while it was away.
            credited = await self._state.credit_idle_time(
                session_id, user_id, idle_seconds=get_settings().session_idle_credit_seconds
            )
            resumed = credited.started_at != session.started_at
            session = credited
        if session.status == SessionStatus.ACTIVE and existing:
            latest_interviewer = next(
                (turn for turn in reversed(existing) if turn.speaker.value == "INTERVIEWER"),
                None,
            )
            if latest_interviewer:
                _, remaining = self._state.remaining_times(session)
                response = self._start_response(latest_interviewer, remaining)
                if resumed:
                    response = response.model_copy(
                        update={"welcome_back": True, "welcome_text": WELCOME_BACK_TEXT}
                    )
                return response

        objective = await self._context.opening_objective(session_id, user_id)
        if session.status == SessionStatus.READY:
            session = await self._state.start(session_id, user_id)
        if session.current_primary_question_id != objective.objective_id:
            session = await self._state.register_primary_question(
                session_id, user_id, objective.objective_id
            )
        greeting = compose_opening_greeting(
            full_name=await self._candidate_first_name(user_id),
            target_role=session.target_role,
            total_time_budget_seconds=session.total_time_budget_seconds,
        )
        opening = await self._turns.create_interviewer_turn(
            session_id,
            user_id,
            response_to_turn_id=None,
            text=f"{greeting}{GREETING_SEPARATOR}{objective.initial_question}",
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
        session: SessionRead | None = None,
    ) -> TextTurnResponse:
        parallel = get_settings().voice_parallel_context
        if session is None:
            session = await self._state.get_state(session_id, user_id)
        if session.status != SessionStatus.ACTIVE:
            raise InterviewFlowRejected("session is not accepting candidate turns")

        plan_task = None
        recent_prefetch = None
        if parallel:
            # Start the plan read now; it does not depend on this turn.
            plan_task = asyncio.ensure_future(self._context.get_plan(session_id, user_id))
            existing_candidate, recent_prefetch = await asyncio.gather(
                self._turns.get_candidate_by_client_id(session_id, request.client_turn_id),
                self._turns.list_turns(session_id, limit=1),
            )
        else:
            existing_candidate = await self._turns.get_candidate_by_client_id(
                session_id, request.client_turn_id
            )
        if existing_candidate:
            if plan_task is not None:
                plan_task.cancel()
            existing_response = await self._turns.get_response(
                session_id, existing_candidate.id
            )
            if existing_response:
                if on_candidate_ready:
                    await on_candidate_ready(existing_candidate)
                return await self._response(existing_candidate, existing_response, user_id)

        recent = recent_prefetch if parallel else await self._turns.list_turns(session_id, limit=1)
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
        async def publish() -> None:
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

        _, remaining = self._state.remaining_times(session)
        if parallel:
            # The candidate turn now exists, so the reads that need it can start with the writes.
            jobs = [publish(), on_candidate_ready(candidate) if on_candidate_ready else _noop()]
            if remaining != 0:
                jobs.append(
                    self._context.build(
                        session_id, user_id, candidate.turn_index,
                        session=session, plan_task=plan_task,
                    )
                )
            results = await asyncio.gather(*jobs)
            context = results[2] if remaining != 0 else None
        else:
            await publish()
            if on_candidate_ready:
                await on_candidate_ready(candidate)
            context = None
        if remaining == 0:
            if plan_task is not None:
                plan_task.cancel()
            interviewer = await self._store_close(
                candidate, session_id, user_id, reason=InterviewerReasonCode.TIME_LIMIT
            )
            return await self._response(candidate, interviewer, user_id)

        if context is None:
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

        completed = self._state.record_event(
            session_id,
            user_id,
            "TEXT_TURN_COMPLETED",
            {
                "candidate_turn_index": candidate.turn_index,
                "interviewer_turn_index": interviewer.turn_index,
            },
        )
        if get_settings().voice_async_persist and on_candidate_ready is not None:
            # Voice turns only: the event is analytics. Text turns keep the write inline.
            completed.close()
            get_deferred_writes().enqueue(
                session_id,
                f"{request.client_turn_id}:text-event",
                lambda: self._state.record_event(
                    session_id,
                    user_id,
                    "TEXT_TURN_COMPLETED",
                    {
                        "candidate_turn_index": candidate.turn_index,
                        "interviewer_turn_index": interviewer.turn_index,
                    },
                ),
            )
            return await self._response(candidate, interviewer, user_id)
        if parallel:
            _, response = await asyncio.gather(
                completed, self._response(candidate, interviewer, user_id)
            )
            return response
        await completed
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
        planned = context.objective.initial_question.strip()
        already_asked = any(
            turn.speaker.value == "INTERVIEWER" and planned and planned in turn.text
            for turn in context.recent_turns
        )
        # Re-asking the same planned question makes the conversation feel stuck, so when it was
        # just asked the fallback moves on instead.
        if not already_asked and await self._state.can_ask_question(
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
        text: str = "Thank you for sharing all of that. That's the end of our conversation. Your reflection will be ready shortly.",
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



WELCOME_BACK_TEXT = "Welcome back. Thank you for coming back. Let's pick up where we were."


async def _noop() -> None:
    return None
