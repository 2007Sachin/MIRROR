"""Progress: movement is only reported when two finished practices actually show it."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.claims_models import ClaimStatus
from app.copy_guard import find_banned
from app.dashboard_models import DashboardDiagnostic, DashboardResponse
from app.dashboard_summary import build_latest_review
from app.progress_summary import (
    IMPROVING,
    NEEDS_MORE,
    STEADY,
    ProgressService,
    build_changes,
    build_dimensions,
    build_headline,
)
from app.report_service import ReportNotFound, ReportService
from tests.test_report import RESULT, SESSION, USER, FakeReportRepository, claim

ROLE = "Data Analyst"


async def review(session_id, claims=None, result=None):
    """A finished review, built the same way the Home page builds one."""
    repo = FakeReportRepository(result=result or RESULT, claims=claims or [])
    report = await ReportService(repo).get_report(SESSION, USER)
    return build_latest_review(session_id, report), report


def row(session_id, *, days_ago=0, role=ROLE, status="COMPLETED", available=True):
    now = datetime.now(UTC) - timedelta(days=days_ago)
    return DashboardDiagnostic(
        id=session_id, target_role=role, company=None, interview_status=status,
        phase="COMPLETE", created_at=now, updated_at=now, completed_at=now,
        assessment=None, diagnostic_available=available,
    )


class FakeDashboard:
    def __init__(self, rows):
        self._rows = rows

    async def workspace(self, user_id):
        return DashboardResponse(current=self._rows[0] if self._rows else None, previous=self._rows[1:])


class FakeReports:
    """Reports keyed by session, so two practices can differ from each other."""

    def __init__(self, reports):
        self._reports = reports

    async def get_report(self, session_id, user_id):
        if session_id not in self._reports:
            raise ReportNotFound
        return self._reports[session_id]


# ----------------------------------------------------------------- pure derivations


@pytest.mark.asyncio
async def test_one_practice_reports_no_direction_at_all() -> None:
    latest, report = await review(uuid4(), [claim(ClaimStatus.CORROBORATED)])
    trends = build_dimensions([latest], report)
    assert trends and all(trend.direction is None for trend in trends)
    assert build_changes(trends) == []


@pytest.mark.asyncio
async def test_one_practice_says_to_come_back_rather_than_claiming_movement() -> None:
    latest, report = await review(uuid4())
    headline = build_headline([latest], build_dimensions([latest], report))
    assert "another practice" in headline.body


@pytest.mark.asyncio
async def test_direction_appears_once_two_practices_can_be_compared() -> None:
    better, report = await review(uuid4(), [claim(ClaimStatus.CORROBORATED), claim(ClaimStatus.CORROBORATED)])
    worse, _ = await review(uuid4(), [claim(ClaimStatus.CONTRADICTED), claim(ClaimStatus.CONTRADICTED)])
    trends = {trend.key: trend for trend in build_dimensions([better, worse], report)}
    assert trends["examples"].direction == IMPROVING
    trends = {trend.key: trend for trend in build_dimensions([worse, better], report)}
    assert trends["examples"].direction == NEEDS_MORE


@pytest.mark.asyncio
async def test_an_area_with_too_little_to_say_never_gets_a_direction() -> None:
    quiet, report = await review(uuid4(), [], {**RESULT, "role_readiness_low": None, "role_readiness_high": None})
    other, _ = await review(uuid4(), [claim(ClaimStatus.CORROBORATED)])
    trends = {trend.key: trend for trend in build_dimensions([quiet, other], report)}
    assert trends["role_understanding"].direction is None


@pytest.mark.asyncio
async def test_unchanged_areas_read_as_steady_and_produce_no_change_line() -> None:
    first, report = await review(uuid4(), [claim(ClaimStatus.CORROBORATED)])
    second, _ = await review(uuid4(), [claim(ClaimStatus.CORROBORATED)])
    trends = build_dimensions([first, second], report)
    assert {trend.direction for trend in trends if trend.direction} == {STEADY}
    assert build_changes(trends) == []


@pytest.mark.asyncio
async def test_changes_are_capped_and_stay_in_plain_words() -> None:
    better, report = await review(uuid4(), [claim(ClaimStatus.CORROBORATED), claim(ClaimStatus.CORROBORATED)])
    worse, _ = await review(uuid4(), [claim(ClaimStatus.CONTRADICTED)])
    changes = build_changes(build_dimensions([better, worse], report))
    assert len(changes) <= 3
    for change in changes:
        assert not find_banned(change.text), change.text


@pytest.mark.asyncio
async def test_excerpts_only_ever_carry_the_reports_own_words() -> None:
    latest, report = await review(uuid4(), [claim(ClaimStatus.CORROBORATED)])
    for trend in build_dimensions([latest], report):
        for excerpt in trend.excerpts:
            assert any(excerpt.quote == moment.quote for moment in report.session_moments)


# ----------------------------------------------------------------------- the service


@pytest.mark.asyncio
async def test_no_finished_practice_means_an_empty_view_not_an_error() -> None:
    service = ProgressService(FakeDashboard([]), FakeReports({}))
    result = await service.progress(USER)
    assert result.roles == [] and result.headline is None and result.practices == []

    unfinished = ProgressService(FakeDashboard([row(uuid4(), status="ASSESSING", available=False)]), FakeReports({}))
    assert (await unfinished.progress(USER)).practices == []


@pytest.mark.asyncio
async def test_practices_are_grouped_by_role_and_default_to_the_newest() -> None:
    recent, other = uuid4(), uuid4()
    _, recent_report = await review(recent, [claim(ClaimStatus.CORROBORATED)])
    _, other_report = await review(other, [claim(ClaimStatus.CORROBORATED)])
    service = ProgressService(
        FakeDashboard([row(recent, days_ago=1), row(other, days_ago=9, role="Product Manager")]),
        FakeReports({recent: recent_report, other: other_report}),
    )
    result = await service.progress(USER)
    assert result.role == ROLE
    assert result.roles == [ROLE, "Product Manager"]
    assert [practice.session_id for practice in result.practices] == [recent]

    chosen = await service.progress(USER, "product manager")
    assert chosen.role == "Product Manager"
    assert [practice.session_id for practice in chosen.practices] == [other]


@pytest.mark.asyncio
async def test_two_practices_for_one_role_are_compared_newest_first() -> None:
    newer, older = uuid4(), uuid4()
    _, newer_report = await review(newer, [claim(ClaimStatus.CORROBORATED), claim(ClaimStatus.CORROBORATED)])
    _, older_report = await review(older, [claim(ClaimStatus.CONTRADICTED), claim(ClaimStatus.CONTRADICTED)])
    service = ProgressService(
        FakeDashboard([row(newer, days_ago=1), row(older, days_ago=8)]),
        FakeReports({newer: newer_report, older: older_report}),
    )
    result = await service.progress(USER)
    assert result.comparable_count == 2
    assert [practice.session_id for practice in result.practices] == [newer, older]
    assert {trend.key: trend.direction for trend in result.dimensions}["examples"] == IMPROVING
    assert result.changes and result.headline is not None


@pytest.mark.asyncio
async def test_a_practice_whose_review_cannot_be_read_is_left_out() -> None:
    readable, unreadable = uuid4(), uuid4()
    _, report = await review(readable, [claim(ClaimStatus.CORROBORATED)])
    service = ProgressService(
        FakeDashboard([row(unreadable, days_ago=1), row(readable, days_ago=6)]),
        FakeReports({readable: report}),
    )
    result = await service.progress(USER)
    assert [practice.session_id for practice in result.practices] == [readable]
    assert result.changes == []  # one comparable practice is never a trend


@pytest.mark.asyncio
async def test_nothing_the_page_shows_contains_a_banned_word() -> None:
    newer, older = uuid4(), uuid4()
    _, newer_report = await review(newer, [claim(ClaimStatus.CORROBORATED)])
    _, older_report = await review(older, [claim(ClaimStatus.PARTIALLY_HELD)])
    service = ProgressService(
        FakeDashboard([row(newer, days_ago=1), row(older, days_ago=7)]),
        FakeReports({newer: newer_report, older: older_report}),
    )
    result = await service.progress(USER)
    assert result.headline is not None
    for text in [result.headline.title, result.headline.body, *(change.text for change in result.changes)]:
        assert not find_banned(text), text
