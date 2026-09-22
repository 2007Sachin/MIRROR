"""Home page summary: derived from the report, never invented."""

import pytest

from app.claims_models import ClaimStatus
from app.dashboard_models import DashboardDiagnostic, DashboardResponse
from app.dashboard_summary import (
    COULD_GO_FURTHER,
    NEEDS_ATTENTION,
    NOT_ENOUGH,
    STRONG,
    DashboardSummaryService,
    build_latest_review,
    review_counts,
    review_improvements,
)
from app.report_service import ReportService
from tests.test_report import RESULT, SESSION, USER, FakeReportRepository, claim


async def make_report(claims=None, result=None):
    repo = FakeReportRepository(result=result or RESULT, claims=claims or [])
    return await ReportService(repo).get_report(SESSION, USER)


@pytest.mark.asyncio
async def test_counts_come_from_the_claim_groups() -> None:
    report = await make_report([
        claim(ClaimStatus.CORROBORATED), claim(ClaimStatus.CORROBORATED),
        claim(ClaimStatus.PARTIALLY_HELD), claim(ClaimStatus.INSUFFICIENT_EVIDENCE), claim(ClaimStatus.CONTRADICTED),
    ])
    counts = review_counts(report)
    assert (counts.clear, counts.could_be_stronger, counts.worth_revisiting) == (2, 2, 1)


@pytest.mark.asyncio
async def test_no_explored_areas_means_no_counts_not_zeros() -> None:
    report = await make_report([claim(ClaimStatus.UNVERIFIED)])
    assert review_counts(report) is None


@pytest.mark.asyncio
async def test_dimensions_use_plain_labels_and_never_numbers() -> None:
    report = await make_report([claim(ClaimStatus.CORROBORATED), claim(ClaimStatus.CORROBORATED)],
                               {**RESULT, "role_readiness_low": 85, "role_readiness_high": 95})
    dims = {d.key: d for d in build_latest_review(SESSION, report).dimensions}
    assert dims["role_understanding"].state == STRONG
    assert dims["examples"].state == STRONG
    for d in dims.values():
        assert not any(ch.isdigit() for ch in d.state + d.note)


@pytest.mark.asyncio
async def test_missing_signal_says_not_enough_to_say_yet() -> None:
    report = await make_report([], {**RESULT, "role_readiness_low": None, "role_readiness_high": None})
    dims = {d.key: d for d in build_latest_review(SESSION, report).dimensions}
    assert dims["role_understanding"].state == NOT_ENOUGH
    assert dims["examples"].state == NOT_ENOUGH and dims["depth"].state == NOT_ENOUGH


@pytest.mark.asyncio
async def test_impact_follows_the_growth_area() -> None:
    report = await make_report([], {**RESULT, "root_cause_code": "OWNERSHIP_SPECIFICITY"})
    assert {d.key: d.state for d in build_latest_review(SESSION, report).dimensions}["impact"] == NEEDS_ATTENTION
    report = await make_report([], {**RESULT, "root_cause_code": "OUTCOME_EVIDENCE"})
    assert {d.key: d.state for d in build_latest_review(SESSION, report).dimensions}["impact"] == COULD_GO_FURTHER


@pytest.mark.asyncio
async def test_improvements_are_at_most_three_and_use_friendly_titles() -> None:
    report = await make_report([claim(ClaimStatus.PARTIALLY_HELD), claim(ClaimStatus.CONTRADICTED), claim(ClaimStatus.INSUFFICIENT_EVIDENCE), claim(ClaimStatus.PARTIALLY_HELD)])
    items = review_improvements(report)
    assert len(items) == 3
    banned = ("claim", "evidence", "verdict", "diagnostic", "weak", "gap")
    for item in items:
        assert not any(word in (item.title + item.note).lower() for word in banned), item
    assert items[0].title == "Go a little deeper"  # the report's own growth area comes first


class _Dashboard:
    def __init__(self, sessions):
        self._sessions = sessions

    async def workspace(self, user_id):
        return DashboardResponse(current=self._sessions[0] if self._sessions else None, previous=self._sessions[1:])


def _row(status, available):
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    return DashboardDiagnostic(
        id=SESSION, target_role="Data Analyst", company=None, interview_status=status, phase="COMPLETE",
        created_at=now, updated_at=now, completed_at=now, assessment=None, diagnostic_available=available,
    )


@pytest.mark.asyncio
async def test_summary_uses_the_latest_finished_review() -> None:
    repo = FakeReportRepository(result=RESULT, claims=[claim(ClaimStatus.CORROBORATED)])
    service = DashboardSummaryService(_Dashboard([_row("COMPLETED", True)]), ReportService(repo))
    latest = (await service.summary(USER)).latest_review
    assert latest is not None and latest.target_role == "Data Analyst"


@pytest.mark.asyncio
async def test_no_finished_review_means_no_summary() -> None:
    service = DashboardSummaryService(_Dashboard([_row("ASSESSING", False)]), ReportService(FakeReportRepository(result=RESULT)))
    assert (await service.summary(USER)).latest_review is None
    empty = DashboardSummaryService(_Dashboard([]), ReportService(FakeReportRepository(result=RESULT)))
    assert (await empty.summary(USER)).latest_review is None


@pytest.mark.asyncio
async def test_an_unreadable_review_does_not_fail_the_home_page() -> None:
    repo = FakeReportRepository(result=None)  # the report says "not ready"
    service = DashboardSummaryService(_Dashboard([_row("COMPLETED", True)]), ReportService(repo))
    assert (await service.summary(USER)).latest_review is None
