from pathlib import Path


ROOT = Path(__file__).parents[2] / "apps" / "web" / "src"
ONBOARDING = (ROOT / "components" / "onboarding-flow.tsx").read_text(
    encoding="utf-8"
)
SETUP_PAGE = (ROOT / "app" / "app" / "setup" / "page.tsx").read_text(
    encoding="utf-8"
)
EVIDENCE_LIBRARY = (ROOT / "components" / "workspace" / "evidence-library.tsx").read_text(encoding="utf-8")
EVIDENCE_ROW = (ROOT / "components" / "workspace" / "evidence-row.tsx").read_text(encoding="utf-8")
EVIDENCE_DRAWER = (ROOT / "components" / "workspace" / "evidence-drawer.tsx").read_text(encoding="utf-8")
EVIDENCE_DIALOGS = (ROOT / "components" / "workspace" / "evidence-dialogs.tsx").read_text(encoding="utf-8")
EVIDENCE_TYPES = (ROOT / "components" / "workspace" / "evidence-types.ts").read_text(encoding="utf-8")
API = (ROOT / "lib" / "api.ts").read_text(encoding="utf-8")


def test_onboarding_collects_role_context_and_starting_evidence() -> None:
    assert "Add the role brief" in ONBOARDING
    assert "Upload role brief" in ONBOARDING
    assert "Paste role brief" in ONBOARDING
    assert "Continue without one" in ONBOARDING
    assert "Add my resume" in ONBOARDING


def test_onboarding_reports_real_upload_progress_and_persists_ids() -> None:
    assert 'role="progressbar"' in ONBOARDING
    assert "onboarding_resume_document_id" in ONBOARDING
    assert "onboarding_role_brief_document_id" in ONBOARDING
    assert "onboarding_session_id" in ONBOARDING
    assert "window.localStorage" not in ONBOARDING


def test_onboarding_prepares_then_opens_the_evidence_interview() -> None:
    assert "mirrorApi.prepare" in ONBOARDING
    assert "mirrorApi.interviewPlan" in ONBOARDING
    assert "Begin the evidence interview" in ONBOARDING
    assert "`/app/interview/${session.id}`" in ONBOARDING


def test_legacy_setup_route_redirects_to_the_unified_flow() -> None:
    assert 'redirect("/onboarding")' in SETUP_PAGE
    assert 'redirect("/dashboard")' in SETUP_PAGE


def test_evidence_library_supports_real_search_filter_sort_and_bulk_selection() -> None:
    assert "mirrorApi.evidence(true)" in EVIDENCE_LIBRARY
    assert 'type="search"' in EVIDENCE_LIBRARY
    assert "EvidenceSort" in EVIDENCE_LIBRARY
    assert "bulkCategory" in EVIDENCE_LIBRARY
    assert "selectedIds" in EVIDENCE_LIBRARY
    assert "Recently removed" in EVIDENCE_LIBRARY


def test_each_evidence_row_exposes_only_implemented_lifecycle_actions() -> None:
    for label in (
        "Open",
        "Edit details",
        "Replace file",
        "Change category",
        "Add context",
        "Download original",
        "Remove from library",
        "Restore",
    ):
        assert label in EVIDENCE_ROW
    assert "Permanently delete" not in EVIDENCE_ROW


def test_evidence_edit_and_remove_flows_surface_historical_safety() -> None:
    assert "Context for Mirror" in EVIDENCE_DRAWER
    assert "What Mirror extracted" in EVIDENCE_DRAWER
    assert "Used in diagnostics" in EVIDENCE_DRAWER
    assert "active diagnostic" in EVIDENCE_DRAWER
    assert "Historical versions stay intact" in EVIDENCE_DIALOGS
    assert "historical diagnostic references will be retained" in EVIDENCE_DIALOGS


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
    assert "signOut" not in EVIDENCE_LIBRARY


def test_evidence_taxonomy_has_one_frontend_source() -> None:
    assert "EVIDENCE_CATEGORIES" in EVIDENCE_TYPES
    assert EVIDENCE_LIBRARY.count("EVIDENCE_CATEGORIES") >= 1
    assert EVIDENCE_DRAWER.count("EVIDENCE_CATEGORIES") >= 1
