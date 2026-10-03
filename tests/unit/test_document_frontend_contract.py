from pathlib import Path


ROOT = Path(__file__).parents[2] / "apps" / "web" / "src"
ONBOARDING = (ROOT / "components" / "onboarding-flow.tsx").read_text(
    encoding="utf-8"
)
ONBOARDING_STEPS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "components" / "onboarding").glob("*.tsx"))
)
ONBOARDING_COPY = (ROOT / "lib" / "copy-onboarding.ts").read_text(encoding="utf-8")
SETUP_PAGE = (ROOT / "app" / "app" / "setup" / "page.tsx").read_text(
    encoding="utf-8"
)
EXPERIENCE = (ROOT / "components" / "experience" / "experience-page.tsx").read_text(encoding="utf-8")
EXPERIENCE_VIEW = (ROOT / "lib" / "experience-view.ts").read_text(encoding="utf-8")
EVIDENCE_DRAWER = (ROOT / "components" / "workspace" / "evidence-drawer.tsx").read_text(encoding="utf-8")
EVIDENCE_DIALOGS = (ROOT / "components" / "workspace" / "evidence-dialogs.tsx").read_text(encoding="utf-8")
EVIDENCE_TYPES = (ROOT / "components" / "workspace" / "evidence-types.ts").read_text(encoding="utf-8")
COPY = (ROOT / "lib" / "copy.ts").read_text(encoding="utf-8")
API = (ROOT / "lib" / "api.ts").read_text(encoding="utf-8")


def test_onboarding_collects_role_context_and_starting_evidence() -> None:
    for label in ("Job description", "Upload it", "Paste it", "Skip for now", "Upload my resume", "Use my saved experience"):
        assert label in ONBOARDING_COPY
    assert "uploadRoleBriefDocument" in ONBOARDING_STEPS
    assert "uploadResumeDocument" in ONBOARDING_STEPS


def test_onboarding_reports_real_upload_progress_and_persists_ids() -> None:
    assert 'role="progressbar"' in ONBOARDING_STEPS
    assert "onboarding_resume_document_id" in ONBOARDING
    assert "onboarding_role_brief_document_id" in ONBOARDING
    assert "window.localStorage" not in ONBOARDING + ONBOARDING_STEPS


def test_onboarding_ends_on_a_plan_without_preparing_a_practice() -> None:
    # A practice is created only from the practice start page, after the person chooses to start.
    for call in ("mirrorApi.createSession", "mirrorApi.prepare", "linkSessionDocuments", "onboarding_session_id"):
        assert call not in ONBOARDING + ONBOARDING_STEPS
    assert "PlanReadyStep" in ONBOARDING


def test_legacy_setup_route_redirects_to_the_unified_flow() -> None:
    assert 'redirect("/onboarding")' in SETUP_PAGE
    assert 'redirect("/dashboard")' in SETUP_PAGE


def test_my_experience_reads_everything_including_what_was_removed() -> None:
    assert "mirrorApi.evidence(true)" in EXPERIENCE
    assert "mirrorApi.resumeAnalysis" in EXPERIENCE
    assert "groupExperience" in EXPERIENCE


def test_my_experience_is_organised_into_the_sections_people_recognise() -> None:
    for section in ("resume:", "work:", "projects:", "achievements:"):
        assert section in COPY
    for anchor in (
        "experience-resume",
        "experience-work",
        "experience-projects",
        "experience-achievements",
        "experience-removed",
    ):
        assert anchor in EXPERIENCE


def test_my_experience_offers_every_lifecycle_action_the_backend_supports() -> None:
    for call in (
        "uploadEvidenceDocument",
        "mirrorApi.updateEvidence",
        "mirrorApi.archiveEvidence",
        "mirrorApi.restoreEvidence",
        "downloadEvidenceDocument",
    ):
        assert call in EXPERIENCE
    assert "EvidenceRemoveDialog" in EXPERIENCE  # removal always confirms first
    assert "signOut" not in EXPERIENCE


def test_my_experience_never_shows_a_completeness_number() -> None:
    # Guidance is a sentence about what is missing, never a count or a percentage.
    assert "%" not in EXPERIENCE_VIEW
    assert "experienceGuidance" in EXPERIENCE_VIEW
    assert "items added" not in EXPERIENCE


def test_evidence_edit_and_remove_flows_surface_historical_safety() -> None:
    assert "Context for Mirror" in EVIDENCE_DRAWER
    assert "What Mirror extracted" in EVIDENCE_DRAWER
    assert "Used in sessions" in EVIDENCE_DRAWER
    assert "session in progress" in EVIDENCE_DRAWER
    assert "Historical versions stay intact" in EVIDENCE_DIALOGS
    assert "your past sessions will stay as they are" in EVIDENCE_DIALOGS


def test_the_drawer_exposes_only_implemented_lifecycle_actions() -> None:
    for label in ("Edit details", "Replace file", "Download", "Remove", "Restore to library"):
        assert label in EVIDENCE_DRAWER
    assert "Permanently delete" not in EVIDENCE_DRAWER


def test_evidence_api_uses_owner_scoped_backend_operations() -> None:
    for contract in (
        "evidenceDetail",
        "updateEvidence",
        "archiveEvidence",
        "restoreEvidence",
        "uploadEvidenceDocument",
        "downloadEvidenceDocument",
    ):
        assert contract in API


def test_evidence_taxonomy_has_one_frontend_source() -> None:
    assert "EVIDENCE_CATEGORIES" in EVIDENCE_TYPES
    assert EVIDENCE_DRAWER.count("EVIDENCE_CATEGORIES") >= 1
    assert EVIDENCE_DIALOGS.count("EVIDENCE_CATEGORIES") >= 1
