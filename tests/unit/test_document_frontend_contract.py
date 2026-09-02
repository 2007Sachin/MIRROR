from pathlib import Path


ROOT = Path(__file__).parents[2] / "apps" / "web" / "src"
SETUP = (ROOT / "components" / "setup-flow.tsx").read_text(encoding="utf-8")


def test_setup_page_has_required_resume_and_job_description_copy() -> None:
    assert (
        "Let&apos;s understand what an interviewer will see before meeting you."
        in SETUP
    )
    assert "Upload resume" in SETUP
    assert "Paste job description" in SETUP
    assert "I don&apos;t have one" in SETUP


def test_setup_reports_upload_progress_and_stores_document_ids() -> None:
    assert 'role="progressbar"' in SETUP
    assert "resumeDocumentId" in SETUP
    assert "jobDescriptionDocumentId" in SETUP
    assert "window.localStorage" in SETUP


def test_onboarding_completion_continues_to_setup() -> None:
    onboarding = (ROOT / "components" / "onboarding-flow.tsx").read_text(
        encoding="utf-8"
    )
    assert 'router.replace("/app/setup")' in onboarding

