"""Behaviour 8 (+ planner half of 10): planner constraints, evaluated against the real
InterviewPlanningService with a scripted provider. Reuses the existing planner test doubles
(MemoryPlans, QueueProvider, context(), plan_output()) by loading them from the API test module.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

import ai_eval_checks as checks
import ai_eval_harness as h
from app.agents import AgentRegistry, AgentRunner, PromptLoader
from app.agents.definitions import ProviderResponse
from app.agents.errors import ProviderFailureError
from app.agents.planner import create_planner_agent
from app.interview_engine import InterviewStateMachine
from app.interviewer_context import InterviewerContextBuilder
from app.planner_models import (
    InterviewPlan,
    InterviewPlanDraft,
    PlanCoverageSummary,
    PlanningStatus,
)
from app.planner_service import InterviewPlanningService
from app.repository import MemorySessionRepository
from app.schemas import SessionCreate
from app.state_machine import PHASE_ORDER
from datetime import UTC, datetime

pytestmark = pytest.mark.ai_eval

_PATH = Path(__file__).resolve().parents[2] / "apps" / "api" / "tests" / "test_interview_planner.py"
_spec = importlib.util.spec_from_file_location("mirror_api_planner_test_helpers", _PATH)
helpers = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = helpers
_spec.loader.exec_module(helpers)  # type: ignore[union-attr]


class NoNormalizePlanner(InterviewPlanningService):
    """Negative control: publishes the model's draft verbatim."""

    def _normalize(self, draft: InterviewPlanDraft, source):  # type: ignore[override]
        return InterviewPlan(
            **draft.model_dump(), session_id=source.session_id, target_role=source.target_role,
            total_time_budget_seconds=source.interview_duration_seconds, planning_version="broken",
            coverage_summary=PlanCoverageSummary(estimated_duration_seconds=0), created_at=datetime.now(UTC))


def make(cls, provider):
    sessions, plans = MemorySessionRepository(), helpers.MemoryPlans()
    registry = AgentRegistry()
    registry.register(create_planner_agent("planner-test-model"))
    service = cls(sessions, plans, AgentRunner(registry, provider, PromptLoader(), execution_logger=h.NullLogger()),
                  model="planner-test-model", intro_reserve_seconds=60, transition_reserve_seconds=60,
                  closing_reserve_seconds=60)
    engine = InterviewStateMachine(sessions, total_time_budget_seconds=1200, phase_time_budget_seconds=180)
    return service, plans, engine


def run_plan(cls, mutate=None, provider=None, *, include_repo=False):
    """Returns (record, planner_input), optionally with the actual in-memory plans repo."""
    holder = {}

    class LateBound:
        requests: list = []

        async def complete(self, request, *, timeout_seconds):
            draft = helpers.plan_output(holder["sid"], max_probes=4)
            if mutate:
                mutate(draft)
            return ProviderResponse(content=draft)

    service, plans, engine = make(cls, provider or LateBound())

    async def go():
        created = await engine.create_session_state(helpers.USER_A, SessionCreate(target_role="Data Analyst"))
        await engine.begin_preparation(created.id, helpers.USER_A)
        holder["sid"] = created.id
        plans.contexts[created.id] = helpers.context(created.id, career_stage="EXPERIENCED")
        return await service.plan(created.id, helpers.USER_A), plans.contexts[created.id].planner_input

    result = asyncio.run(go())
    return (*result, plans) if include_repo else result


def hostile(draft):
    """Out-of-order phases, over-budget, excess probes, ids the planner was never given."""
    objs = draft["objectives"]
    objs.reverse()
    for o in objs:
        o["time_budget_seconds"] = 900
        o["max_probes"] = 9
    objs[0]["target_claim_ids"].append("99999999-0000-4000-8000-000000000001")
    objs[1]["target_competency_ids"].append("99999999-0000-4000-8000-000000000002")
    objs[2]["target_project_ids"].append("99999999-0000-4000-8000-000000000003")


def consumed(plan):
    """Phase order is enforced where the plan is consumed (interviewer_context.py:141), not stored."""
    return InterviewerContextBuilder.ordered_objectives(plan)


def test_b8_planner_obeys_constraints_on_hostile_model_output():
    record, planner_input = run_plan(InterviewPlanningService, hostile)
    assert record.status == PlanningStatus.COMPLETED and record.plan
    assert checks.check_plan_constraints(record.plan, planner_input, PHASE_ORDER,
                                         ordered=consumed(record.plan)) == []
    # the stored order is the model's (reversed) order: ordering is a consumer-side guarantee
    assert checks.check_plan_constraints(record.plan, planner_input, PHASE_ORDER)


def test_b8_planner_obeys_constraints_on_well_behaved_model_output():
    record, planner_input = run_plan(InterviewPlanningService)
    assert record.plan and checks.check_plan_constraints(
        record.plan, planner_input, PHASE_ORDER, ordered=consumed(record.plan)) == []


def test_b8_complete_phase_objective_is_rejected_not_published():
    def with_complete(draft):
        draft["objectives"][1]["phase"] = "COMPLETE"

    record, _ = run_plan(InterviewPlanningService, with_complete)
    assert record.status == PlanningStatus.FAILED and record.plan is None
    assert record.error_type in {"validation_failure", "plan_validation_failure"}


def test_b8_negative_control_planner_without_normalisation():
    record, planner_input = run_plan(NoNormalizePlanner, hostile)
    violations = checks.check_plan_constraints(record.plan, planner_input, PHASE_ORDER,
                                               ordered=record.plan.objectives)
    joined = "\n".join(violations)
    for needle in ("exceeds budget", "max_probes", "unknown claim", "unknown competency", "unknown project"):
        assert needle in joined, needle


def test_b8_check_fn_flags_complete_phase_and_disorder():
    """The check itself must catch COMPLETE objectives and phase disorder even though the real
    system never emits them."""
    record, planner_input = run_plan(InterviewPlanningService)
    plan = record.plan
    broken = plan.model_copy(update={"objectives": [
        plan.objectives[-1], *plan.objectives[:-1],
        plan.objectives[0].model_copy(update={"phase": "COMPLETE", "objective_id": "x-complete"})]})
    violations = checks.check_plan_constraints(broken, planner_input, PHASE_ORDER)
    assert any("COMPLETE-phase" in v for v in violations) and any("out of order" in v for v in violations)


# ------------------------------------------------------------- (10) planner failure degrades safely
class Raising:
    async def complete(self, request, *, timeout_seconds):
        raise ProviderFailureError("down")


class Fabricating(InterviewPlanningService):
    """Negative control: on model failure it publishes a canned plan instead of failing."""

    async def plan(self, session_id, user_id):
        record = await super().plan(session_id, user_id)
        if record.status == PlanningStatus.FAILED:
            return record.model_copy(update={"status": PlanningStatus.COMPLETED, "error_type": None,
                                             "plan": object()})
        return record


def test_b10_planner_failure_repository_contains_no_published_plan():
    record, _, plans = run_plan(InterviewPlanningService, provider=Raising(), include_repo=True)
    persisted = [item for rows in plans.records.values() for item in rows]
    assert len(persisted) == 1  # failure record is stored, not generated plan content
    assert persisted[0].status == PlanningStatus.FAILED
    assert persisted[0].error_type == record.error_type
    assert all(item.plan is None for item in persisted)


def test_b10_planner_failure_is_typed_and_publishes_no_plan():
    record, _, plans = run_plan(InterviewPlanningService, provider=Raising(), include_repo=True)
    published = sum(item.plan is not None for rows in plans.records.values() for item in rows)
    outcome = {"name": "planner", "error_type": record.error_type, "content": record.plan,
               "stored": published}
    assert record.status == PlanningStatus.FAILED
    assert checks.check_safe_degradation([outcome]) == []


def test_b10_negative_control_planner_fabricates_plan():
    record, _, plans = run_plan(Fabricating, provider=Raising(), include_repo=True)
    published = sum(item.plan is not None for rows in plans.records.values() for item in rows)
    outcome = {"name": "planner", "error_type": record.error_type, "content": record.plan,
               "stored": published}
    assert checks.check_safe_degradation([outcome])
