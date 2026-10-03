from pathlib import Path


ROOT = Path(__file__).parents[2]
WEB = ROOT / "apps" / "web" / "src"
DASHBOARD = (WEB / "components" / "dashboard" / "home-page.tsx").read_text(encoding="utf-8")
DASHBOARD_PAGE = (WEB / "app" / "dashboard" / "page.tsx").read_text(
    encoding="utf-8"
)
SECTIONS = (WEB / "components" / "dashboard" / "home-parts.tsx").read_text(encoding="utf-8")
HOME_SERVICE = (ROOT / "apps" / "api" / "app" / "home_service.py").read_text(encoding="utf-8")
VIEW = (WEB / "lib" / "dashboard-view.ts").read_text(encoding="utf-8")
HOME_VIEW = (WEB / "lib" / "home-view.ts").read_text(encoding="utf-8")
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
    start = COPY.index("export const homeNow = {")
    return COPY[start : COPY.index("} as const;", start)]


def test_dashboard_is_an_authenticated_home_page() -> None:
    assert "getServerOnboarding" in DASHBOARD_PAGE
    assert 'redirect("/login?reason=session_expired")' in DASHBOARD_PAGE
    assert 'redirect("/onboarding")' in DASHBOARD_PAGE
    copy = home_copy()
    for text in ("Continue where you left off", "Start practice", "Your preparation",
                 "Recent activity", "Recommended next step", "Since your last practice"):
        assert text.lower() in copy.lower(), text
    assert "initialRole={role}" in DASHBOARD_PAGE


def test_home_page_uses_candidate_friendly_words() -> None:
    copy = home_copy().lower()
    for word in ("evidence", "claim", "diagnostic", "verdict", "skeptic", "adjudication", "weak claim"):
        assert word not in copy, word


def test_dashboard_uses_canonical_status_and_report_data() -> None:
    # One request decides Home; the page never stitches five sources together itself.
    assert "mirrorApi.home(" in DASHBOARD
    for call in ("mirrorApi.dashboard()", "mirrorApi.dashboardSummary()", "mirrorApi.interviewMap", "mirrorApi.pressureTest", "mirrorApi.practiceRecommendation"):
        assert call not in DASHBOARD
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
    assert "mirrorApi.retryAssessment(sessionId)" in DASHBOARD
    assert "completed owned session not found" in ASSESSMENT_REPOSITORY
    assert '"status": "pending"' in ASSESSMENT_REPOSITORY


def test_sidebar_is_navigation_only_and_uses_candidate_words() -> None:
    assert not (WEB / "components" / "workspace" / "sidebar-overview.tsx").exists()
    shell_copy = (WEB / "lib" / "copy-shell.ts").read_text(encoding="utf-8")
    for label in ("Home", "My plan", "My stories", "Practice", "Reflect", "My experience", "Roles", "Preferences", "Help"):
        assert f'label: "{label}"' in shell_copy
    for internal in ("Recent Sessions", "Experience Library", "Evidence Library", "Claims", "Diagnostic"):
        assert internal not in APP_SHELL
    assert "ws-sidebar-overview" not in APP_SHELL
    assert "ws-mobile-nav" in APP_SHELL


def test_missing_review_data_never_signs_the_user_out() -> None:
    # Only a genuine 401 signs anyone out; a pending or unreadable review is just a state.
    # Home signs out only on its own 401; the profile's 401 is handled once, in the shared useProfile.
    assert DASHBOARD.count('router.replace("/login?reason=session_expired")') == 1
    assert DASHBOARD.count("reason.status === 401") == 1
    assert "useProfile()" in DASHBOARD
    page_shell = (WEB / "components" / "workspace" / "page-shell.tsx").read_text(encoding="utf-8")
    assert "reason.status === 401" in page_shell
    assert "setFailed(true)" in DASHBOARD  # a failed load is an error, never an empty Home
    assert '"network")' not in PROXY  # an unreachable auth service is not a sign-out


def test_every_dashboard_action_goes_somewhere_real() -> None:
    for source in (DASHBOARD, SECTIONS):
        assert 'href="#"' not in source
        assert "onClick={() => {}}" not in source


def test_returning_authentication_routes_to_dashboard_without_auto_logout() -> None:
    assert 'router.replace("/dashboard")' in AUTH_FORM
    assert 'redirectWithCookies(request, response, "/dashboard")' in PROXY
    assert '"/dashboard/:path*"' in PROXY
    assert "auth.signOut()" in APP_SHELL
    assert "reason.status === 401" in DASHBOARD


def test_authenticated_sidebar_routes_are_real_and_guarded() -> None:
    for route in ("practice", "plan", "experience", "roles", "reflect", "help", "settings"):
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


def test_home_renders_each_server_state_and_never_picks_one_itself() -> None:
    for state in ("ACTIVE_PRACTICE", "REVIEW_READY", "REVIEW_PROCESSING", "REVIEW_FAILED", "FIRST_PRACTICE",
                  "EARLY_BASELINE", "RECOMMENDED_NEXT", "RETURNING", "NO_ROLE"):
        assert f'"{state}"' in API and state in HOME_SERVICE
    assert "data.state ===" in SECTIONS
    # Precedence lives in one documented place on the server.
    assert "State precedence for the selected role, first match wins" in HOME_SERVICE
    assert "def decide(" in HOME_SERVICE
    for banned in ("sessionKind(", "buildHomeView", "reviewForRole", "hasCompletedPractice"):
        assert banned not in DASHBOARD and banned not in SECTIONS


def test_active_practice_beats_starting_another_and_saved_copy_is_not_repeated() -> None:
    copy = COPY[COPY.index("export const homeNow = {") : COPY.index("export const progress = {")]
    assert "Continue practice" in copy and "Your work is saved" not in copy
    # A cross-role unfinished practice keeps its own block, named for its own role.
    assert "other_active" in SECTIONS and "t.otherRole.continue(practice.target_role)" in SECTIONS
    # Ending goes through the existing end endpoint after a confirmation.
    assert "mirrorApi.endInterview(sessionId)" in DASHBOARD and "hm-confirm" in SECTIONS


def test_home_consumes_progress_analytics_and_computes_none() -> None:
    assert "insightViews(data.progress" in SECTIONS
    for source in (SECTIONS, HOME_VIEW):
        assert "trend =" not in source and "Math.round" not in source and "toFixed" not in source
    assert "summary_from" in HOME_SERVICE and "map_and_recommendation" in HOME_SERVICE


def test_home_qa_fixture_is_local_only_and_does_not_alter_dashboard_auth() -> None:
    qa_page = (WEB / "app" / "home-qa" / "page.tsx").read_text(encoding="utf-8")
    qa_fixtures = (WEB / "lib" / "home-qa-fixtures.ts").read_text(encoding="utf-8")
    assert 'process.env.NODE_ENV === "production"' in qa_page
    assert 'process.env.MIRROR_HOME_QA !== "1"' in qa_page
    assert "notFound()" in qa_page
    assert "Supabase" in qa_fixtures and "authorization" in qa_fixtures
    assert "home-qa" not in DASHBOARD_PAGE
    for scenario in ("active", "review-ready", "returning", "new-role", "early", "cross-role-active"):
        assert f'id: "{scenario}"' in qa_fixtures


def test_role_switching_is_a_view_choice_kept_in_the_address() -> None:
    assert "window.history.replaceState" in DASHBOARD and "?role=" in DASHBOARD
    assert "role_profile_id=" in API and "data.roles.length < 2" in SECTIONS
    assert "aria-label={t.roleLabel}" in SECTIONS  # a real, keyboard-operable select


def test_development_mapper_uses_four_plain_language_states() -> None:
    for state in ("Coming through clearly", "Developing", "Needs more practice", "Not explored yet"):
        assert state in VIEW
    progress_view = (WEB / "lib" / "progress-view.ts").read_text(encoding="utf-8")
    for label in ("Connecting your experience to the role", "Using real examples", "Explaining your decisions", "Showing your impact"):
        assert label in progress_view


def test_starting_a_practice_carries_the_exact_role() -> None:
    assert "startRoleHref" in SECTIONS and "startStepHref" in SECTIONS
    assert "role_profile_id" in HOME_VIEW and "startPracticeHref" in HOME_VIEW
    assert "mirrorApi.createSession(role" in START_PRACTICE
    assert "mirrorApi.linkSessionDocuments" in START_PRACTICE
    assert "mirrorApi.prepare" in START_PRACTICE


def test_dashboard_topbar_and_responsive_navigation_are_present() -> None:
    assert "shellCopy.profile.help" in APP_SHELL  # Help lives in the profile menu
    assert "aria-expanded={sidebarOpen}" in APP_SHELL
    assert "ws-mobile-nav" in APP_SHELL


def test_the_profile_menu_is_an_account_menu_and_nothing_is_invented() -> None:
    assert 'aria-haspopup="menu"' in APP_SHELL
    assert 'role="menuitem"' in APP_SHELL
    assert "menuCopy.signOut" in APP_SHELL
    # No notification surface exists in the backend, so none is shown.
    assert "Notifications" not in APP_SHELL
    # The account menu never repeats the main navigation.
    profile_items = APP_SHELL.split("const profileNavigation")[1].split("];")[0]
    for route in ("/experience", "/roles", "/settings", "/help"):
        assert f'href: "{route}"' in profile_items
    for route in ("/dashboard", "/plan", "/stories", "/practice", "/reflect", "/progress"):
        assert f'"{route}"' not in profile_items
        assert f'href="{route}"' not in APP_SHELL.split("function ProfileMenu")[1]


def test_frontend_api_exposes_dashboard_completion_and_retry_contracts() -> None:
    assert "SessionCompletion" in API
    assert 'request<DashboardResponse>("/api/v1/dashboard")' in API
    assert "/assessment/retry" in API


def test_home_surfaces_an_interview_within_two_days_without_competing_with_the_primary_card() -> None:
    assert "upcoming_interview: UpcomingInterview | None = None" in HOME_SERVICE
    assert "timing(e.scheduled_for, now) == Timing.SOON" in HOME_SERVICE
    assert "upcoming_interview?: HomeUpcomingInterview | null;" in API
    stack = SECTIONS[SECTIONS.index('<div className="hm-stack">'):]
    assert stack.index("<UpcomingInterview") < stack.index("<Primary ")
    assert '<aside className="hm-upcoming" aria-label={t.upcoming.label}>' in SECTIONS
    assert 'className="hm-text-action" href={briefHref(event)}' in SECTIONS  # a text link, never a second primary button
    assert "return `/roles/${event.role_profile_id}/interviews/${event.event_id}`;" in HOME_VIEW
    copy = home_copy()
    assert "Read your brief" in copy and "Interview coming up" in copy
    fixtures = (WEB / "lib" / "home-qa-fixtures.ts").read_text(encoding="utf-8")
    assert 'id: "upcoming-interview"' in fixtures and "upcoming_interview: {" in fixtures
