"""My plan: server-gated page, one filled action, plain statuses, the right links, warm tokens only."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[2] / "apps" / "web" / "src"
PAGE = (ROOT / "app" / "plan" / "page.tsx").read_text(encoding="utf-8")
ROLE_PAGE = (ROOT / "app" / "roles" / "[role_profile_id]" / "page.tsx").read_text(encoding="utf-8")
PLAN = (ROOT / "components" / "plan" / "plan-page.tsx").read_text(encoding="utf-8")
CARD = (ROOT / "components" / "plan" / "plan-area-card.tsx").read_text(encoding="utf-8")
COPY = (ROOT / "lib" / "copy-plan.ts").read_text(encoding="utf-8")
API = (ROOT / "lib" / "api-plan.ts").read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "plan.css").read_text(encoding="utf-8")
EXPERIENCE = (ROOT / "components" / "experience" / "experience-page.tsx").read_text(encoding="utf-8")
REVIEWED = (ROOT / "components" / "experience" / "reviewed-examples.tsx").read_text(encoding="utf-8")


def test_page_is_server_gated_like_progress() -> None:
    assert "getServerOnboarding" in PAGE
    assert 'redirect("/login?reason=session_expired")' in PAGE
    assert 'redirect("/onboarding")' in PAGE
    assert "WorkspaceUnavailable" in PAGE
    assert 'export const dynamic = "force-dynamic"' in PAGE


def test_role_page_redirects_to_plan() -> None:
    assert "redirect(`/plan?role=${encodeURIComponent(role_profile_id)}`)" in ROLE_PAGE
    assert (ROOT / "app" / "roles" / "[role_profile_id]" / "pressure-test" / "page.tsx").exists()


def test_api_paths() -> None:
    assert "/api/v1/plan${query}" in API
    assert "role_profile_id=" in API
    assert "/areas/${encodeURIComponent(areaKey)}/link" in API
    assert 'method: "PUT"' in API


def test_only_the_recommended_need_gets_the_filled_action() -> None:
    assert 'recommended ? "dh-primary-action" : "dh-primary-action is-quiet"' in CARD
    assert "dh-text-action" in CARD


def test_actions_link_to_practice_story_and_experience() -> None:
    assert "startPracticeHref(role.target_role" in PLAN and "theme: area.theme" in PLAN and "role.role_profile_id" in PLAN
    assert "&evidence=${encodeURIComponent(item)}" in PLAN
    assert 'ADD_EXAMPLE: "/experience"' in PLAN
    assert 'href="/experience#review"' in PLAN
    for label in ("Practice this explanation", "Turn it into a story", "Add another example"):
        assert label in COPY


def test_statuses_are_plain_words() -> None:
    assert 'STRONG: "Strong example"' in COPY
    assert "Good example" in COPY and "explanation to practice" in COPY
    assert 'BUILD: "Build an example"' in COPY
    for banned in ("Intermediate", "Beginner", "Advanced", "%"):
        assert banned not in COPY
    for reason in ("TOOL", "OUTCOME", "DECISION", "CAPABILITY", "CONFIRMED"):
        assert re.search(rf"{reason}: \"", COPY)


def test_experience_has_reviewed_examples_section() -> None:
    assert "<ReviewedExamples />" in EXPERIENCE
    assert 'id="review"' in REVIEWED
    assert "ReviewItem" in REVIEWED
    assert "@/lib/api-evidence" in REVIEWED


def test_css_uses_tokens_only_and_no_blue() -> None:
    assert '"@/styles/plan.css"' in PLAN
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb|hsl", CSS)
    assert "blue" not in CSS.lower()
    allowed = {"action", "action-soft", "ink", "slate", "line", "paper-raised", "success", "caution"}
    colors = set(re.findall(r"var\(--([a-z-]+)\)", CSS)) - {name for name in re.findall(r"var\(--([a-z-]+)", CSS) if name.startswith(("space", "text"))}
    assert colors <= allowed, colors


def test_every_imported_css_file_exists() -> None:
    for source in (PLAN, CARD, REVIEWED):
        for path in re.findall(r'import "@/(styles/[^"]+\.css)"', source):
            assert (ROOT / path).exists(), path
