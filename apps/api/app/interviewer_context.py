from __future__ import annotations

from uuid import UUID

from .flag_activation import FlagEligibilityService
from .interview_engine import InterviewStateMachine
from .interviewer_models import (
    InterviewerContext,
    InterviewerObjective,
    RecentInterviewTurn,
)
from .interviewer_repository import InterviewTurnRepository
from .planner_models import InterviewObjective, InterviewPlan
from .planner_repository import InterviewPlanRepository
from .schemas import SessionStatus


class InterviewPlanUnavailableForSession(Exception):
    pass


class InterviewerContextBuilder:
    """Builds the minimal, objective-scoped model context."""

    def __init__(
        self,
        state_machine: InterviewStateMachine,
        plans: InterviewPlanRepository,
        turns: InterviewTurnRepository,
        flags: FlagEligibilityService | None = None,
    ) -> None:
        self._state = state_machine
        self._plans = plans
        self._turns = turns
        self._flags = flags

    async def get_plan(self, session_id: UUID, user_id: UUID) -> InterviewPlan:
        record = await self._plans.get_active(session_id, user_id)
        if record is None or record.plan is None:
            raise InterviewPlanUnavailableForSession
        return record.plan

    async def opening_objective(
        self, session_id: UUID, user_id: UUID
    ) -> InterviewObjective:
        plan = await self.get_plan(session_id, user_id)
        return self._ordered(plan)[0]

    async def build(
        self, session_id: UUID, user_id: UUID, current_turn_index: int
    ) -> InterviewerContext:
        session = await self._state.get_state(session_id, user_id)
        plan = await self.get_plan(session_id, user_id)
        turns = await self._turns.list_turns(session_id, limit=6)
        objective = self._current_objective(plan, session.current_primary_question_id)
        claims = await self._turns.get_claims(user_id, objective.target_claim_ids)
        competencies = await self._turns.get_competencies(
            user_id, objective.target_competency_ids
        )
        remaining_phase, remaining_total = self._state.remaining_times(session)
        pending_flag = None
        if self._flags:
            pending_flag = await self._flags.select(
                session_id,
                user_id,
                current_turn_index,
                session_active=session.status == SessionStatus.ACTIVE,
                probe_count=session.current_probe_count,
                relevant_claim_ids=objective.target_claim_ids,
            )
        return InterviewerContext(
            session_id=session_id,
            current_turn_index=current_turn_index,
            phase=session.phase,
            objective=InterviewerObjective.model_validate(
                objective.model_dump(
                    include={
                        "objective_id",
                        "phase",
                        "objective",
                        "priority",
                        "target_claim_ids",
                        "target_competency_ids",
                        "target_project_ids",
                        "initial_question",
                        "question_intent",
                        "time_budget_seconds",
                        "max_probes",
                        "difficulty_start",
                    }
                )
            ),
            recent_turns=[
                RecentInterviewTurn(
                    turn_index=turn.turn_index,
                    speaker=turn.speaker,
                    text=turn.text,
                    turn_type=turn.turn_type,
                    phase=turn.phase,
                )
                for turn in turns
            ],
            relevant_claims=claims,
            relevant_competencies=competencies,
            primary_thread_id=session.current_primary_question_id,
            probe_count=session.current_probe_count,
            remaining_phase_time_seconds=remaining_phase,
            remaining_time_seconds=remaining_total,
            pending_flag=pending_flag,
        )

    @staticmethod
    def ordered_objectives(plan: InterviewPlan) -> list[InterviewObjective]:
        return InterviewerContextBuilder._ordered(plan)

    @staticmethod
    def _ordered(plan: InterviewPlan) -> list[InterviewObjective]:
        phase_order = {
            "INTRO": 0,
            "BACKGROUND": 1,
            "PROJECTS": 2,
            "ROLE_CORE": 3,
            "DEEP_DIVE": 4,
            "BEHAVIOURAL": 5,
            "CLOSING": 6,
        }
        return sorted(
            plan.objectives,
            key=lambda item: (phase_order[item.phase.value], plan.objectives.index(item)),
        )

    @classmethod
    def _current_objective(
        cls, plan: InterviewPlan, primary_thread_id: str | None
    ) -> InterviewObjective:
        ordered = cls._ordered(plan)
        if primary_thread_id:
            for objective in ordered:
                if objective.objective_id == primary_thread_id:
                    return objective
        return ordered[0]

