"""Interview Map -> Practice: exact role identity survives every link, and the map's own
deterministic recommendation and story matches are used, never re-derived or invented."""

from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

MAP_VIEW = read("lib", "map-view.ts")
PRACTICE_VIEW = read("lib", "practice-view.ts")
STORY_VIEW = read("lib", "story-view.ts")
API = read("lib", "api.ts")
ROLE_DETAIL = read("components", "roles", "role-detail.tsx")
MAP_COMPONENT = read("components", "roles", "interview-map-view.tsx")
COPY = read("lib", "copy.ts")
INTERVIEW_MAP_COPY = COPY[COPY.index("export const interviewMap = {"):COPY.index("export const roleWorkspace")]


def test_the_maps_practice_action_carries_its_exact_role() -> None:
    # This was the defect: PRACTICE dropped role_profile_id and start-practice then fell
    # back to the account's current role, which can silently be a different role.
    area_href = MAP_VIEW[MAP_VIEW.index("export function areaHref"):MAP_VIEW.index("export function areaActionLabel")]
    assert "startPracticeHref(map.target_role, area.focus, map.role_profile_id)" in area_href


def test_the_pages_own_start_practice_button_carries_its_exact_role() -> None:
    assert 'startPracticeHref(role, undefined, roleProfileId)' in ROLE_DETAIL


def test_the_header_button_steps_back_when_the_banner_already_offers_practice() -> None:
    # Two buttons both saying "start a practice" at once reads as redundant, not as one
    # clear next action - the header defers to the recommendation banner when there is one.
    action = ROLE_DETAIL[ROLE_DETAIL.index("action={"):ROLE_DETAIL.index("<RoleTabs")]
    assert 'data?.recommendation ? "dh-text-action" : "dh-primary-action"' in action


def test_find_story_and_pressure_test_already_carried_the_role_and_still_do() -> None:
    assert "findStoryHref(map.role_profile_id" in MAP_VIEW
    assert "pressureTestHref(map.role_profile_id)" in MAP_VIEW


def test_the_recommendation_reuses_the_backend_that_home_and_practice_already_trust() -> None:
    # No new recommendation logic here: the same endpoint, read the same way.
    assert "mirrorApi.practiceRecommendation(roleProfileId)" in ROLE_DETAIL
    assert ".then((value) => value.recommendation)" in ROLE_DETAIL
    assert ".catch(() => null)" in ROLE_DETAIL  # never blocks the page


def test_the_recommendation_href_keeps_role_mode_focus_and_theme_together() -> None:
    fn = MAP_VIEW[MAP_VIEW.index("export function recommendationHref"):MAP_VIEW.index("export function recommendationTitle")]
    assert "recommendation.role_profile_id" in fn
    assert "recommendation.mode" in fn and "recommendation.focus" in fn and "recommendation.theme" in fn
    assert "startPracticeHref(" in fn  # the one existing entry point, not a new one


def test_the_map_shows_at_most_one_recommendation_banner_and_it_is_optional() -> None:
    assert "recommendation?: PracticeRecommendation | null" in MAP_COMPONENT
    assert "{recommendation ? (" in MAP_COMPONENT
    assert MAP_COMPONENT.count('aria-labelledby="map-next-title"') == 1


def test_a_prepared_theme_with_a_story_can_be_practised_directly() -> None:
    fn = MAP_VIEW[MAP_VIEW.index("export function storyToPractise"):MAP_VIEW.index("export function recommendationHref")]
    assert 'first.kind === "STORY"' in fn and "first.story_id" in fn
    assert "practiseStoryHref(storyId)" in MAP_COMPONENT
    # A non-story match (work/project/skill/tool) never gets this action.
    assert "storyToPractise(theme)" in MAP_COMPONENT


def test_coverage_matches_carry_the_exact_story_id_not_a_name_lookup() -> None:
    themes_type = API[API.index("themes: Array<{"):API.index("preparation_areas: Array<{")]
    assert "story_id: string | null" in themes_type


def test_dig_deeper_and_practice_are_distinguished_in_copy() -> None:
    # The one place both sit next to each other: the bottom "Dig deeper" banner.
    assert "practise saying it" in INTERVIEW_MAP_COPY.lower() or "practice saying it" in INTERVIEW_MAP_COPY.lower()


def test_map_copy_never_leaks_internal_vocabulary() -> None:
    for internal in ("readiness", "confidence", "diagnostic", "verification", "coverage score", "assessment", "claim"):
        assert internal not in INTERVIEW_MAP_COPY.lower()


def test_practice_mode_language_stays_concrete_about_depth_and_duration() -> None:
    modes = COPY[COPY.index("export const practiceModes"):COPY.index("export const practiceModes") + 900]
    for phrase in ("About 20 minutes", "about 9 minutes", "about 5 minutes"):
        assert phrase in modes
