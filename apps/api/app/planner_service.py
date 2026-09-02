from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from math import ceil
from uuid import UUID

from .agents.definitions import AgentExecutionContext
from .agents.planner import (
    PLANNER_AGENT_NAME,
    PLANNER_PROMPT_VERSION,
    PLANNING_VERSION,
)
from .agents.runner import AgentRunner
from .planner_models import (
    DifficultyStart,
    InterviewObjective,
    InterviewPlan,
    InterviewPlanDraft,
    InterviewPlanRecord,
    InterviewPlanResponse,
    PlanCoverageSummary,
    PlanningResponse,
    PlanningStatus,
    PlanSummary,
    PublicInterviewPlan,
)
from .planner_repository import InterviewPlanRepository
from .repository import SessionRepository
from .schemas import Phase, SessionStatus


logger = logging.getLogger("mirror.interview_planning")


class PlanNotFound(Exception):
    pass


class SessionNotPlannable(Exception):
    pass


class InvalidInterviewPlan(Exception):
    pass


class InterviewPlanningService:
    def __init__(
        self,
        sessions: SessionRepository,
        plans: InterviewPlanRepository,
        runner: AgentRunner,
        *,
        model: str,
        intro_reserve_seconds: int,
        transition_reserve_seconds: int,
        closing_reserve_seconds: int,
    ) -> None:
        if (
            min(
                intro_reserve_seconds,
                transition_reserve_seconds,
                closing_reserve_seconds,
            )
            < 0
        ):
            raise ValueError("planner reserves cannot be negative")
        self._sessions = sessions
        self._plans = plans
        self._runner = runner
        self._model = model
        self._intro_reserve = intro_reserve_seconds
        self._transition_reserve = transition_reserve_seconds
        self._closing_reserve = closing_reserve_seconds

    async def plan(self, session_id: UUID, user_id: UUID) -> InterviewPlanRecord:
        session = await self._sessions.get(session_id, user_id)
        if session is None:
            raise PlanNotFound
        if session.status not in (SessionStatus.PREPARING, SessionStatus.READY):
            raise SessionNotPlannable
        context = await self._plans.load_context(
            session_id,
            user_id,
            target_role=session.target_role,
            duration_seconds=session.total_time_budget_seconds,
        )
        record, started = await self._plans.begin(
            session_id,
            user_id,
            model=self._model,
            prompt_version=PLANNER_PROMPT_VERSION,
            planning_version=PLANNING_VERSION,
        )
        if not started:
            return record

        result = await self._runner.run(
            PLANNER_AGENT_NAME,
            context.planner_input,
            context=AgentExecutionContext(session_id=session_id, user_id=user_id),
        )
        if not result.success or result.output is None:
            failed = await self._plans.fail(
                record.id,
                user_id,
                result.execution_id,
                result.error_type.value if result.error_type else "internal_failure",
            )
            self._log(result, context.planner_input, failed, 0, 0)
            return failed

        try:
            draft = InterviewPlanDraft.model_validate(result.output)
            normalized = self._normalize(draft, context.planner_input)
        except (ValueError, InvalidInterviewPlan):
            failed = await self._plans.fail(
                record.id, user_id, result.execution_id, "plan_validation_failure"
            )
            self._log(result, context.planner_input, failed, 0, 0)
            return failed

        completed = await self._plans.complete(
            record.id, user_id, result.execution_id, normalized
        )
        self._log(
            result,
            context.planner_input,
            completed,
            len(normalized.objectives),
            normalized.coverage_summary.estimated_duration_seconds,
        )
        return completed

    async def get(self, session_id: UUID, user_id: UUID) -> InterviewPlanRecord:
        if await self._sessions.get(session_id, user_id) is None:
            raise PlanNotFound
        plan = await self._plans.get_active(session_id, user_id)
        if plan is None:
            raise PlanNotFound
        return plan

    @staticmethod
    def response(record: InterviewPlanRecord) -> PlanningResponse:
        plan = record.plan
        return PlanningResponse(
            planning_status=record.status,
            plan_id=record.id,
            version=record.version,
            summary=PlanSummary(
                objective_count=len(plan.objectives) if plan else 0,
                estimated_duration_seconds=(
                    plan.coverage_summary.estimated_duration_seconds if plan else 0
                ),
                phases=(
                    list(
                        dict.fromkeys(objective.phase for objective in plan.objectives)
                    )
                    if plan
                    else []
                ),
            ),
        )

    @staticmethod
    def detail(record: InterviewPlanRecord) -> InterviewPlanResponse:
        public_plan = (
            PublicInterviewPlan.model_validate(
                record.plan.model_dump(exclude={"coverage_summary"})
            )
            if record.plan
            else None
        )
        return InterviewPlanResponse(
            id=record.id,
            session_id=record.session_id,
            version=record.version,
            status=record.status,
            plan=public_plan,
        )

    def _normalize(self, draft: InterviewPlanDraft, source) -> InterviewPlan:
        if draft.session_id != source.session_id:
            raise InvalidInterviewPlan("plan session does not match input")
        if draft.target_role.casefold() != source.target_role.casefold():
            raise InvalidInterviewPlan("plan target role does not match input")
        if draft.total_time_budget_seconds != source.interview_duration_seconds:
            raise InvalidInterviewPlan(
                "plan duration does not match configured duration"
            )
        if draft.planning_version != PLANNING_VERSION:
            raise InvalidInterviewPlan("planning version mismatch")
        if not any(item.phase == Phase.INTRO for item in draft.objectives):
            raise InvalidInterviewPlan("an INTRO objective is required")
        if not any(item.phase == Phase.CLOSING for item in draft.objectives):
            raise InvalidInterviewPlan("a CLOSING objective is required")

        claim_ids = {item.id for item in source.claims_summary}
        competency_ids = {item.id for item in source.role_competencies}
        project_ids = {item.id for item in source.projects}
        for objective in draft.objectives:
            if not set(objective.target_claim_ids) <= claim_ids:
                raise InvalidInterviewPlan("plan references an unknown claim")
            if not set(objective.target_competency_ids) <= competency_ids:
                raise InvalidInterviewPlan("plan references an unknown competency")
            if not set(objective.target_project_ids) <= project_ids:
                raise InvalidInterviewPlan("plan references an unknown project")

        beginner = source.career_stage in {
            "STUDENT",
            "FINAL_YEAR_STUDENT",
            "FRESHER",
        }
        objectives = [
            objective.model_copy(
                update={
                    "max_probes": min(2, objective.max_probes),
                    "difficulty_start": (
                        DifficultyStart.BASIC
                        if beginner
                        and objective.difficulty_start
                        in (DifficultyStart.INTERMEDIATE, DifficultyStart.ADVANCED)
                        else objective.difficulty_start
                    ),
                }
            )
            for objective in draft.objectives
        ]
        objectives = self._limit_project_dominance(objectives)
        objectives = self._normalize_time(objectives, source.interview_duration_seconds)

        targeted_claims = {
            claim_id for item in objectives for claim_id in item.target_claim_ids
        }
        targeted_competencies = {
            competency_id
            for item in objectives
            for competency_id in item.target_competency_ids
        }
        targeted_projects = {
            project_id for item in objectives for project_id in item.target_project_ids
        }
        high_claims = set(source.high_verification_priority_claims)
        if high_claims and not targeted_claims.intersection(high_claims):
            raise InvalidInterviewPlan("no high-priority claim receives coverage")
        critical = {
            item.id
            for item in source.role_competencies
            if item.importance_weight >= 0.8
        }
        if critical and not targeted_competencies.intersection(critical):
            raise InvalidInterviewPlan("no role-critical competency receives coverage")

        uncovered = [f"claim:{item}" for item in sorted(high_claims - targeted_claims)]
        uncovered.extend(
            f"competency:{item}" for item in sorted(critical - targeted_competencies)
        )
        estimated = (
            sum(item.time_budget_seconds for item in objectives)
            + self._transition_reserve
        )
        return InterviewPlan(
            **draft.model_dump(exclude={"objectives", "coverage_summary"}),
            objectives=objectives,
            coverage_summary=PlanCoverageSummary(
                role_competency_coverage=sorted(targeted_competencies),
                claims_targeted=sorted(targeted_claims),
                projects_targeted=sorted(targeted_projects),
                uncovered_high_priority_items=uncovered,
                estimated_duration_seconds=estimated,
            ),
            created_at=datetime.now(UTC),
        )

    def _normalize_time(
        self, objectives: list[InterviewObjective], duration: int
    ) -> list[InterviewObjective]:
        available = duration - self._transition_reserve
        if available < 60:
            raise InvalidInterviewPlan("interview duration is too short")
        normalized = list(objectives)
        for phase, reserve in (
            (Phase.INTRO, self._intro_reserve),
            (Phase.CLOSING, self._closing_reserve),
        ):
            matching = [
                index for index, item in enumerate(normalized) if item.phase == phase
            ]
            if matching and reserve:
                index = matching[0]
                item = normalized[index]
                normalized[index] = item.model_copy(
                    update={
                        "time_budget_seconds": max(item.time_budget_seconds, reserve)
                    }
                )
        overflow = sum(item.time_budget_seconds for item in normalized) - available
        if overflow <= 0:
            return normalized
        reduction_order = sorted(
            range(len(normalized)),
            key=lambda index: (
                normalized[index].priority == "HIGH",
                normalized[index].phase in (Phase.INTRO, Phase.CLOSING),
            ),
        )
        for index in reduction_order:
            floor = 30
            if normalized[index].phase == Phase.INTRO:
                floor = max(floor, self._intro_reserve)
            elif normalized[index].phase == Phase.CLOSING:
                floor = max(floor, self._closing_reserve)
            reducible = normalized[index].time_budget_seconds - floor
            reduction = min(max(0, reducible), overflow)
            if reduction:
                normalized[index] = normalized[index].model_copy(
                    update={
                        "time_budget_seconds": normalized[index].time_budget_seconds
                        - reduction
                    }
                )
                overflow -= reduction
            if overflow == 0:
                break
        if overflow:
            raise InvalidInterviewPlan("objectives cannot fit the configured duration")
        return normalized

    @staticmethod
    def _limit_project_dominance(
        objectives: list[InterviewObjective],
    ) -> list[InterviewObjective]:
        substantive = [
            item
            for item in objectives
            if item.phase not in (Phase.INTRO, Phase.CLOSING)
        ]
        maximum = max(1, ceil(len(substantive) / 2))
        seen: Counter[UUID] = Counter()
        normalized: list[InterviewObjective] = []
        for objective in objectives:
            projects = []
            for project_id in objective.target_project_ids:
                if seen[project_id] < maximum:
                    projects.append(project_id)
                    seen[project_id] += 1
            normalized.append(
                objective.model_copy(update={"target_project_ids": projects})
            )
        return normalized

    @staticmethod
    def _log(result, source, record, objective_count: int, duration: int) -> None:
        logger.info(
            "interview_planning_completed",
            extra={
                "planning_execution_id": str(result.execution_id),
                "session_id": str(source.session_id),
                "planner_model": result.model,
                "prompt_version": result.prompt_version,
                "claims_count": len(source.claims_summary),
                "competencies_count": len(source.role_competencies),
                "planned_objective_count": objective_count,
                "estimated_duration": duration,
                "latency_ms": result.latency_ms,
                "retry_count": result.retry_count,
                "success": record.status == PlanningStatus.COMPLETED,
            },
        )

