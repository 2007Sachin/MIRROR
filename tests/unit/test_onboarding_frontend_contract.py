from pathlib import Path


ROOT = Path(__file__).parents[2] / "apps" / "web" / "src"


def test_completed_onboarding_redirects_away_from_onboarding() -> None:
    page = (ROOT / "app" / "onboarding" / "page.tsx").read_text(encoding="utf-8")
    assert "onboarding.onboarding_completed" in page
    assert 'redirect("/app")' in page


def test_incomplete_onboarding_redirects_away_from_app() -> None:
    page = (ROOT / "app" / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "!onboarding.onboarding_completed" in page
    assert 'redirect("/onboarding")' in page

