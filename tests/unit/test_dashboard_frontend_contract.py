from pathlib import Path


ROOT = Path(__file__).parents[2]
WEB = ROOT / "apps" / "web" / "src"
DASHBOARD = (WEB / "components" / "evidence-dashboard.tsx").read_text(
    encoding="utf-8"
)
DASHBOARD_PAGE = (WEB / "app" / "dashboard" / "page.tsx").read_text(
    encoding="utf-8"
)
SECTIONS = (WEB / "components" / "dashboard" / "sections.tsx").read_text(encoding="utf-8")
PRACTICE_LAUNCHER = (WEB / "components" / "dashboard" / "practice-launcher.tsx").read_text(encoding="utf-8")
VIEW = (WEB / "lib" / "dashboard-view.ts").read_text(encoding="utf-8")
COPY = (WEB / "lib" / "copy.ts").read_text(encoding="utf-8")
APP_SHELL = (WEB / "components" / "workspace" / "app-shell.tsx").read_text(
    encoding="utf-8"
)
AUTH_FORM = (WEB / "components" / "auth-form.tsx").read_text(encoding="utf-8")
PROXY = (WEB / "proxy.ts").read_text(encoding="utf-8")
START_PRACTICE = (WEB / "lib" / "start-practice.ts").read_text(encoding="utf-8")
API = (WEB / "lib" / "api.ts").read_text(encoding="utf-8")
ASSESSMENT_REPOSITORY = (
    ROOT / "apps" / "api" / "app" / "assessment_pipeline_repository.py"
).read_text(encoding="utf-8")


def home_copy() -> str:
    start = COPY.index("export const home = {")
    return COPY[start : COPY.index("} as const;", start)]


def test_dashboard_is_an_authenticated_home_page() -> None:
    assert "getServerOnboarding" in DASHBOARD_PAGE
    assert 'redirect("/login?reason=session_expired")' in DASHBOARD_PAGE
    assert 'redirect("/onboarding")' in DASHBOARD_PAGE
    copy = home_copy()
    for text in ("Here's where you stand and what to work on next", "Start practice",
                 "Your latest review", "How you're developing", "Continue preparing", "Your next step"):
        assert text in copy, text
    assert "initialOnboarding={result.onboarding}" in DASHBOARD_PAGE


def test_home_page_uses_candidate_friendly_words() -> None:
    copy = home_copy().lower()
    for word in ("evidence", "claim", "diagnostic", "verdict", "skeptic", "adjudication", "weak claim"):
        assert word not in copy, word


def test_dashboard_uses_canonical_status_and_report_data() -> None:
    assert "mirrorApi.dashboard()" in DASHBOARD
    assert "mirrorApi.dashboardSummary()" in DASHBOARD
    assert "diagnostic_available" in VIEW
    assert "assessment?.status" in VIEW
    # The page renders what the API derives; it never reads the report's internals itself.
    for source in (DASHBOARD, VIEW, SECTIONS):
        assert "claims_audit" not in source
        assert "skill_assessments" not in source
    assert "setInterval" not in DASHBOARD
    assert "POLL_DELAYS" in DASHBOARD


def test_failed_assessment_is_recoverable_without_repeating_interview() -> None:
    copy = home_copy()
    assert "Your conversation is saved" in copy
    assert "Try again" in copy
    assert "mirrorApi.retryAssessment(current.id)" in DASHBOARD
    assert "completed owned session not found" in ASSESSMENT_REPOSITORY
    assert '"status": "pending"' in ASSESSMENT_REPOSITORY


def test_sidebar_is_navigation_only_and_uses_candidate_words() -> None:
    assert not (WEB / "components" / "workspace" / "sidebar-overview.tsx").exists()
    for label in ("Home", "Practice", "My Experience", "Roles", "Progress", "Settings", "Help"):
        assert f'label: "{label}"' in APP_SHELL
    for internal in ("Recent Sessions", "Experience Library", "Evidence Library", "Claims", "Diagnostic"):
        assert internal not in APP_SHELL
    assert "ws-sidebar-overview" not in APP_SHELL
    assert "ws-mobile-nav" in APP_SHELL


def test_missing_review_data_never_signs_the_user_out() -> None:
    # Only a genuine 401 signs anyone out; a pending or unreadable review is just a state.
    assert DASHBOARD.count('router.replace("/login?reason=session_expired")') == 2
    assert DASHBOARD.count("reason.status === 401") == 2
    assert "summaryFor.current = null" in DASHBOARD
    assert '"network")' not in PROXY  # an unreachable auth service is not a sign-out


def test_every_dashboard_action_goes_somewhere_real() -> None:
    for source in (DASHBOARD, SECTIONS, PRACTICE_LAUNCHER):
        assert 'href="#"' not in source
        assert "onClick={() => {}}" not in source


def test_returning_authentication_routes_to_dashboard_without_auto_logout() -> None:
    assert 'router.replace("/dashboard")' in AUTH_FORM
    assert 'redirectWithCookies(request, response, "/dashboard")' in PROXY
    assert '"/dashboard/:path*"' in PROXY
    assert "auth.signOut()" in APP_SHELL
    assert "reason.status === 401" in DASHBOARD


def test_authenticated_sidebar_routes_are_real_and_guarded() -> None:
    for route in ("practice", "experience", "roles", "progress", "help", "settings"):
        page = (WEB / "app" / route / "page.tsx").read_text(encoding="utf-8")
        assert "getServerOnboarding" in page
        assert 'redirect("/login?reason=session_expired")' in page
        assert 'redirect("/onboarding")' in page
        assert f'"/{route}/:path*"' in PROXY
        assert f'"/{route}"' in APP_SHELL


def test_the_routes_practice_and_experience_moved_from_still_work() -> None:
    for old, new in (("diagnostics", "/practice"), ("evidence", "/experience")):
        page = (WEB / "app" / old / "page.tsx").read_text(encoding="utf-8")
        assert f'redirect("{new}")' in page
        assert f'"/{old}/:path*"' in PROXY


def test_home_supports_each_phase_one_user_state() -> None:
    for state in ("review_ready", "review_processing", "review_failed", "in_progress", "ready", "failed"):
        assert f'case "{state}"' in DASHBOARD
    assert "SetupProgress" in DASHBOARD
    assert "Complete another practice to see how your answers are developing" in home_copy()
    assert "Your work is saved" in home_copy()


def test_home_has_only_the_four_phase_one_content_concepts() -> None:
    for component in ("NextAction", "ReviewSummary", "DevelopmentAreas", "ContinuePreparing"):
        assert component in DASHBOARD
    assert "dh-signals" not in SECTIONS
    assert "counts.clear" not in SECTIONS
    assert "ImprovementAreas" not in DASHBOARD
    assert "SidebarOverview" not in DASHBOARD


def test_development_mapper_uses_four_plain_language_states() -> None:
    for state in ("Coming through clearly", "Developing", "Needs more practice", "Not explored yet"):
        assert state in VIEW
    for label in ("Connecting your experience to the role", "Using real examples", "Explaining your decisions", "Showing your impact"):
        assert label in VIEW
    assert "developmentAreas(review)" in DASHBOARD


def test_start_practice_reuses_existing_setup_only_when_safe() -> None:
    assert "practiceOptions(sessions, initialOnboarding)" in DASHBOARD
    assert "onboarding_resume_document_id" in VIEW
    assert "onboarding_role_profile_id" in VIEW
    # Starting a practice lives in one module, used by Home and by Practice.
    assert "canStartDirectly" in DASHBOARD and "createPractice" in DASHBOARD
    assert "mirrorApi.createSession(role" in START_PRACTICE
    assert "mirrorApi.linkSessionDocuments" in START_PRACTICE
    assert "mirrorApi.prepare" in START_PRACTICE
    assert "What do you want to prepare for?" in home_copy()


def test_dashboard_topbar_and_responsive_navigation_are_present() -> None:
    assert "Help" in APP_SHELL
    assert "aria-expanded={sidebarOpen}" in APP_SHELL
    assert "ws-mobile-nav" in APP_SHELL


def test_the_profile_menu_is_an_account_menu_and_nothing_is_invented() -> None:
    assert 'aria-haspopup="menu"' in APP_SHELL
    assert 'role="menuitem"' in APP_SHELL
    assert "menuCopy.signOut" in APP_SHELL
    # No notification surface exists in the backend, so none is shown.
    assert "Notifications" not in APP_SHELL
    # The account menu never repeats the main navigation.
    for route in ("/practice", "/experience", "/roles", "/progress"):
        assert f'href="{route}"' not in APP_SHELL.split("function ProfileMenu")[1]


def test_frontend_api_exposes_dashboard_completion_and_retry_contracts() -> None:
    assert "SessionCompletion" in API
    assert 'request<DashboardResponse>("/api/v1/dashboard")' in API
    assert "/assessment/retry" in API
