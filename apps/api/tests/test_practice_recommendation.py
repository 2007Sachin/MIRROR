"""What to practise next: deterministic, one recommendation, or honestly none.

No dedicated test existed for `recommend_practice()` before the Interview Map started
surfacing it directly (previously only Home and the Practice page did). This file locks
in the three-step order so the Map's new "Recommended for you" banner can rely on it.
"""

from datetime import UTC, datetime
from uuid import uuid4

from app.dashboard_summary import LatestReview, ReviewCounts, ReviewNextStep
from app.interview_map import (
    AreaAction,
    Coverage,
    ExperienceState,
    InterviewMap,
    InterviewTheme,
    MapState,
    PreparationArea,
)
from app.practice_recommendation import RecommendationSource, recommend_practice
from app.role_models import CompetencyCategory

ROLE = uuid4()


def theme(key, name, coverage):
    return InterviewTheme(key=key, name=name, category=CompetencyCategory.ANALYTICAL, from_job_description=True, coverage=coverage)


def area(key, action, theme_key=None, focus=None, body="Worth preparing."):
    return PreparationArea(key=key, title=key, body=body, action=action, theme_key=theme_key, focus=focus)


def interview_map(*, areas=(), themes=(), state=MapState.READY):
    return InterviewMap(
        role_profile_id=ROLE, target_role="Product Manager", state=state, experience_state=ExperienceState.READY,
        themes=list(themes), preparation_areas=list(areas),
    )


def review(root_cause):
    return LatestReview(
        session_id=uuid4(), target_role="Product Manager", role_profile_id=ROLE, completed_at=datetime.now(UTC),
        counts=ReviewCounts(clear=1, could_be_stronger=1, worth_revisiting=0),
        dimensions=[], improvements=[], next_step=ReviewNextStep(title="t", body="b"), root_cause=root_cause,
    )


def test_a_role_preparing_or_unreadable_map_recommends_nothing() -> None:
    for state in (MapState.ROLE_PREPARING, MapState.ROLE_UNREADABLE):
        assert recommend_practice(interview_map(state=state), None) is None


def test_a_role_area_with_a_focus_wins_over_everything_else() -> None:
    """Step 1: a preparation area that already names a practice focus (the impact area)."""
    map_ = interview_map(areas=[area("impact", AreaAction.PRACTICE, focus="impact", body="Add what changed.")])
    result = recommend_practice(map_, review("ROLE_SKILL_GAP"))
    assert result is not None
    assert (result.focus, result.source, result.reason) == ("impact", RecommendationSource.ROLE_AREA, "Add what changed.")
    assert result.role_profile_id == ROLE and result.theme is None and result.mode == "QUICK_DRILL"


def test_a_pressure_test_area_with_a_focus_also_counts_as_step_one() -> None:
    map_ = interview_map(areas=[area("dig", AreaAction.PRESSURE_TEST, focus="story")])
    result = recommend_practice(map_, None)
    assert result is not None and result.source == RecommendationSource.ROLE_AREA and result.focus == "story"


def test_an_area_action_without_a_focus_is_not_step_one() -> None:
    """FIND_STORY/ADD_EXPERIENCE areas never carry a focus and must fall through."""
    map_ = interview_map(areas=[area("find", AreaAction.FIND_STORY, theme_key="ownership")])
    assert recommend_practice(map_, None) is None  # nothing else to fall back to either


def test_the_latest_reviews_growth_area_is_step_two() -> None:
    map_ = interview_map(areas=[area("find", AreaAction.FIND_STORY)])  # no focus: step 1 skips it
    result = recommend_practice(map_, review("TECHNICAL_DEPTH"))
    assert result is not None
    assert result.focus == "decisions" and result.source == RecommendationSource.REVIEW
    assert result.reason == "Explain how it works, including one choice you made and why."


def test_an_unrecognised_root_cause_falls_through_step_two() -> None:
    map_ = interview_map(areas=[area("find", AreaAction.FIND_STORY, theme_key="t1")], themes=[theme("t1", "Ownership", Coverage.MISSING)])
    result = recommend_practice(map_, review("SOMETHING_UNMAPPED"))
    assert result is not None and result.source == RecommendationSource.MAP_GAP  # step 3, not step 2


def test_a_missing_or_mentioned_theme_is_step_three() -> None:
    map_ = interview_map(
        areas=[area("find", AreaAction.FIND_STORY, theme_key="ownership", body="Add an example of ownership.")],
        themes=[theme("ownership", "Ownership", Coverage.MISSING)],
    )
    result = recommend_practice(map_, None)
    assert result is not None
    assert (result.focus, result.theme, result.source) == ("role", "Ownership", RecommendationSource.MAP_GAP)
    assert result.reason == "Add an example of ownership."


def test_a_mentioned_theme_also_qualifies_for_step_three() -> None:
    map_ = interview_map(
        areas=[area("find", AreaAction.FIND_STORY, theme_key="t1")],
        themes=[theme("t1", "Data analysis", Coverage.MENTIONED)],
    )
    result = recommend_practice(map_, None)
    assert result is not None and result.theme == "Data analysis"


def test_a_prepared_or_experience_theme_is_never_recommended_as_a_gap() -> None:
    map_ = interview_map(
        areas=[area("find", AreaAction.FIND_STORY, theme_key="t1")],
        themes=[theme("t1", "Ownership", Coverage.PREPARED)],
    )
    assert recommend_practice(map_, None) is None


def test_nothing_to_go_on_means_no_recommendation_never_a_guess() -> None:
    assert recommend_practice(interview_map(), None) is None
