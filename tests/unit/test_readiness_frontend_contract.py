"""The readiness surfaces render backend decisions and never compute their own."""

import re
from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

MAP_VIEW = read("lib", "map-view.ts")
ROLE_VIEW = read("lib", "role-view.ts")
STORY_VIEW = read("lib", "story-view.ts")
ROLE_DETAIL = read("components", "roles", "role-detail.tsx")
PRESSURE = read("components", "roles", "pressure-test-page.tsx")
EDITOR = read("components", "stories", "story-editor.tsx")
SHELL = read("components", "workspace", "app-shell.tsx")
PROXY = read("proxy.ts")
COPY = read("lib", "copy.ts")


def test_the_role_workspace_reads_the_backend_interview_map() -> None:
    assert "mirrorApi.interviewMap" in ROLE_DETAIL
    # The earlier client-side word matching was removed in favour of the backend map.
    assert "roleConnections" not in ROLE_VIEW


def test_map_actions_all_lead_somewhere_real() -> None:
    for action in ("FIND_STORY", "PRESSURE_TEST", "PRACTICE", "ADD_EXPERIENCE"):
        assert f"{action}:" in MAP_VIEW


def test_the_pressure_test_saves_only_the_candidates_own_answers() -> None:
    assert "mirrorApi.answerChecks" in PRESSURE
    assert "storyFromAnswers" in PRESSURE
    assert "source_text: statement" in STORY_VIEW  # the resume statement is kept as a source, not an answer


def test_story_deletion_asks_first() -> None:
    assert "showModal" in EDITOR and "deleteTitle" in EDITOR


def test_my_stories_is_navigable_and_guarded() -> None:
    assert '"/stories"' in SHELL
    assert '"/stories/:path*"' in PROXY


def test_candidate_copy_frames_the_pressure_test_as_explaining_not_proving() -> None:
    assert "digs deeper" in COPY
    assert not re.search(r"prove", COPY, re.IGNORECASE)
