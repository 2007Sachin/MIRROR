"""Onboarding ends on a role plan, never on a practice it created by itself."""

import re
from pathlib import Path


ROOT = Path(__file__).parents[2] / "apps" / "web" / "src"
FLOW = (ROOT / "components" / "onboarding-flow.tsx").read_text(encoding="utf-8")
STEPS = ROOT / "components" / "onboarding"
REVIEW = (STEPS / "review-step.tsx").read_text(encoding="utf-8")
PLAN = (STEPS / "plan-ready-step.tsx").read_text(encoding="utf-8")
EXPERIENCE = (STEPS / "experience-step.tsx").read_text(encoding="utf-8")
ROLE = (STEPS / "role-step.tsx").read_text(encoding="utf-8")
NEW_ROLE = (STEPS / "new-role-flow.tsx").read_text(encoding="utf-8")
NEW_ROLE_PAGE = ROOT / "app" / "roles" / "new" / "page.tsx"
COPY = (ROOT / "lib" / "copy-onboarding.ts").read_text(encoding="utf-8")
API = (ROOT / "lib" / "api-evidence.ts").read_text(encoding="utf-8")
CSS = (ROOT / "styles" / "onboarding-plan.css").read_text(encoding="utf-8")
ALL = "\n".join([FLOW, REVIEW, PLAN, EXPERIENCE, ROLE, NEW_ROLE])


def test_onboarding_never_creates_a_practice_session() -> None:
    assert "createSession" not in ALL
    assert "createPractice" not in ALL
    assert "mirrorApi.prepare" not in ALL
    assert "onboarding_session_id" not in ALL


def test_steps_run_role_experience_review_then_plan() -> None:
    for step in ("RoleStep", "ExperienceStep", "ReviewStep", "PlanReadyStep"):
        assert step in FLOW
    assert "Here is what I found. Is this right?" in COPY
    assert "What role are you preparing for?" in COPY
    assert "Bring in the work you want to talk about." in COPY
    assert "preparation plan is ready." in COPY


def test_review_step_edits_removes_and_approves_found_items() -> None:
    assert "approveEvidence" in REVIEW
    assert "updateEvidence" in REVIEW
    for state in ("READING", "UNREADABLE", "NO_RESUME"):
        assert state in REVIEW
    assert "Use this in my plan" in COPY
    assert '"/api/v1/career-evidence/approve"' in API
    item = (STEPS / "review-item.tsx").read_text(encoding="utf-8")
    for field in ("title", "detail", "outcome", "metric"):
        assert f'"{field}"' in item
    assert '"REMOVED"' in item and '"APPROVED"' in item


def test_existing_resume_is_reused_rather_than_uploaded_again() -> None:
    assert "Use my saved experience" in COPY
    assert "saved" in EXPERIENCE


def test_plan_ready_opens_the_plan_with_a_short_practice_as_a_text_link() -> None:
    # Loop 2 (UX proposal section 3): the promised plan is the one primary exit; practice is a text link.
    assert "See your plan" in COPY and "Start a short practice instead" in COPY
    assert "Explore my workspace" not in COPY
    exits = re.findall(r'className="([^"]*)"[^>]*onClick=\{\(\) => void leave\(([^)]*)\)', PLAN)
    assert [cls for cls, _ in exits] == ["button-primary op-target", "op-text op-target"]
    assert exits[0][1].startswith("planHref(roleProfileId")
    assert '"/dashboard"' not in PLAN
    assert "startPracticeHref" in PLAN and '"QUICK_DRILL"' in PLAN


def test_add_a_role_route_sets_the_active_role_without_a_session() -> None:
    assert NEW_ROLE_PAGE.exists()
    assert "NewRoleFlow" in NEW_ROLE_PAGE.read_text(encoding="utf-8")
    assert "RoleStep" in NEW_ROLE and "PlanReadyStep" in NEW_ROLE
    assert "setActiveRole" in NEW_ROLE
    assert '"/api/v1/active-role"' in (ROOT / "lib" / "api-active-role.ts").read_text(encoding="utf-8")
    assert "ExperienceStep" not in NEW_ROLE


def test_onboarding_styles_use_tokens_and_no_blue() -> None:
    assert "var(--action-soft" in CSS and "var(--ink" in CSS
    assert not re.search(r"blue|cobalt|indigo|teal|#(?:2563eb|3b82f6|1d4ed8|0ea5e9)", CSS, re.IGNORECASE)
