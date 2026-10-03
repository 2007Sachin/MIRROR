"""Practice modes on screen: one recommendation, three plain choices, no engine vocabulary."""

import re
from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
API_APP = Path(__file__).parents[2] / "apps" / "api" / "app"
read = lambda path: path.read_text(encoding="utf-8")  # noqa: E731

PRACTICE = read(WEB / "components" / "practice" / "practice-page.tsx")
START = read(WEB / "components" / "practice" / "start-practice.tsx")
VIEW = read(WEB / "lib" / "practice-view.ts")
COPY = read(WEB / "lib" / "copy.ts")
MODES_PY = read(API_APP / "practice_modes.py")
BRIEF = read(WEB / "components" / "practice" / "practice-brief-note.tsx")
BRIEF_PAGE = read(WEB / "app" / "sessions" / "[id]" / "brief" / "page.tsx")


def test_practice_leads_with_one_recommendation_from_the_backend() -> None:
    assert "mirrorApi.practiceRecommendation" in PRACTICE
    assert "recommendedFallback" in PRACTICE  # says so when there is nothing to recommend
    assert "Choose something you'd like to practise." in COPY


def test_the_three_ways_to_practise_are_named_plainly() -> None:
    for title in ("Full interview", "Focused practice", "Quick drill"):
        assert f'title: "{title}"' in COPY
    assert not re.search(r"\b(session mode|practice mode)\b", COPY, re.IGNORECASE)


def test_focus_keys_on_screen_match_the_backend_areas() -> None:
    backend = set(re.findall(r'= "([a-z]+)"', MODES_PY.split("class PracticeFocus")[1].split("@dataclass")[0]))
    screen = set(re.findall(r'key: "([a-z]+)"', COPY.split("export const practiceFocus")[1].split("export const practiceModes")[0]))
    assert screen == backend - {"full"}


def test_a_short_practice_cannot_start_without_an_area() -> None:
    assert "choiceIsComplete" in START and "choiceIsComplete" in VIEW
    assert "!choiceIsComplete(choice)" in START


def test_the_pre_practice_brief_uses_the_actual_session_duration() -> None:
    assert "modeCopy(session.practice_mode).length" in BRIEF
    assert "Allow about 20 minutes" not in BRIEF_PAGE
