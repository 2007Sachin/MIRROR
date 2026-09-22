"""Practice modes run on the existing session, planner and engine, with a fixed short plan."""

import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.copy_guard import find_banned
from app.dashboard_summary import LatestReview, ReviewNextStep
from app.interview_map import AreaAction, Coverage, MatchStrength, WordMatcher, build_interview_map
from app.planner_models import PlannerProjectSummary, PlanningStatus
from app.practice_modes import (
    PracticeFocus,
    PracticeMode,
    budgets_for,
    build_practice_plan,
    practice_questions,
)
from app.practice_recommendation import RecommendationSource, recommend_practice
from app.schemas import SessionCreate
from tests.test_interview_map import NOW, OUTPUT, claim, competency, resume, role
from tests.test_interview_planner import USER_A, context, make_service


def planner_input(projects=True):
    source = context(uuid4()).planner_input
    if not projects:
        return source.model_copy(update={"projects": []})
    return source.model_copy(update={"projects": [PlannerProjectSummary(id=uuid4(), name="Pricing dashboard")]})


# ------------------------------------------------------------------ session contract


def test_short_modes_need_one_area_and_full_interviews_do_not() -> None:
    assert SessionCreate(target_role="Analyst").practice_mode == "FULL_INTERVIEW"
    SessionCreate(target_role="Analyst", practice_mode="QUICK_DRILL", practice_focus="impact")
    with pytest.raises(ValidationError):
        SessionCreate(target_role="Analyst", practice_mode="QUICK_DRILL")
    with pytest.raises(ValidationError):
        SessionCreate(target_role="Analyst", practice_mode="FOCUSED_PRACTICE", practice_focus="full")
    with pytest.raises(ValidationError):
        SessionCreate(target_role="Analyst", practice_mode="SPEED_ROUND", practice_focus="impact")
    with pytest.raises(ValidationError):
        SessionCreate(target_role="Analyst", practice_mode="QUICK_DRILL", practice_focus="unknown")


def test_a_theme_can_only_be_chosen_for_role_specific_practice() -> None:
    SessionCreate(target_role="Analyst", practice_mode="QUICK_DRILL", practice_focus="role", practice_theme="SQL")
    with pytest.raises(ValidationError):
        SessionCreate(target_role="Analyst", practice_mode="QUICK_DRILL", practice_focus="impact", practice_theme="SQL")


def test_budgets_are_short_for_short_modes_and_unchanged_for_full_interviews() -> None:
    assert budgets_for(PracticeMode.FULL_INTERVIEW, full_total=1800, full_phase=240) == (1800, 240)
    assert budgets_for(PracticeMode.QUICK_DRILL, full_total=1800, full_phase=240) == (300, 300)
    total, phase = budgets_for(PracticeMode.FOCUSED_PRACTICE, full_total=1800, full_phase=240)
    assert total == phase and total < 1800


# ------------------------------------------------------------------ the plan


def test_a_quick_drill_has_exactly_three_questions_and_one_follow_up_each() -> None:
    plan = build_practice_plan(PracticeMode.QUICK_DRILL, PracticeFocus.IMPACT, planner_input())
    assert len(plan.objectives) == 3
    assert all(objective.max_probes == 1 for objective in plan.objectives)
    assert plan.total_time_budget_seconds == 300
    assert len({objective.objective_id for objective in plan.objectives}) == 3


def test_focused_practice_is_a_little_longer_and_stays_on_one_area() -> None:
    plan = build_practice_plan(PracticeMode.FOCUSED_PRACTICE, PracticeFocus.DECISIONS, planner_input())
    assert len(plan.objectives) == 4
    assert all(objective.max_probes == 2 for objective in plan.objectives)
    assert {objective.objective for objective in plan.objectives} == {"Practise explaining decisions."}


def test_questions_name_a_project_only_when_the_candidate_has_one() -> None:
    with_project = practice_questions(PracticeFocus.PROJECT, 3, planner_input())
    assert any("Pricing dashboard" in question for question in with_project)
    without = practice_questions(PracticeFocus.PROJECT, 3, planner_input(projects=False))
    assert not any("{project}" in question or "Pricing dashboard" in question for question in without)


def test_role_practice_uses_the_chosen_theme_or_the_roles_top_competency() -> None:
    source = planner_input()
    chosen = practice_questions(PracticeFocus.ROLE, 3, source, theme="Stakeholder management")
    assert chosen[0].startswith("Stakeholder management")
    top = max(source.role_competencies, key=lambda item: item.importance_weight).name
    assert top.lower() in practice_questions(PracticeFocus.ROLE, 3, source)[0].lower()


def test_every_practice_question_is_plain_and_ends_as_a_question_or_request() -> None:
    for focus in PracticeFocus:
        if focus == PracticeFocus.FULL:
            with pytest.raises(ValueError):
                practice_questions(focus, 3, planner_input())
            continue
        source = planner_input()
        themes = [item.name for item in source.role_competencies]
        for question in practice_questions(focus, 4, source):
            mirror_words = question
            for theme in themes:  # a theme is the job description's own wording
                mirror_words = mirror_words.replace(theme, "")
            assert not find_banned(mirror_words), question
            assert question[0].isupper() and "{" not in question


def test_the_planner_builds_a_drill_without_calling_the_model() -> None:
    service, plans, provider, engine = make_service()  # the model has no queued answers

    async def run():
        created = await engine.create_session_state(
            USER_A, SessionCreate(target_role="Data Analyst", practice_mode="QUICK_DRILL", practice_focus="impact")
        )
        assert created.total_time_budget_seconds == 300
        await engine.begin_preparation(created.id, USER_A)
        plans.contexts[created.id] = context(created.id)
        return await service.plan(created.id, USER_A)

    record = asyncio.run(run())
    assert record.status == PlanningStatus.COMPLETED
    assert record.plan is not None and len(record.plan.objectives) == 3
    assert record.planner_model == "deterministic"


def test_a_full_interview_still_goes_to_the_planner_agent() -> None:
    service, plans, provider, engine = make_service()

    async def run():
        created = await engine.create_session_state(USER_A, SessionCreate(target_role="Data Analyst"))
        assert created.total_time_budget_seconds == 1200
        await engine.begin_preparation(created.id, USER_A)
        plans.contexts[created.id] = context(created.id)
        return await service.plan(created.id, USER_A)

    record = asyncio.run(run())
    assert record.planner_model == "planner-test-model"  # the agent path, unchanged


# ------------------------------------------------------------------ recommendation


def _review(root_cause=None):
    return LatestReview(
        session_id=uuid4(), target_role="AR Analyst", completed_at=NOW, counts=None,
        dimensions=[], improvements=[], next_step=ReviewNextStep(title="t", body="b"), root_cause=root_cause,
    )


def test_a_role_preparation_area_is_recommended_first() -> None:
    claims = [claim(f"Improved reporting {i}") for i in range(4)]
    built = build_interview_map(role([competency("Experimentation")]), resume(OUTPUT, claims), has_resume_document=True)
    pick = recommend_practice(built, _review("TECHNICAL_DEPTH"))
    assert pick and pick.source == RecommendationSource.ROLE_AREA
    assert pick.focus == PracticeFocus.IMPACT and pick.mode == PracticeMode.QUICK_DRILL


def test_the_latest_review_is_used_when_the_role_has_no_practice_area() -> None:
    built = build_interview_map(role([competency("Data analysis")]), resume(OUTPUT), has_resume_document=True)
    pick = recommend_practice(built, _review("TECHNICAL_DEPTH"))
    assert pick and pick.source == RecommendationSource.REVIEW and pick.focus == PracticeFocus.DECISIONS


def test_a_map_gap_becomes_role_practice_on_that_theme() -> None:
    built = build_interview_map(role([competency("Experimentation")]), resume(OUTPUT), has_resume_document=True)
    pick = recommend_practice(built, None)
    assert pick and pick.source == RecommendationSource.MAP_GAP
    assert pick.focus == PracticeFocus.ROLE and pick.theme == "Experimentation"


def test_nothing_to_go_on_means_no_recommendation_rather_than_an_invented_one() -> None:
    covered = build_interview_map(role([competency("Data analysis")]), resume(OUTPUT), has_resume_document=True)
    assert all(theme.coverage != Coverage.MISSING for theme in covered.themes)
    assert recommend_practice(covered, None) is None
    unread = build_interview_map(role([competency("SQL")], status="PROCESSING"), None, has_resume_document=False)
    assert recommend_practice(unread, _review("TECHNICAL_DEPTH")) is None


def test_missing_experience_is_not_turned_into_a_practice_recommendation() -> None:
    built = build_interview_map(role([competency("Experimentation")]), None, has_resume_document=False)
    assert built.preparation_areas[0].action == AreaAction.ADD_EXPERIENCE
    assert recommend_practice(built, None) is None


# ------------------------------------------------------------------ matcher


def test_the_matcher_grades_none_weak_and_useful() -> None:
    matcher = WordMatcher()
    assert matcher.strength("Data analysis", "Built data analysis for planning") == MatchStrength.USEFUL
    assert matcher.strength("Stakeholder management", "Managed the office move") == MatchStrength.WEAK
    assert matcher.strength("Experimentation", "Wrote release notes") == MatchStrength.NONE
    assert matcher.strength("Stakeholder communication", "Presented findings to clients") == MatchStrength.USEFUL
    assert matcher.strength("Reports", "Built monthly report") == MatchStrength.USEFUL  # plural folded


def test_a_weak_overlap_with_work_is_only_mentioned_not_experience() -> None:
    built = build_interview_map(role([competency("Stakeholder management")]), resume(OUTPUT), has_resume_document=True)
    assert built.themes[0].coverage == Coverage.MENTIONED
