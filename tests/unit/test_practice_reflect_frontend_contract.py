"""Practice, the pre-practice check, the reflection after a practice, and Reflect (W7)."""

import re
from pathlib import Path

WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
read = lambda *parts: WEB.joinpath(*parts).read_text(encoding="utf-8")  # noqa: E731

HOME = read("components", "practice", "practice-page.tsx")
START = read("components", "practice", "start-practice.tsx")
DISCARD = read("components", "practice", "discard-practice.tsx")
API_PRACTICE = read("lib", "api-practice.ts")
VIEW = read("lib", "practice-view.ts")
REVIEW = read("components", "review", "review-page.tsx")
COPY = read("lib", "copy-practice.ts")
REFLECT_PAGE = read("app", "reflect", "page.tsx")
REFLECT = read("app", "reflect", "reflect-view.tsx")
PROGRESS_PAGE = read("app", "progress", "page.tsx")
CSS = read("styles", "practice-reflect.css")


def test_every_practice_class_is_styled_without_blue() -> None:
    for source in (HOME, START, DISCARD, REVIEW, REFLECT):
        for name in set(re.findall(r"\bpr-[a-z-]+", source)):
            assert f".{name}" in CSS, name
    assert not re.search(r"blue|#[0-9a-f]{3,6}\b", CSS, re.IGNORECASE)
    assert "min-height: 44px" in CSS
    assert "prefers-reduced-motion" in CSS


def test_practice_home_has_one_way_in_and_never_creates_a_practice() -> None:
    assert HOME.count('className="dh-primary-action"') == 1
    assert "startPracticeHref" in HOME
    for creator in ("createPractice", "createSession", "mirrorApi.start"):
        assert creator not in HOME


def test_formats_are_explained_by_outcome_and_time() -> None:
    for title in ("5-minute drill", "Focused practice", "Full interview"):
        assert f'title: "{title}"' in COPY
    assert COPY.count("length:") >= 3


def test_drafts_continue_or_are_discarded_after_asking() -> None:
    assert "h.continue" in HOME and "<DiscardPractice" in HOME
    assert 'action: "Discard this practice"' in COPY
    assert "setConfirming(true)" in DISCARD and "abandonPractice(sessionId)" in DISCARD
    assert "/abandon" in API_PRACTICE and '"POST"' in API_PRACTICE


def test_history_lists_only_completed_practice() -> None:
    assert "sessions.filter(isCompleted)" in VIEW
    assert "previousTitle" in HOME


def test_start_practice_is_the_only_place_a_practice_is_created() -> None:
    assert "createPractice(" in START
    for label in ("preCheck.role", "preCheck.focus", "preCheck.format", "preCheck.length"):
        assert label in START
    assert "data?.active?.role" in START  # the active role is the default


def test_review_reflects_and_offers_four_ways_on_without_a_readiness_number() -> None:
    order = [REVIEW.index(key) for key in ("r.landedTitle", "r.strengthenTitle", "r.nextTitle", "r.repeatTitle")]
    assert order == sorted(order)
    for text in ('"What landed well"', '"One thing to strengthen"', '"Try this next"'):
        assert text in COPY
    for key in ("sameAnswer", "editStory", "anotherTheme", "finish"):
        assert f"r.repeat.{key}" in REVIEW
    assert 'href="/dashboard"' in REVIEW
    assert not re.search(r"readiness|percent|%\}", REVIEW, re.IGNORECASE)


def test_reflect_is_gated_puts_the_active_role_first_and_owns_progress() -> None:
    for guard in ("getServerOnboarding", 'redirect("/login?reason=session_expired")', 'redirect("/onboarding")'):
        assert guard in REFLECT_PAGE
    assert "<ReflectView" in REFLECT_PAGE
    assert "getActiveRole" in REFLECT and "RoleTileCard" in REFLECT
    assert REFLECT.index('id="reflect-recent"') < REFLECT.index('id="reflect-developing"')
    assert 'redirect("/reflect")' in PROGRESS_PAGE
    assert (WEB / "app" / "progress" / "[roleProfileId]" / "page.tsx").exists()
