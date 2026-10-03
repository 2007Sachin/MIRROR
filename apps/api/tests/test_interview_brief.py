"""Night-before brief and debrief follow-ups: pure, deterministic, copy-clean."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.copy_guard import all_clean
from app.dashboard_summary import LatestReview, ReviewNextStep
from app.interview_brief import (
    LIMITATION_SOURCES,
    best_theme,
    build_brief,
    follow_ups,
    questions_to_ask,
    timing,
)
from app.interview_event_models import (
    FollowUpAction,
    InterviewDebriefWrite,
    InterviewEventCreate,
    InterviewEventRecord,
    Timing,
)
from app.interview_map import Coverage, CoverageMatch, ExperienceState, InterviewMap, InterviewTheme, MapState
from app.pressure_test import PressureItem, PressureQuestion, PressureTest, QuestionKind, Readiness
from app.role_models import CompetencyCategory
from app.story_models import StoryCompleteness

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
ROLE = uuid4()
STORY = uuid4()


def theme(name, coverage, category=CompetencyCategory.TECHNICAL, matches=()):
    return InterviewTheme(
        key=name.lower().replace(" ", "-"), name=name, category=category, from_job_description=True,
        coverage=coverage, matches=list(matches),
    )


def make_map(state=MapState.READY, themes=None) -> InterviewMap:
    themes = themes if themes is not None else [
        theme("SQL", Coverage.PREPARED, matches=[CoverageMatch(kind="STORY", label="Churn dashboard", text="x", story_id=STORY)]),
        theme("Stakeholder management", Coverage.MISSING, CompetencyCategory.BEHAVIOURAL),
        theme("Python", Coverage.EXPERIENCE, matches=[CoverageMatch(kind="WORK", label="Intern", text="Built Python jobs")]),
        theme("Tableau", Coverage.MENTIONED, CompetencyCategory.TOOL),
    ]
    return InterviewMap(
        role_profile_id=ROLE, target_role="Data Analyst", state=state,
        experience_state=ExperienceState.READY, themes=themes if state == MapState.READY else [],
    )


def record(when=NOW + timedelta(days=5)) -> InterviewEventRecord:
    return InterviewEventRecord(
        id=uuid4(), user_id=uuid4(), role_profile_id=ROLE, scheduled_for=when, round_kind="TECHNICAL",
        created_at=NOW, updated_at=NOW,
    )


def item(readiness):
    q = PressureQuestion(kind=QuestionKind.OUTCOME, text="What changed because of this work?", why="w", story_part="outcome")
    return PressureItem(claim_id=uuid4(), statement=f"did {readiness}", where="r", questions=[q], readiness=readiness)


def test_timing_boundaries() -> None:
    assert timing(NOW - timedelta(seconds=1), NOW) == Timing.PAST
    assert timing(NOW, NOW) == Timing.SOON
    assert timing(NOW + timedelta(hours=48), NOW) == Timing.SOON
    assert timing(NOW + timedelta(hours=48, seconds=1), NOW) == Timing.UPCOMING


def test_brief_picks_top_three_themes_with_support_and_limitations() -> None:
    brief = build_brief(record(), make_map(), None, None, now=NOW)
    assert [t.label for t in brief.themes] == ["SQL", "Stakeholder management", "Python"]
    sql, stakeholder, python = brief.themes
    assert sql.support == "Churn dashboard" and sql.story_id == STORY
    assert stakeholder.support is None and stakeholder.story_id is None
    assert python.support == "Built Python jobs"
    assert all(t.prompt for t in brief.themes)
    assert LIMITATION_SOURCES in brief.limitations
    assert brief.focus is None and brief.event.timing == Timing.UPCOMING


def test_recheck_orders_needs_preparation_then_unmarked() -> None:
    items = [item(None), item(Readiness.CAN_EXPLAIN), item(Readiness.NEEDS_PREPARATION), item(None), item(None)]
    pressure = PressureTest(role_profile_id=ROLE, target_role="Data Analyst", state="READY", items=items)
    recheck = build_brief(record(), make_map(), pressure, None, now=NOW).recheck
    assert [c.claim_id for c in recheck] == [items[2].claim_id, items[0].claim_id, items[3].claim_id]


@pytest.mark.parametrize("state", [MapState.ROLE_PREPARING, MapState.ROLE_UNREADABLE])
def test_role_not_ready_gives_empty_lists_but_keeps_limitations(state) -> None:
    pressure = PressureTest(role_profile_id=ROLE, target_role="x", state="READY", items=[item(None)])
    brief = build_brief(record(), make_map(state), pressure, None, now=NOW)
    assert brief.themes == [] and brief.recheck == []
    assert LIMITATION_SOURCES in brief.limitations
    assert 3 <= len(brief.questions_to_ask) <= 5


def test_questions_to_ask_are_three_to_five_and_fixed() -> None:
    for themes in ([], [theme("SQL", Coverage.MISSING)], make_map().themes,
                   [theme(n, Coverage.MISSING, c) for n, c in zip(("Qzx1", "Qzx2", "Qzx3", "Qzx4", "Qzx5", "Qzx6"), CompetencyCategory)]):
        asked = questions_to_ask(make_map(themes=themes))
        assert 3 <= len(asked) <= 5 and len(set(asked)) == len(asked)
        assert not any(t.name in q for t in themes for q in asked)  # never interpolates role or company text


def test_focus_comes_from_the_latest_review_for_this_role() -> None:
    review = LatestReview(
        session_id=uuid4(), target_role="Data Analyst", role_profile_id=ROLE, completed_at=NOW, counts=None,
        dimensions=[], improvements=[], next_step=ReviewNextStep(title="Say what you owned", body="Use I."),
    )
    assert build_brief(record(), make_map(), None, review, now=NOW).focus.title == "Say what you owned"
    other = review.model_copy(update={"role_profile_id": uuid4()})
    assert build_brief(record(), make_map(), None, other, now=NOW).focus is None


def test_follow_up_actions() -> None:
    questions = ["How do you handle stakeholder management?", "Tell me about SQL joins", "Python generators?",
                 "Tableau dashboards?", "Where do you see yourself?"]
    result = follow_ups(questions, make_map(), {STORY: StoryCompleteness.DEVELOPING})
    assert [f.action for f in result] == [
        FollowUpAction.ADD_STORY, FollowUpAction.STRENGTHEN_STORY, FollowUpAction.NONE,
        FollowUpAction.ADD_STORY, FollowUpAction.NONE,
    ]
    assert result[0].action_href .startswith("/stories/new?guided=1&role=")
    assert "theme=Stakeholder+management" in result[0].action_href
    assert result[1].action_href == f"/stories/{STORY}"
    assert result[4].theme_key is None and result[4].coverage is None
    assert [f.question for f in result] == questions  # verbatim
    ready = follow_ups(["SQL?"], make_map(), {STORY: StoryCompleteness.READY})
    assert ready[0].action == FollowUpAction.NONE
    assert best_theme("anything", []) is None


def test_debrief_questions_are_cleaned_and_bounded() -> None:
    write = InterviewDebriefWrite(questions_asked=["  Why SQL? ", "", "why sql?", "Tell me about you"])
    assert write.questions_asked == ["Why SQL?", "Tell me about you"]
    with pytest.raises(ValidationError):
        InterviewDebriefWrite(questions_asked=[f"q{i}" for i in range(16)])
    with pytest.raises(ValidationError):
        InterviewDebriefWrite(questions_asked=["x" * 501])
    assert len(InterviewDebriefWrite(questions_asked=["same"] * 30).questions_asked) == 1


def test_event_needs_a_timezone_and_cleans_label() -> None:
    with pytest.raises(ValidationError):
        InterviewEventCreate(scheduled_for=datetime(2026, 10, 1, 9))
    event = InterviewEventCreate(scheduled_for=datetime(2026, 10, 1, 9, tzinfo=timezone(timedelta(hours=5, minutes=30))), company_label="  ")
    assert event.company_label is None and event.round_kind == "OTHER"


def test_every_fixed_string_passes_copy_guard() -> None:
    pressure = PressureTest(role_profile_id=ROLE, target_role="x", state="READY", items=[item(None)])
    for state in MapState:
        brief = build_brief(record(), make_map(state), pressure, None, now=NOW)
        assert all_clean([*brief.limitations, *brief.questions_to_ask, *(t.prompt for t in brief.themes)])
    from app import interview_brief
    assert all_clean([*interview_brief._ASK_BY_CATEGORY.values(), *interview_brief._ASK_GENERAL])
