"""Home: one dominant next action, decided on the server, scoped to one role and one person."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.home_service import (
    ACTIVITY_LIMIT,
    REVIEW_FRESH,
    HomeService,
    HomeState,
    SessionKind,
    decide,
    session_kind,
)
from app.dashboard_repository import DashboardUnavailable
from app.interview_map import Coverage, ExperienceState, InterviewMap, InterviewTheme, MapState
from app.practice_modes import PracticeFocus, PracticeMode
from app.practice_recommendation import PracticeRecommendation, RecommendationSource
from app.report_models import SessionMomentType
from app.role_progress import RoleProgressService
from app.role_service import RoleProfileNotFoundForUser
from app.story_models import StoryRead
from tests.test_role_progress import (
    OTHER,
    USER,
    FakeReports,
    moment,
    profile,
    report,
    session,
)

NOW = datetime.now(UTC)


def story(title, *, ready, days_ago=1):
    text = "Something specific happened here."
    fields = dict(situation=text, actions=text, outcome=text)
    if ready:
        fields.update(ownership=text, reasoning=text)
    when = NOW - timedelta(days=days_ago)
    return StoryRead(id=uuid4(), user_id=USER, title=title, origin="MANUAL", created_at=when, updated_at=when, **fields)


def interview_map(role, *, missing=2, state=MapState.READY):
    themes = [
        InterviewTheme(key=f"t{i}", name=f"Theme {i}", category="ANALYTICAL", from_job_description=True,
                       coverage=Coverage.MISSING if i < missing else Coverage.PREPARED)
        for i in range(4)
    ]
    return InterviewMap(role_profile_id=role.id, target_role=role.target_role, state=state,
                        experience_state=ExperienceState.READY, themes=themes if state == MapState.READY else [])


def recommendation(role):
    return PracticeRecommendation(role_profile_id=role.id, target_role=role.target_role, mode=PracticeMode.QUICK_DRILL,
                                  focus=PracticeFocus.DECISIONS, reason="Your answers describe what you did.", source=RecommendationSource.REVIEW)


class FakeRoles:
    def __init__(self, by_user):
        self.by_user = by_user

    async def families(self, user_id):
        return self.by_user.get(user_id, [])

    async def get(self, profile_id, user_id):  # not used by summary_from, kept for the interface
        raise RoleProfileNotFoundForUser


class FakeDashboard:
    def __init__(self, by_user):
        self.by_user = by_user
        self.calls = 0

    async def sessions(self, user_id, limit=100):
        self.calls += 1
        return self.by_user.get(user_id, [])


class FakeReadiness:
    def __init__(self, rec=True, missing=2, state=MapState.READY, fail=False):
        self.rec, self.missing, self.state, self.fail = rec, missing, state, fail

    async def map_and_recommendation(self, role_profile_id, user_id):
        if self.fail is True:
            raise DashboardUnavailable("role analysis down")
        if self.fail:
            raise self.fail
        role = SimpleNamespace(id=role_profile_id, target_role="Data Analyst")
        rec = recommendation(role) if self.rec and self.state == MapState.READY else None
        return interview_map(role, missing=self.missing, state=self.state), rec


class FakeStories:
    def __init__(self, rows, fail=False):
        self.rows, self.fail = rows, fail

    async def list_for_user(self, user_id):
        if self.fail:
            from app.story_repository import StoriesUnavailable

            raise StoriesUnavailable("stories down")
        return self.rows


def build(sessions, *, readiness=None, stories=None, reports=None):
    """Home for USER with two roles; reports default to a readable review for every session."""
    analyst = profile(USER, "Data Analyst")
    manager = profile(USER, "Product Manager")
    roles = [(analyst, frozenset({analyst.id})), (manager, frozenset({manager.id}))]
    dashboard = FakeDashboard({USER: sessions(analyst, manager)})
    by_session = reports or {s.id: report() for s in dashboard.by_user[USER]}
    progress = RoleProgressService(FakeRoles({USER: roles}), dashboard, FakeReports(by_session), None, None)
    service = HomeService(FakeRoles({USER: roles, OTHER: []}), dashboard, progress, readiness or FakeReadiness(), stories or FakeStories([]))
    return service, analyst, manager, dashboard


# ----------------------------------------------------------------- the pure decision


def base(**overrides):
    args = dict(active=None, newest=None, practice_count=0, has_next_step=False, now=NOW)
    args.update(overrides)
    return decide(**args)


def test_precedence_is_fixed() -> None:
    role = profile(USER)
    fresh_review = session(role.id, days_ago=0)
    old_review = session(role.id, days_ago=3)
    processing = session(role.id, days_ago=0, available=False)
    active = SimpleNamespace()  # any non-None active practice
    assert base(active=active, newest=fresh_review, practice_count=3, has_next_step=True) == HomeState.ACTIVE_PRACTICE
    assert base(newest=processing, practice_count=3, has_next_step=True) == HomeState.REVIEW_PROCESSING
    assert base(newest=fresh_review, practice_count=3, has_next_step=True) == HomeState.REVIEW_READY
    assert base(newest=old_review, practice_count=3, has_next_step=True) == HomeState.RECOMMENDED_NEXT
    assert base(newest=old_review, practice_count=3, has_next_step=False) == HomeState.RETURNING
    assert base(newest=old_review, practice_count=1) == HomeState.EARLY_BASELINE
    assert base() == HomeState.FIRST_PRACTICE


def test_a_review_stops_being_the_headline_after_it_is_no_longer_fresh() -> None:
    role = profile(USER)
    edge = session(role.id, days_ago=0).model_copy(update={"completed_at": NOW - REVIEW_FRESH + timedelta(minutes=1)})
    stale = session(role.id, days_ago=0).model_copy(update={"completed_at": NOW - REVIEW_FRESH - timedelta(minutes=1)})
    assert base(newest=edge, practice_count=2) == HomeState.REVIEW_READY
    assert base(newest=stale, practice_count=2) == HomeState.RETURNING


def test_session_kinds() -> None:
    role = profile(USER)
    assert session_kind(session(role.id, days_ago=0)) == SessionKind.REVIEW_READY
    assert session_kind(session(role.id, days_ago=0, status="ACTIVE", available=False)) == SessionKind.ACTIVE
    assert session_kind(session(role.id, days_ago=0, status="READY", available=False)) == SessionKind.READY
    assert session_kind(session(role.id, days_ago=0, status="COMPLETED", available=False)) == SessionKind.REVIEW_PROCESSING
    assert session_kind(session(role.id, days_ago=0, status="CREATED", available=False)) == SessionKind.OTHER


# ----------------------------------------------------------------- each state, end to end


@pytest.mark.asyncio
async def test_no_role() -> None:
    service = HomeService(FakeRoles({USER: []}), FakeDashboard({USER: []}), None, FakeReadiness(), FakeStories([]))
    result = await service.home(USER)
    assert result.state == HomeState.NO_ROLE and result.roles == [] and result.selected is None


@pytest.mark.asyncio
async def test_first_practice_for_a_new_role_has_no_analytics() -> None:
    service, _, manager, _ = build(lambda a, m: [])
    result = await service.home(USER, manager.id)
    assert result.state == HomeState.FIRST_PRACTICE
    assert result.progress.stage.value == "NONE" and result.progress.insights == [] and result.progress.highlights == []


@pytest.mark.asyncio
async def test_early_baseline_shows_what_one_practice_showed_and_no_trend() -> None:
    service, analyst, _, _ = build(lambda a, m: [session(a.id, days_ago=3)])
    result = await service.home(USER, analyst.id)
    assert result.state == HomeState.EARLY_BASELINE
    assert result.progress.stage.value == "BASELINE" and result.progress.insights == []
    assert result.progress.highlights  # observations from that one practice only


@pytest.mark.asyncio
async def test_recommended_next_uses_the_existing_recommendation_and_links_the_progress_area() -> None:
    service, analyst, _, _ = build(lambda a, m: [session(a.id, days_ago=3), session(a.id, days_ago=6)])
    result = await service.home(USER, analyst.id)
    assert result.state == HomeState.RECOMMENDED_NEXT
    assert result.next_step.focus == "decisions" and result.next_step.dimension == "depth"
    assert result.next_step.role_profile_id == analyst.id


@pytest.mark.asyncio
async def test_returning_without_a_recommendation_still_has_one_action() -> None:
    service, analyst, _, _ = build(lambda a, m: [session(a.id, days_ago=3), session(a.id, days_ago=6)], readiness=FakeReadiness(rec=False))
    result = await service.home(USER, analyst.id)
    assert result.state == HomeState.RETURNING and result.next_step is None


@pytest.mark.asyncio
async def test_review_ready_beats_the_recommendation() -> None:
    service, analyst, _, _ = build(lambda a, m: [session(a.id, days_ago=0), session(a.id, days_ago=6)])
    result = await service.home(USER, analyst.id)
    assert result.state == HomeState.REVIEW_READY
    assert result.review.kind == SessionKind.REVIEW_READY and result.next_step is not None


@pytest.mark.asyncio
async def test_review_processing_is_a_state_not_silence() -> None:
    service, analyst, _, _ = build(lambda a, m: [session(a.id, days_ago=0, status="COMPLETED", available=False)])
    result = await service.home(USER, analyst.id)
    assert result.state == HomeState.REVIEW_PROCESSING and result.review.kind == SessionKind.REVIEW_PROCESSING


@pytest.mark.asyncio
async def test_active_practice_beats_review_ready_and_carries_real_numbers() -> None:
    def sessions(a, m):
        live = session(a.id, days_ago=0, status="ACTIVE", available=False, mode="FOCUSED_PRACTICE", focus="decisions")
        return [live.model_copy(update={"total_questions": 3}), session(a.id, days_ago=0)]

    service, analyst, _, _ = build(sessions)
    result = await service.home(USER, analyst.id)
    assert result.state == HomeState.ACTIVE_PRACTICE and result.review is None
    assert (result.active.question_number, result.active.question_total) == (3, 4)  # a focused practice has four
    assert result.active.practice_focus == "decisions" and result.other_active is None


@pytest.mark.asyncio
async def test_a_full_interview_has_no_invented_total() -> None:
    def sessions(a, m):
        return [session(a.id, days_ago=0, status="ACTIVE", available=False).model_copy(update={"total_questions": 5})]

    service, analyst, _, _ = build(sessions)
    active = (await service.home(USER, analyst.id)).active
    assert active.question_number == 5 and active.question_total is None


# ----------------------------------------------------------------- roles


@pytest.mark.asyncio
async def test_an_unfinished_practice_for_another_role_is_never_hidden() -> None:
    def sessions(a, m):
        return [session(a.id, days_ago=0, status="ACTIVE", available=False, mode="FOCUSED_PRACTICE", focus="decisions")]

    service, analyst, manager, _ = build(sessions)
    result = await service.home(USER, manager.id)
    assert result.selected.role_profile_id == manager.id
    assert result.state == HomeState.FIRST_PRACTICE  # the selected role's own next step
    assert result.active is None and result.other_active.role_profile_id == analyst.id


@pytest.mark.asyncio
async def test_switching_role_changes_everything_and_mixes_nothing() -> None:
    def sessions(a, m):
        return [session(a.id, days_ago=6), session(a.id, days_ago=9), session(m.id, days_ago=8)]

    service, analyst, manager, _ = build(sessions)
    first = await service.home(USER, analyst.id)
    second = await service.home(USER, manager.id)
    assert (first.progress.practice_count, second.progress.practice_count) == (2, 1)
    assert first.state == HomeState.RECOMMENDED_NEXT and second.state == HomeState.EARLY_BASELINE
    assert {item.session_id for item in second.activity}.isdisjoint({item.session_id for item in first.activity})


@pytest.mark.asyncio
async def test_default_role_is_the_role_of_the_newest_practice() -> None:
    service, _, manager, _ = build(lambda a, m: [session(m.id, days_ago=1), session(a.id, days_ago=4)])
    assert (await service.home(USER)).selected.role_profile_id == manager.id


@pytest.mark.asyncio
async def test_a_role_that_is_not_yours_is_refused() -> None:
    service, _, _, _ = build(lambda a, m: [])
    with pytest.raises(RoleProfileNotFoundForUser):
        await service.home(USER, uuid4())
    theirs = profile(OTHER, "Data Analyst")
    service._roles.by_user[OTHER] = [(theirs, frozenset({theirs.id}))]
    with pytest.raises(RoleProfileNotFoundForUser):
        await service.home(USER, theirs.id)  # another person's role, by exact id


@pytest.mark.asyncio
async def test_another_person_sees_only_their_own_data() -> None:
    service, _, _, _ = build(lambda a, m: [session(a.id, days_ago=1)])
    theirs = profile(OTHER, "Designer")
    service._roles.by_user[OTHER] = [(theirs, frozenset({theirs.id}))]
    service._dashboard.by_user[OTHER] = []
    result = await service.home(OTHER)
    assert [r.target_role for r in result.roles] == ["Designer"] and result.progress.practice_count == 0
    assert result.active is None and result.other_active is None and result.activity == []


# ----------------------------------------------------------------- summaries and activity


@pytest.mark.asyncio
async def test_since_last_practice_comes_from_the_progress_analytics() -> None:
    service, analyst, _, dashboard = build(lambda a, m: [session(a.id, days_ago=2), session(a.id, days_ago=8)])
    newest, oldest = dashboard.by_user[USER]
    service._progress._reports.reports.update({
        newest.id: report(role=(90, 95), moments=[moment(SessionMomentType.OWNERSHIP_CLARIFICATION, uuid4())]),
        oldest.id: report(role=(10, 15)),
    })
    result = await service.home(USER, analyst.id)
    assert result.progress.stage.value == "COMPARABLE"
    assert (result.progress.insights[0].dimension, result.progress.insights[0].trend.value) == ("role_understanding", "MORE")


@pytest.mark.asyncio
async def test_map_and_stories_summaries_are_real_counts() -> None:
    stories = FakeStories([story("A", ready=True), story("B", ready=True), story("C", ready=False)])
    service, analyst, _, _ = build(lambda a, m: [], readiness=FakeReadiness(missing=2), stories=stories)
    result = await service.home(USER, analyst.id)
    assert (result.map.state, result.map.without_example) == ("READY", 2)
    assert (result.stories.state, result.stories.ready, result.stories.developing) == ("READY", 2, 1)


@pytest.mark.asyncio
async def test_a_failing_part_is_reported_as_unavailable_not_as_zero() -> None:
    service, analyst, _, _ = build(lambda a, m: [], readiness=FakeReadiness(fail=True), stories=FakeStories([], fail=True))
    result = await service.home(USER, analyst.id)
    assert result.map.state == "UNAVAILABLE" and result.map.without_example == 0
    assert result.stories.state == "UNAVAILABLE"
    assert result.state == HomeState.FIRST_PRACTICE  # the core answer still stands


@pytest.mark.asyncio
async def test_a_role_still_being_read_is_preparing() -> None:
    service, analyst, _, _ = build(lambda a, m: [], readiness=FakeReadiness(state=MapState.ROLE_PREPARING))
    assert (await service.home(USER, analyst.id)).map.state == "PREPARING"


@pytest.mark.asyncio
async def test_activity_is_this_roles_practice_plus_story_edits_and_is_short() -> None:
    def sessions(a, m):
        return [session(a.id, days_ago=day) for day in (1, 3, 5, 7)] + [session(m.id, days_ago=0)]

    stories = FakeStories([story("Pricing decision", ready=True, days_ago=2)])
    service, analyst, manager, dashboard = build(sessions, stories=stories)
    activity = (await service.home(USER, analyst.id)).activity
    assert len(activity) == ACTIVITY_LIMIT
    assert [item.at for item in activity] == sorted((item.at for item in activity), reverse=True)
    assert any(item.kind == "STORY" for item in activity)
    manager_sessions = {s.id for s in dashboard.by_user[USER] if s.role_profile_id == manager.id}
    assert not manager_sessions & {item.session_id for item in activity}


@pytest.mark.asyncio
async def test_home_reads_sessions_once() -> None:
    service, analyst, _, dashboard = build(lambda a, m: [session(a.id, days_ago=1)])
    await service.home(USER, analyst.id)
    assert dashboard.calls == 1


@pytest.mark.asyncio
async def test_an_unexpected_error_in_a_part_is_a_bug_that_surfaces_not_a_quiet_downgrade() -> None:
    service, analyst, _, _ = build(lambda a, m: [], readiness=FakeReadiness(fail=ValueError("bug")))
    with pytest.raises(ValueError):
        await service.home(USER, analyst.id)


@pytest.mark.asyncio
async def test_an_unbound_legacy_practice_never_drives_the_review_headline() -> None:
    def sessions(a, m):
        legacy = session(a.id, days_ago=0).model_copy(update={"role_profile_id": None, "target_role": "Data Analyst"})
        return [legacy]

    service, analyst, _, _ = build(sessions)
    result = await service.home(USER, analyst.id)
    assert result.state == HomeState.FIRST_PRACTICE and result.review is None and result.activity == []  # agrees with Progress


@pytest.mark.asyncio
async def test_an_unbound_legacy_unfinished_practice_is_still_found() -> None:
    def sessions(a, m):
        return [session(a.id, days_ago=0, status="ACTIVE", available=False).model_copy(update={"role_profile_id": None, "target_role": "Data Analyst"})]

    service, analyst, _, _ = build(sessions)
    assert (await service.home(USER, analyst.id)).state == HomeState.ACTIVE_PRACTICE


@pytest.mark.asyncio
async def test_a_practice_never_begun_does_not_hide_a_review_that_finished_after_it() -> None:
    def sessions(a, m):
        unbegun = session(a.id, days_ago=5, status="READY", available=False).model_copy(update={"updated_at": NOW - timedelta(days=5)})
        return [session(a.id, days_ago=0), unbegun]

    service, analyst, _, _ = build(sessions)
    assert (await service.home(USER, analyst.id)).state == HomeState.REVIEW_READY


@pytest.mark.asyncio
async def test_a_newer_unbegun_practice_is_offered_to_begin() -> None:
    def sessions(a, m):
        return [session(a.id, days_ago=0, status="READY", available=False), session(a.id, days_ago=4)]

    service, analyst, _, _ = build(sessions)
    result = await service.home(USER, analyst.id)
    assert result.state == HomeState.ACTIVE_PRACTICE and result.active.kind == SessionKind.READY


@pytest.mark.asyncio
async def test_an_unrelated_session_does_not_hide_an_older_review_still_processing() -> None:
    def sessions(a, m):
        return [session(a.id, days_ago=0, status="CREATED", available=False), session(a.id, days_ago=1, status="COMPLETED", available=False)]

    service, analyst, _, _ = build(sessions)
    assert (await service.home(USER, analyst.id)).state == HomeState.REVIEW_PROCESSING


# ----------------------------------------------------------------- an interview coming up


class FakeInterviews:
    def __init__(self, rows=(), fail=False):
        self.rows, self.fail, self.seen = list(rows), fail, []

    async def list_for_user(self, user_id):
        self.seen.append(user_id)
        if self.fail:
            from app.interview_event_repository import InterviewEventsUnavailable

            raise InterviewEventsUnavailable("down")
        return [row for row in self.rows if row.user_id == user_id]


def event(role, *, hours, user=USER, round_kind="TECHNICAL"):
    from app.interview_event_models import InterviewEventRecord

    return InterviewEventRecord(id=uuid4(), user_id=user, role_profile_id=role.id, scheduled_for=NOW + timedelta(hours=hours),
                                round_kind=round_kind, company_label="Acme", created_at=NOW, updated_at=NOW)


def with_interviews(interviews):
    service, analyst, manager, dashboard = build(lambda a, m: [])
    service._interviews = interviews
    return service, analyst, manager


@pytest.mark.asyncio
async def test_an_interview_within_48_hours_is_surfaced_and_the_state_is_untouched() -> None:
    fake = FakeInterviews()
    service, analyst, _ = with_interviews(fake)
    fake.rows = [event(analyst, hours=20)]
    result = await service.home(USER, analyst.id, now=NOW)
    up = result.upcoming_interview
    assert (up.event_id, up.role_profile_id, up.target_role, up.round_kind.value, up.company_label) == (
        fake.rows[0].id, analyst.id, "Data Analyst", "TECHNICAL", "Acme")
    assert result.state == HomeState.FIRST_PRACTICE


@pytest.mark.asyncio
async def test_interviews_further_out_or_already_past_are_not_surfaced() -> None:
    fake = FakeInterviews()
    service, analyst, _ = with_interviews(fake)
    fake.rows = [event(analyst, hours=49), event(analyst, hours=-1)]
    assert (await service.home(USER, analyst.id, now=NOW)).upcoming_interview is None


@pytest.mark.asyncio
async def test_the_soonest_interview_across_all_roles_is_the_one_surfaced() -> None:
    fake = FakeInterviews()
    service, analyst, manager = with_interviews(fake)
    fake.rows = [event(analyst, hours=30), event(manager, hours=5), event(analyst, hours=60)]
    up = (await service.home(USER, analyst.id, now=NOW)).upcoming_interview  # the selected role is the analyst
    assert (up.role_profile_id, up.target_role, up.event_id) == (manager.id, "Product Manager", fake.rows[1].id)


@pytest.mark.asyncio
async def test_an_interview_outage_hides_the_nudge_never_home() -> None:
    service, analyst, _ = with_interviews(FakeInterviews(fail=True))
    result = await service.home(USER, analyst.id, now=NOW)
    assert result.upcoming_interview is None and result.state == HomeState.FIRST_PRACTICE


@pytest.mark.asyncio
async def test_another_persons_interview_never_appears() -> None:
    fake = FakeInterviews()
    service, analyst, _ = with_interviews(fake)
    theirs = profile(OTHER, "Designer")
    fake.rows = [event(theirs, hours=2, user=OTHER), event(analyst, hours=2, user=OTHER)]
    assert (await service.home(USER, analyst.id, now=NOW)).upcoming_interview is None
    assert fake.seen == [USER]


@pytest.mark.asyncio
async def test_memory_repository_lists_only_this_persons_interviews() -> None:
    from app.interview_event_models import InterviewEventCreate
    from app.interview_event_repository import MemoryInterviewEventRepository

    repo = MemoryInterviewEventRepository()
    mine = await repo.create(USER, uuid4(), InterviewEventCreate(scheduled_for=NOW + timedelta(hours=3)))
    await repo.create(OTHER, uuid4(), InterviewEventCreate(scheduled_for=NOW + timedelta(hours=1)))
    assert [row.id for row in await repo.list_for_user(USER)] == [mine.id]
