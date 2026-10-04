"""P4 seams: practice questions override, planner prompt loader, target-scoped progress.

Every seam defaults to today's behaviour: no loader / empty prompts -> the same plan as before;
role progress still counts every practice of the role, target sessions included.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from app.planner_models import PlanningStatus
from app.practice_modes import PracticeFocus, PracticeMode, build_practice_plan
from app.role_progress import RoleProgressService
from app.schemas import SessionCreate
from tests.test_interview_planner import USER_A, context, make_service
from tests.test_practice_modes import planner_input
from tests.test_role_progress import (
    USER,
    FakeAttempts,
    FakeDashboard,
    FakeReports,
    FakeRoles,
    FakeTranscript,
    profile,
    report,
    session,
)

PROMPTS = [
    "Tell me about a time you noticed a problem outside your own task and decided to act on it.",
    "Tell me about a time a user's need changed how you built something.",
    "Tell me about a time you dug into the details to understand why something kept breaking.",
    "Tell me about a time you made something simpler for the people who had to use it.",
]


def _shape(plan):
    return [
        (o.objective_id, o.phase, o.initial_question, o.max_probes, o.time_budget_seconds, o.expected_signal, o.target_competency_ids)
        for o in plan.objectives
    ], plan.total_time_budget_seconds, plan.planning_version


# ------------------------------------------------------------------ practice_modes


def test_questions_override_keeps_ids_phases_budgets_and_probes() -> None:
    source = planner_input()
    base = build_practice_plan(PracticeMode.FOCUSED_PRACTICE, PracticeFocus.ROLE, source, theme="Examples from your own work")
    over = build_practice_plan(
        PracticeMode.FOCUSED_PRACTICE, PracticeFocus.ROLE, source, theme="Examples from your own work", questions=PROMPTS,
    )
    assert [o.initial_question for o in over.objectives] == PROMPTS
    strip = lambda plan: [(a, b, d, e, f, g) for a, b, _, d, e, f, g in _shape(plan)[0]]  # noqa: E731
    assert strip(over) == strip(base)
    assert [o.objective_id for o in over.objectives] == [f"practice-role-{i}" for i in range(1, 5)]


def test_questions_override_is_trimmed_to_the_mode_shape() -> None:
    plan = build_practice_plan(PracticeMode.QUICK_DRILL, PracticeFocus.ROLE, planner_input(), theme="Designing a system", questions=PROMPTS)
    assert [o.initial_question for o in plan.objectives] == PROMPTS[:3]


def test_no_override_is_identical_to_today() -> None:
    source = planner_input()
    for mode in (PracticeMode.QUICK_DRILL, PracticeMode.FOCUSED_PRACTICE):
        for focus in (PracticeFocus.ROLE, PracticeFocus.PROJECT, PracticeFocus.IMPACT):
            today = build_practice_plan(mode, focus, source)
            assert _shape(build_practice_plan(mode, focus, source, questions=())) == _shape(today)


# ------------------------------------------------------------------ planner loader


def _plan_with(loader, *, focus="role", theme="Examples from your own work"):
    service, plans, _, engine = make_service()
    if loader is not None:
        service._target_prompts = loader  # noqa: SLF001 - constructor wiring is covered below

    async def run():
        created = await engine.create_session_state(
            USER_A, SessionCreate(target_role="Data Analyst", practice_mode="FOCUSED_PRACTICE", practice_focus=focus, practice_theme=theme if focus == "role" else None),
        )
        await engine.begin_preparation(created.id, USER_A)
        plans.contexts[created.id] = context(created.id)
        return await service.plan(created.id, USER_A), created.id

    return asyncio.run(run())


def test_planner_uses_linked_prompts_when_the_loader_returns_them() -> None:
    calls = []

    async def loader(session_id, user_id):
        calls.append((session_id, user_id))
        return list(PROMPTS)

    record, session_id = _plan_with(loader)
    assert record.status == PlanningStatus.COMPLETED
    assert [o.initial_question for o in record.plan.objectives] == PROMPTS
    assert calls == [(session_id, USER_A)]


def test_planner_without_loader_or_with_empty_prompts_is_unchanged() -> None:
    async def empty(session_id, user_id):
        return []

    none_record, _ = _plan_with(None)
    empty_record, _ = _plan_with(empty)
    assert [o.initial_question for o in empty_record.plan.objectives] == [o.initial_question for o in none_record.plan.objectives]
    assert [o.objective_id for o in empty_record.plan.objectives] == [o.objective_id for o in none_record.plan.objectives]


def test_planner_loader_is_only_asked_for_role_practice() -> None:
    calls = []

    async def loader(session_id, user_id):
        calls.append(session_id)
        return list(PROMPTS)

    record, _ = _plan_with(loader, focus="impact")
    assert calls == []
    assert [o.initial_question for o in record.plan.objectives] != PROMPTS


def test_planning_service_accepts_the_loader_as_a_keyword() -> None:
    import inspect

    from app.planner_service import InterviewPlanningService

    parameter = inspect.signature(InterviewPlanningService.__init__).parameters["target_prompts"]
    assert parameter.default is None


def test_dependency_wiring_passes_a_loader_that_is_empty_when_targets_are_off() -> None:
    from app.dependencies import _target_prompt_texts

    assert asyncio.run(_target_prompt_texts(uuid4(), uuid4())) == []


# ------------------------------------------------------------------ target-scoped progress


def _progress_world():
    role = profile(USER, "Software Development Engineer")
    linked_old, linked_new = session(role.id, days_ago=5, mode="FOCUSED_PRACTICE", focus="role"), session(role.id, days_ago=1, mode="QUICK_DRILL", focus="role")
    plain = session(role.id, days_ago=3)
    reports = {s.id: report() for s in (linked_old, linked_new, plain)}
    service = RoleProgressService(
        FakeRoles({USER: [(role, frozenset({role.id}))]}),
        FakeDashboard({USER: [linked_new, plain, linked_old]}),
        FakeReports(reports),
        FakeTranscript({}, {}),
        FakeAttempts(),
    )
    return service, role, (linked_old, linked_new), plain


def test_target_progress_counts_only_linked_sessions() -> None:
    service, role, linked, plain = _progress_world()
    progress = asyncio.run(service.target_detail(role.id, USER, frozenset(s.id for s in linked)))
    assert progress.practice_count == 2
    assert {p.session_id for p in progress.practices} == {s.id for s in linked}


def test_role_progress_still_counts_every_practice_of_the_role() -> None:
    service, role, linked, plain = _progress_world()
    progress = asyncio.run(service.detail(role.id, USER))
    assert progress.practice_count == 3
    assert {p.session_id for p in progress.practices} == {plain.id, *(s.id for s in linked)}


def test_target_progress_with_no_links_is_empty_not_the_role() -> None:
    service, role, _, _ = _progress_world()
    progress = asyncio.run(service.target_detail(role.id, USER, frozenset()))
    assert progress.practice_count == 0 and progress.practices == []


def test_target_progress_ignores_session_ids_outside_the_role_family() -> None:
    service, role, linked, _ = _progress_world()
    stranger = uuid4()
    progress = asyncio.run(service.target_detail(role.id, USER, frozenset({stranger, linked[0].id})))
    assert [p.session_id for p in progress.practices] == [linked[0].id]
