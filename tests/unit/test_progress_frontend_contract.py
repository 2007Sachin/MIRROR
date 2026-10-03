"""Role progress renders backend decisions: no client-side trends, scores or invented data."""

import re
from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: (WEB.joinpath(*parts)).read_text(encoding="utf-8")  # noqa: E731

VIEW = read("lib", "progress-view.ts")
API = read("lib", "api.ts")
COMPONENTS = {p.name: p.read_text(encoding="utf-8") for p in (WEB / "components" / "progress").glob("*.ts*")}
LIVE = {name: text for name, text in COMPONENTS.items() if "qa-preview" not in name}


def test_the_role_based_routes_exist_and_the_old_area_route_is_gone() -> None:
    app = WEB / "app" / "progress"
    assert (app / "[roleProfileId]" / "page.tsx").exists()
    assert (app / "[roleProfileId]" / "[dimension]" / "page.tsx").exists()
    assert (app / "[roleProfileId]" / "[dimension]" / "answers" / "page.tsx").exists()
    assert (app / "[roleProfileId]" / "answers" / "[sessionId]" / "[turnId]" / "page.tsx").exists()
    assert not (app / "[area]").exists()


def test_pages_read_the_role_progress_api_not_a_name_based_one() -> None:
    assert "/api/v1/progress/roles" in API
    assert "/api/v1/progress?" not in API and "request<ProgressResponse>" not in API
    assert "mirrorApi.progressHub" in COMPONENTS["progress-hub.tsx"]
    assert "mirrorApi.roleProgress" in COMPONENTS["use-role-progress.ts"]
    assert "mirrorApi.progressAnswer" in COMPONENTS["answer-detail.tsx"]


def test_the_frontend_never_computes_a_trend_or_a_number() -> None:
    forbidden = re.compile(r"Math\.(round|floor)\(.*(strong|seen)|\* *100|toFixed|percent", re.I)
    for name, text in {**LIVE, "progress-view.ts": VIEW}.items():
        assert not forbidden.search(text), name
    # Direction comes from the backend field, never from comparing states here.
    assert "cells[" not in VIEW and ".trend =" not in VIEW


def test_retry_uses_the_existing_try_again_flow() -> None:
    detail = COMPONENTS["answer-detail.tsx"]
    assert "TryAgain" in detail and 'from "@/components/review/try-again"' in detail
    assert "mirrorApi.tryAgain" not in detail  # no parallel retry implementation


def test_focused_practice_goes_through_the_existing_practice_start() -> None:
    assert "startPracticeHref" in VIEW and "FOCUSED_PRACTICE" in VIEW


def test_markers_are_buttons_with_a_text_label_and_not_colour_only() -> None:
    timeline = COMPONENTS["development-timeline.tsx"]
    assert "aria-label={markerLabel" in timeline and "aria-pressed" in timeline
    assert "<caption" in timeline and 'scope="row"' in timeline
    assert "strokeDasharray" in COMPONENTS["state-mark.tsx"]  # shape differs, not only colour


def test_the_qa_route_is_local_only() -> None:
    page = read("app", "progress-qa", "page.tsx")
    assert 'NODE_ENV === "production"' in page and "MIRROR_HOME_QA" in page and "notFound()" in page
    assert all("progress-qa" not in text for text in LIVE.values())


def test_home_links_into_the_role_it_is_about() -> None:
    home_view = read("lib", "home-view.ts")
    assert "roleProgressHref" in home_view and "dimensionAnswersHref" in home_view and "step.role_profile_id" in home_view
