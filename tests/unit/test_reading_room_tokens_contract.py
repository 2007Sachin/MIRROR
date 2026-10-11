"""Reading Room design tokens exist, are named by role, and keep WCAG AA contrast."""

import re
from pathlib import Path


CSS = (Path(__file__).parents[2] / "apps" / "web" / "src" / "app" / "globals.css").read_text(encoding="utf-8")
WEB = Path(__file__).parents[2] / "apps" / "web" / "src"
CRITICAL_PATH = (Path(__file__).parents[2] / "scripts" / "qa" / "browser" / "tests" / "critical-path.mjs").read_text(encoding="utf-8")
ROOT_BLOCK = re.search(r":root\s*\{(.*?)\n\}", CSS, re.S).group(1)
TOKENS = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", ROOT_BLOCK))

READING_ROOM = [
    "--canvas", "--canvas-sunken", "--surface", "--surface-fallback",
    "--fg-primary", "--fg-secondary", "--fg-muted", "--border-control",
    "--accent-50", "--accent-100", "--accent-500", "--accent-600", "--accent-700",
    "--provenance-50", "--provenance-600", "--focus-ring",
    "--success-soft", "--warning", "--warning-ink", "--warning-soft", "--info", "--info-soft",
    "--radius-control", "--radius-panel", "--radius-glass", "--radius-pill",
    "--elevation-1", "--elevation-2", "--elevation-3",
    "--glass-bg", "--glass-blur", "--glass-edge",
]


def rgb(token: str) -> tuple[float, ...]:
    value = TOKENS[token].strip()
    while value.startswith("var("):
        value = TOKENS[value[4:-1]].strip()
    if value.startswith("#"):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(float(part) for part in re.findall(r"[\d.]+", value))


def over(top: str, bottom: str) -> tuple[float, ...]:
    *colour, alpha = rgb(top)
    return tuple(c * alpha + b * (1 - alpha) for c, b in zip(colour, rgb(bottom)))


def contrast(a, b) -> float:
    def luminance(channels):
        lin = [(c / 255) / 12.92 if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in channels[:3]]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_reading_room_tokens_are_defined_by_role_not_hue() -> None:
    assert [name for name in READING_ROOM if name not in TOKENS] == []
    # The onboarding contract bans hue words in feature CSS; token names must never force one in.
    assert not [name for name in TOKENS if re.search(r"teal|plum|blue|indigo|cobalt|purple|green", name)]


def test_reading_room_text_pairs_meet_aa() -> None:
    white = (255, 255, 255)
    pairs = [
        (rgb("--fg-primary"), rgb("--surface")), (rgb("--fg-primary"), rgb("--canvas")),
        (rgb("--fg-secondary"), rgb("--canvas-sunken")), (rgb("--fg-muted"), rgb("--canvas-sunken")),
        (white, rgb("--accent-600")), (rgb("--accent-700"), rgb("--canvas")), (rgb("--accent-700"), rgb("--accent-50")),
        (rgb("--provenance-600"), rgb("--provenance-50")), (rgb("--warning-ink"), rgb("--warning-soft")),
        (rgb("--info"), rgb("--info-soft")), (rgb("--success"), rgb("--success-soft")),
        # Glass text, checked over the darkest likely underlay (graphite text scrolling beneath it).
        (rgb("--fg-secondary"), over("--glass-bg", "--fg-primary")),
    ]
    assert [round(contrast(a, b), 2) for a, b in pairs if contrast(a, b) < 4.5] == []


def test_reading_room_controls_and_focus_meet_non_text_contrast() -> None:
    for token in ("--border-control", "--focus-ring", "--accent-500"):
        assert contrast(rgb(token), rgb("--canvas")) >= 3, token


def test_glass_falls_back_to_a_solid_surface() -> None:
    assert re.search(r"@supports not \(\(backdrop-filter: blur\(1px\)\) or \(-webkit-backdrop-filter: blur\(1px\)\)\)\s*\{\s*:root \{ --glass-bg: var\(--surface-fallback\); \}", CSS)
    assert re.search(r"@media \(prefers-reduced-transparency: reduce\)\s*\{\s*:root \{ --glass-bg: var\(--surface-fallback\); --glass-blur: none; \}", CSS)


MIGRATED = {
    # P3A: Help, Settings, Roles, Stories
    "components/help/help-page.tsx", "components/workspace/account-settings.tsx",
    "components/roles/roles-page.tsx", "components/roles/role-detail.tsx", "components/roles/pressure-test-page.tsx",
    "components/interviews/interviews-page.tsx", "components/interviews/interview-brief-page.tsx",
    "components/onboarding/new-role-flow.tsx", "components/stories/stories-page.tsx", "components/stories/story-editor.tsx",
    # P3B: Plan, Progress, Reflect, Practice
    "components/plan/plan-page.tsx", "components/plan/round-page.tsx",
    "components/progress/progress-hub.tsx", "components/progress/role-progress.tsx", "components/progress/dimension-detail.tsx",
    "components/progress/dimension-answers.tsx", "components/progress/answer-detail.tsx",
    "app/reflect/reflect-view.tsx", "components/practice/practice-page.tsx", "components/practice/start-practice.tsx",
    # P3C: Landing, Login/Signup, Onboarding
    "components/landing-story.tsx", "components/auth-form.tsx", "components/onboarding-flow.tsx", "app/onboarding/page.tsx",
}


def test_reading_room_scope_maps_legacy_tokens_to_role_tokens() -> None:
    scope = re.search(r"\.reading-room \{(.*?)\}", CSS, re.S).group(1)
    for legacy, role in (("--paper", "--canvas"), ("--ink", "--fg-primary"), ("--action", "--accent-600"), ("--pulse", "--accent-600")):
        assert f"{legacy}: var({role});" in scope
    assert not re.search(r"#[0-9a-f]{3,6}\b|rgba?\(", scope)  # tokens only, no raw colours


def test_migrated_screens_opt_into_the_reading_room() -> None:
    missing = [f for f in sorted(MIGRATED) if "readingRoom" not in (WEB / f).read_text(encoding="utf-8") and "reading-room" not in (WEB / f).read_text(encoding="utf-8")]
    assert missing == []


def test_isolated_browser_journey_covers_landing_content_and_layout() -> None:
    for expected in (
        'await step("landing"',
        'heading("Find the words for your experience.", 1)',
        'getByRole("link", { name: "See a sample reflection" }).click()',
        'getByRole("table", { name: "Mirror compared with a generic mock interview" })',
        'getByRole("columnheader").count()',
        'overflow("landing", true)',
    ):
        assert expected in CRITICAL_PATH
