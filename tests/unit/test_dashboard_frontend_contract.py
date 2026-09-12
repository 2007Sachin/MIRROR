from pathlib import Path


ROOT = Path(__file__).parents[2]
WEB = ROOT / "apps" / "web" / "src"
DASHBOARD = (WEB / "components" / "evidence-dashboard.tsx").read_text(
    encoding="utf-8"
)
DASHBOARD_PAGE = (WEB / "app" / "dashboard" / "page.tsx").read_text(
    encoding="utf-8"
)
CURRENT_DIAGNOSTIC = (
    WEB / "components" / "workspace" / "current-diagnostic.tsx"
).read_text(encoding="utf-8")
APP_SHELL = (WEB / "components" / "workspace" / "app-shell.tsx").read_text(
    encoding="utf-8"
)
RECENT_DIAGNOSTICS = (
    WEB / "components" / "workspace" / "recent-diagnostics.tsx"
).read_text(encoding="utf-8")
EVIDENCE_PREVIEW = (
    WEB / "components" / "workspace" / "evidence-preview.tsx"
).read_text(encoding="utf-8")
AUTH_FORM = (WEB / "components" / "auth-form.tsx").read_text(encoding="utf-8")
PROXY = (WEB / "proxy.ts").read_text(encoding="utf-8")
API = (WEB / "lib" / "api.ts").read_text(encoding="utf-8")
ASSESSMENT_REPOSITORY = (
    ROOT / "apps" / "api" / "app" / "assessment_pipeline_repository.py"
).read_text(encoding="utf-8")


def test_dashboard_is_an_authenticated_evidence_workspace() -> None:
    assert "getServerOnboarding" in DASHBOARD_PAGE
    assert 'redirect("/login?reason=session_expired")' in DASHBOARD_PAGE
    assert 'redirect("/onboarding")' in DASHBOARD_PAGE
    assert "Your evidence workspace" in DASHBOARD
    assert "Current diagnostic" in CURRENT_DIAGNOSTIC
    assert "Recent diagnostics" in RECENT_DIAGNOSTICS
    assert "Continue building your case" in (
        WEB / "components" / "workspace" / "quick-actions.tsx"
    ).read_text(encoding="utf-8")
    assert "Your evidence library" in EVIDENCE_PREVIEW
    assert "Build your first evidence case" in DASHBOARD


def test_dashboard_uses_canonical_status_and_report_data() -> None:
    assert "mirrorApi.dashboard()" in DASHBOARD
    assert "diagnostic_available" in CURRENT_DIAGNOSTIC
    assert "assessment?.status" in CURRENT_DIAGNOSTIC
    assert "claims_audit" not in DASHBOARD
    assert "skill_assessments" not in DASHBOARD
    assert "setInterval" not in DASHBOARD
    assert "POLL_DELAYS" in DASHBOARD


def test_failed_assessment_is_recoverable_without_repeating_interview() -> None:
    assert "Your interview has been saved" in CURRENT_DIAGNOSTIC
    assert "Retry evaluation" in CURRENT_DIAGNOSTIC
    assert "mirrorApi.retryAssessment(id)" in DASHBOARD
    assert "completed owned session not found" in ASSESSMENT_REPOSITORY
    assert '"status": "pending"' in ASSESSMENT_REPOSITORY


def test_returning_authentication_routes_to_dashboard_without_auto_logout() -> None:
    assert 'router.replace("/dashboard")' in AUTH_FORM
    assert 'redirectWithCookies(request, response, "/dashboard")' in PROXY
    assert '"/dashboard/:path*"' in PROXY
    assert "auth.signOut()" in APP_SHELL
    assert "ApiError && reason.status === 401" in DASHBOARD


def test_authenticated_sidebar_routes_are_real_and_guarded() -> None:
    for route in ("diagnostics", "evidence", "roles", "settings"):
        page = (WEB / "app" / route / "page.tsx").read_text(encoding="utf-8")
        assert "getServerOnboarding" in page
        assert 'redirect("/login?reason=session_expired")' in page
        assert 'redirect("/onboarding")' in page
        assert f'"/{route}/:path*"' in PROXY
        assert f'"/{route}"' in APP_SHELL


def test_frontend_api_exposes_dashboard_completion_and_retry_contracts() -> None:
    assert "SessionCompletion" in API
    assert 'request<DashboardResponse>("/api/v1/dashboard")' in API
    assert "/assessment/retry" in API
