from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.report_models import ReportResponse
from app.report_service import ReportService, is_shorter_conversation
from app.schemas import SessionEventRead
from tests.test_report import RESULT, SESSION, USER, FakeReportRepository, session


class TurnRepo(FakeReportRepository):
    def __init__(self, turns, **kw):
        super().__init__(**kw)
        self.turns = turns

    async def count_candidate_turns(self, session_id, user_id):
        return self.turns


def end_event(elapsed):
    return SessionEventRead(
        id=uuid4(), session_id=SESSION, user_id=USER, event_type="SESSION_END_REQUESTED",
        payload={"elapsed_seconds": elapsed}, created_at=datetime.now(UTC),
    )


def rule(**kw):
    base = dict(answered_turns=6, duration_seconds=600, total_budget_seconds=1200, events=[], min_answers=4, min_seconds=180)
    return is_shorter_conversation(**{**base, **kw})


def test_rule_boundaries():
    assert not rule()
    assert rule(answered_turns=3)
    assert not rule(answered_turns=4)
    assert rule(answered_turns=0)
    assert rule(duration_seconds=179)
    assert not rule(duration_seconds=180)
    assert not rule(answered_turns=None)
    assert rule(events=[end_event(719)])
    assert not rule(events=[end_event(720)])


@pytest.mark.asyncio
async def test_flag_not_set_for_full_conversation():
    report = await ReportService(TurnRepo(6, result=RESULT, events=[end_event(1100)])).get_report(SESSION, USER)
    assert report.shorter_conversation is False


@pytest.mark.asyncio
async def test_flag_set_for_few_turns_and_early_end():
    few = await ReportService(TurnRepo(2, result=RESULT)).get_report(SESSION, USER)
    assert few.shorter_conversation is True
    early = await ReportService(TurnRepo(6, result=RESULT, events=[end_event(200)])).get_report(SESSION, USER)
    assert early.shorter_conversation is True


@pytest.mark.asyncio
async def test_zero_turns_without_claims_still_valid():
    now = datetime.now(UTC)
    short = session().model_copy(update={"started_at": now - timedelta(seconds=20), "elapsed_seconds": 20})
    result = {**RESULT, "role_readiness_low": None, "role_readiness_high": None,
              "interview_readiness_low": None, "interview_readiness_high": None, "assessment_confidence": 0.0}
    report = await ReportService(TurnRepo(0, current=short, result=result, events=[end_event(20)])).get_report(SESSION, USER)
    assert report.shorter_conversation is True
    assert report.role_readiness.low is None
    assert report.claims_audit.held == []
    ReportResponse.model_validate(report.model_dump())


def test_model_default():
    fields = ReportResponse.model_fields
    assert fields["shorter_conversation"].default is False
