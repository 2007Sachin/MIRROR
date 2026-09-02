from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from .repository import SessionRepository
from .schemas import Phase, SessionCreate, SessionEventRead, SessionRead, SessionStatus


PHASE_ORDER = (
    Phase.INTRO,
    Phase.BACKGROUND,
    Phase.PROJECTS,
    Phase.ROLE_CORE,
    Phase.DEEP_DIVE,
    Phase.BEHAVIOURAL,
    Phase.CLOSING,
)

LEGAL_TRANSITIONS: dict[SessionStatus, frozenset[SessionStatus]] = {
    SessionStatus.CREATED: frozenset({SessionStatus.PREPARING, SessionStatus.FAILED}),
    SessionStatus.PREPARING: frozenset({SessionStatus.READY, SessionStatus.FAILED}),
    SessionStatus.READY: frozenset({SessionStatus.ACTIVE, SessionStatus.FAILED}),
    SessionStatus.ACTIVE: frozenset({SessionStatus.ASSESSING, SessionStatus.FAILED}),
    SessionStatus.ASSESSING: frozenset({SessionStatus.COMPLETED, SessionStatus.FAILED}),
    SessionStatus.COMPLETED: frozenset(),
    SessionStatus.FAILED: frozenset(),
}

MAX_PROBES_PER_PRIMARY_QUESTION = 2


class SessionNotFound(Exception):
    pass


class IllegalSessionTransition(Exception):
    pass


class InterviewFlowRejected(Exception):
    pass


class ConcurrentSessionChange(Exception):
    pass


class InterviewStateMachine:
    """Deterministic authority for lifecycle, phase, probe, and time rules."""

    def __init__(
        self,
        repository: SessionRepository,
        *,
        total_time_budget_seconds: int,
        phase_time_budget_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if total_time_budget_seconds <= 0 or phase_time_budget_seconds <= 0:
            raise ValueError("interview time budgets must be positive")
        self._repository = repository
        self._total_time_budget_seconds = total_time_budget_seconds
        self._phase_time_budget_seconds = phase_time_budget_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create_session_state(
        self, user_id: UUID, payload: SessionCreate
    ) -> SessionRead:
        return await self._repository.create(
            user_id,
            payload,
            total_time_budget_seconds=self._total_time_budget_seconds,
            phase_time_budget_seconds=self._phase_time_budget_seconds,
        )

    async def prepare(self, session_id: UUID, user_id: UUID) -> SessionRead:
        preparing = await self.begin_preparation(session_id, user_id)
        return await self.mark_ready(preparing.id, user_id)

    async def begin_preparation(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._require(session_id, user_id)
        return await self._transition(
            session,
            SessionStatus.PREPARING,
            "SESSION_PREPARING",
            {"from": session.status.value},
        )

    async def mark_ready(self, session_id: UUID, user_id: UUID) -> SessionRead:
        preparing = await self._require(session_id, user_id)
        return await self._transition(
            preparing,
            SessionStatus.READY,
            "SESSION_PREPARED",
            {"phase": preparing.phase.value},
            completion_pct=5,
        )

    async def start(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._require(session_id, user_id)
        now = self._clock()
        return await self._transition(
            session,
            SessionStatus.ACTIVE,
            "SESSION_STARTED",
            {"total_time_budget_seconds": session.total_time_budget_seconds},
            started_at=now,
            phase_started_at=now,
            elapsed_seconds=0,
        )

    async def can_ask_question(
        self, session_id: UUID, user_id: UUID, *, probe: bool = False
    ) -> bool:
        session = await self._require(session_id, user_id)
        if session.status != SessionStatus.ACTIVE or self._is_expired(session):
            return False
        if self._is_phase_expired(session):
            return False
        if session.phase in (Phase.CLOSING, Phase.COMPLETE):
            return False
        if probe:
            return bool(
                session.current_primary_question_id
                and session.current_probe_count < MAX_PROBES_PER_PRIMARY_QUESTION
            )
        return True

    async def register_primary_question(
        self, session_id: UUID, user_id: UUID, question_id: str
    ) -> SessionRead:
        session = await self._active(session_id, user_id)
        self._require_question_time(session)
        question_id = question_id.strip()
        if not question_id:
            raise InterviewFlowRejected("primary question id is required")
        return await self._apply(
            session,
            {
                "current_primary_question_id": question_id,
                "current_probe_count": 0,
                "total_questions": session.total_questions + 1,
                "elapsed_seconds": self._elapsed(session),
            },
            "PRIMARY_QUESTION_STARTED",
            {"question_id": question_id, "phase": session.phase.value},
        )

    async def register_probe(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._active(session_id, user_id)
        if not session.current_primary_question_id:
            raise InterviewFlowRejected("a probe requires an active primary question")
        self._require_question_time(session)
        if session.current_probe_count >= MAX_PROBES_PER_PRIMARY_QUESTION:
            raise InterviewFlowRejected("probe limit reached; recovery is required")
        probe_count = session.current_probe_count + 1
        updated = await self._apply(
            session,
            {
                "current_probe_count": probe_count,
                "elapsed_seconds": self._elapsed(session),
            },
            "PROBE_REGISTERED",
            {
                "question_id": session.current_primary_question_id,
                "probe_count": probe_count,
            },
        )
        if probe_count == MAX_PROBES_PER_PRIMARY_QUESTION:
            await self._repository.record_event(
                session.id,
                user_id,
                "PROBE_LIMIT_REACHED",
                {"question_id": session.current_primary_question_id},
            )
        return updated

    async def must_recover(
        self, session_id: UUID, user_id: UUID, *, repeated_inability: bool = False
    ) -> bool:
        session = await self._active(session_id, user_id)
        return (
            repeated_inability
            or session.current_probe_count >= MAX_PROBES_PER_PRIMARY_QUESTION
        )

    async def trigger_recovery(
        self, session_id: UUID, user_id: UUID, *, repeated_inability: bool = False
    ) -> SessionRead:
        session = await self._active(session_id, user_id)
        if not (
            repeated_inability
            or session.current_probe_count >= MAX_PROBES_PER_PRIMARY_QUESTION
        ):
            raise InterviewFlowRejected("recovery is not currently required")
        return await self._apply(
            session,
            {
                "current_primary_question_id": None,
                "current_probe_count": 0,
                "recovery_count": session.recovery_count + 1,
                "elapsed_seconds": self._elapsed(session),
            },
            "RECOVERY_TRIGGERED",
            {"reason": "repeated_inability" if repeated_inability else "probe_limit"},
        )

    async def advance_phase(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._active(session_id, user_id)
        if self._is_expired(session):
            raise InterviewFlowRejected("interview time budget is exhausted")
        current_index = PHASE_ORDER.index(session.phase)
        if current_index == len(PHASE_ORDER) - 1:
            raise InterviewFlowRejected("closing is the final active phase")
        next_phase = PHASE_ORDER[current_index + 1]
        return await self._apply(
            session,
            {
                "phase": next_phase,
                "phase_started_at": self._clock(),
                "current_primary_question_id": None,
                "current_probe_count": 0,
                "elapsed_seconds": self._elapsed(session),
                "completion_pct": self._phase_completion(next_phase),
            },
            "PHASE_CHANGED",
            {"from": session.phase.value, "to": next_phase.value},
        )

    async def request_close(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._active(session_id, user_id)
        return await self._transition(
            session,
            SessionStatus.ASSESSING,
            "SESSION_END_REQUESTED",
            {"elapsed_seconds": self._elapsed(session)},
            phase=Phase.CLOSING,
            phase_started_at=self._clock(),
            current_primary_question_id=None,
            current_probe_count=0,
            elapsed_seconds=self._elapsed(session),
            completion_pct=95,
        )

    async def complete(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._require(session_id, user_id)
        return await self._transition(
            session,
            SessionStatus.COMPLETED,
            "SESSION_ENDED",
            {"outcome": "completed"},
            phase=Phase.COMPLETE,
            completed_at=self._clock(),
            elapsed_seconds=self._elapsed(session),
            completion_pct=100,
        )

    async def fail(
        self, session_id: UUID, user_id: UUID, *, reason: str
    ) -> SessionRead:
        session = await self._require(session_id, user_id)
        if SessionStatus.FAILED not in LEGAL_TRANSITIONS[session.status]:
            raise IllegalSessionTransition
        return await self._transition(
            session,
            SessionStatus.FAILED,
            "SESSION_ENDED",
            {"outcome": "failed", "reason": reason[:500]},
            completed_at=self._clock(),
            elapsed_seconds=self._elapsed(session),
        )

    async def get_state(self, session_id: UUID, user_id: UUID) -> SessionRead:
        return await self._require(session_id, user_id)

    async def get_events(
        self, session_id: UUID, user_id: UUID
    ) -> list[SessionEventRead]:
        await self._require(session_id, user_id)
        return await self._repository.list_events(session_id, user_id)

    async def record_event(
        self, session_id: UUID, user_id: UUID, event_type: str, payload: dict
    ) -> SessionEventRead:
        await self._require(session_id, user_id)
        return await self._repository.record_event(
            session_id, user_id, event_type, payload
        )

    def remaining_times(self, session: SessionRead) -> tuple[int, int]:
        total = max(0, session.total_time_budget_seconds - self._elapsed(session))
        phase_elapsed = max(
            0, int((self._clock() - session.phase_started_at).total_seconds())
        )
        phase = max(0, session.phase_time_budget_seconds - phase_elapsed)
        return phase, total

    @staticmethod
    def flag_is_eligible(*, detected_at_turn: int, current_turn: int) -> bool:
        return current_turn >= detected_at_turn + 1

    async def _active(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._require(session_id, user_id)
        if session.status != SessionStatus.ACTIVE:
            raise IllegalSessionTransition
        return session

    async def _require(self, session_id: UUID, user_id: UUID) -> SessionRead:
        session = await self._repository.get(session_id, user_id)
        if session is None:
            raise SessionNotFound
        return session

    async def _transition(
        self,
        session: SessionRead,
        target: SessionStatus,
        event_type: str,
        payload: dict,
        **values: object,
    ) -> SessionRead:
        if target not in LEGAL_TRANSITIONS[session.status]:
            raise IllegalSessionTransition(
                f"{session.status.value} cannot transition to {target.value}"
            )
        return await self._apply(
            session, {"status": target, **values}, event_type, payload
        )

    async def _apply(
        self, session: SessionRead, values: dict, event_type: str, payload: dict
    ) -> SessionRead:
        updated = await self._repository.apply_state_change(
            session, values, event_type, payload
        )
        if updated is None:
            raise ConcurrentSessionChange
        return updated

    def _elapsed(self, session: SessionRead) -> int:
        if session.started_at is None:
            return session.elapsed_seconds
        elapsed = max(0, int((self._clock() - session.started_at).total_seconds()))
        return min(session.total_time_budget_seconds, elapsed)

    def _is_expired(self, session: SessionRead) -> bool:
        return self._elapsed(session) >= session.total_time_budget_seconds

    def _is_phase_expired(self, session: SessionRead) -> bool:
        elapsed = max(
            0, int((self._clock() - session.phase_started_at).total_seconds())
        )
        return elapsed >= session.phase_time_budget_seconds

    def _require_question_time(self, session: SessionRead) -> None:
        if self._is_expired(session):
            raise InterviewFlowRejected("interview time budget is exhausted")
        if self._is_phase_expired(session):
            raise InterviewFlowRejected("phase time budget is exhausted")

    @staticmethod
    def _phase_completion(phase: Phase) -> int:
        return round((PHASE_ORDER.index(phase) / len(PHASE_ORDER)) * 90)

