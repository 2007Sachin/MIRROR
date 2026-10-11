"""Contract for the shared Reading Room page-layout primitives (redesign P4)."""

from pathlib import Path


ROOT = Path(__file__).parents[2]
WEB = ROOT / "apps" / "web" / "src"
PAGE_SHELL = (WEB / "components" / "workspace" / "page-shell.tsx").read_text(encoding="utf-8")
CSS = (WEB / "styles" / "dashboard.css").read_text(encoding="utf-8")


def test_page_shell_exposes_one_shared_layout_scope() -> None:
    assert '"dh dh-page-layout reading-room"' in PAGE_SHELL
    assert '"dh dh-page-layout"' in PAGE_SHELL
    assert PAGE_SHELL.count("dh-page-layout") == 2


def test_shared_layout_keeps_content_solid_and_glass_out() -> None:
    for selector in (
        ".dh-page-layout .dh-section",
        ".dh-page-layout .dh-empty",
        ".dh-page-layout .dh-alert",
    ):
        assert selector in CSS
    assert "background: var(--paper-raised)" in CSS
    shared = CSS[CSS.index(".dh-page-layout {") :]
    assert "backdrop-filter" not in shared
    assert "glass-bg" not in shared


def test_shared_layout_standardizes_accessible_controls() -> None:
    assert ":is(a, button, input, select, textarea, summary):focus-visible" in CSS
    assert "outline: 2px solid var(--focus-ring)" in CSS
    assert ".dh-page-layout .dh-form :is(input, select, textarea, .field)" in CSS
    assert "min-height: 2.75rem" in CSS
    assert ".dh-page-layout .dh-alert button" in CSS


def test_shared_layout_is_responsive_without_decorative_loading_motion() -> None:
    mobile = CSS[CSS.index("@media (max-width: 720px)") :]
    assert ".dh-page-layout .dh-section" in mobile
    assert ".dh-page-layout .dh-alert" in mobile
    assert "flex-direction: column" in mobile
    assert "shimmer" not in CSS.casefold()
