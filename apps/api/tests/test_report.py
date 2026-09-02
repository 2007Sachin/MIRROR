from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.claims_models import ClaimRead, ClaimSource, ClaimStatus, ClaimType, VerificationPriority
from app.report_service import ReportAssessmentIncomplete, ReportNotFound, ReportService
from app.schemas import Phase, SessionRead, SessionStatus
from app.specialist_assessor_models import (
    AssessorType,
    DomainAssessment,
    SignalStrength,
    SpecialistAssessmentOutput,
    SpecialistStatus,
)


USER = uuid4()
SESSION = uuid4()
TURN = uuid4()


def session(user=USER, status=SessionStatus.COMPLETED):
    now = datetime.now(UTC)
    return SessionRead(
        id=SESSION, user_id=user, target_role="Data Analyst", jd_text="", status=status,
        phase=Phase.COMPLETE, completion_pct=100, synthetic=False,
        started_at=now - timedelta(minutes=10), completed_at=now, created_at=now,
        updated_at=now, phase_started_at=now, phase_time_budget_seconds=180,
        total_time_budget_seconds=1200, elapsed_seconds=600, current_probe_count=0,
        total_questions=4, recovery_count=0,
    )


def claim(status):
    now = datetime.now(UTC)
    return ClaimRead(
        id=uuid4(), user_id=USER, session_id=SESSION, claim_text="Used SQL to improve reporting",
        claim_type=ClaimType.SKILL, source=ClaimSource.RESUME, source_document_id=None,
        source_reference="experience", confidence=.8, verification_priority=VerificationPriority.HIGH,
        synthetic=False, status=status, created_at=now, updated_at=now,
    )


class FakeReportRepository:
    def __init__(self, *, current=session(), result=None, claims=None, evidence=None, specialists=None, events=None):
        self.current = current
        self.result = result
        self.claims = claims or []
        self.evidence = evidence or []
        self.specialists = specialists or []
        self.events = events or []

    async def get_session(self, session_id, user_id):
        return self.current if self.current and self.current.id == session_id and self.current.user_id == user_id else None

    async def get_result(self, session_id, user_id):
        return self.result

    async def list_claims(self, session_id, user_id):
        return [item for item in self.claims if item.user_id == user_id]

    async def list_evidence(self, claim_ids, user_id):
        return self.evidence

    async def list_specialists(self, session_id, user_id):
        return self.specialists

    async def list_events(self, session_id, user_id):
        return self.events


RESULT = {
    "role_readiness_low": 61, "role_readiness_high": 68,
    "interview_readiness_low": 54, "interview_readiness_high": 63,
    "verdict_code": "NEAR_READY", "root_cause_code": "TECHNICAL_DEPTH",
    "summary": "Technical fundamentals are credible.", "confidence_note": "Evidence was sufficient.",
    "assessment_confidence": .8, "model": "secret-model", "prompt_version": "secret-prompt",
}


@pytest.mark.asyncio
async def test_owner_access_and_incomplete_assessment():
    service = ReportService(FakeReportRepository(result=RESULT))
    with pytest.raises(ReportNotFound):
        await service.get_report(SESSION, uuid4())
    with pytest.raises(ReportAssessmentIncomplete):
        await ReportService(FakeReportRepository(current=session(status=SessionStatus.ACTIVE), result=RESULT)).get_report(SESSION, USER)


@pytest.mark.asyncio
async def test_claim_grouping_and_walked_back_evidence():
    walked = claim(ClaimStatus.WALKED_BACK)
    repo = FakeReportRepository(result=RESULT, claims=[claim(ClaimStatus.CORROBORATED), walked], evidence=[{
        "claim_id": str(walked.id), "turn_id": str(TURN), "quote_text": "I only supported the dashboard filters.",
        "evidence_direction": "WEAKENS", "strength": "MODERATE",
    }])
    report = await ReportService(repo).get_report(SESSION, USER)
    assert len(report.claims_audit.held) == 1
    assert report.claims_audit.walked_back[0].evidence[0].turn_id == TURN
    assert "model" not in report.model_dump_json()
    assert "prompt" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_not_enough_signal_has_no_fake_range():
    result = {**RESULT, "role_readiness_low": None, "role_readiness_high": None, "assessment_confidence": 0.2}
    report = await ReportService(FakeReportRepository(result=result)).get_report(SESSION, USER)
    assert report.role_readiness.low is None
    assert report.role_readiness.high is None
    assert report.role_readiness.label == "Not enough signal"


@pytest.mark.asyncio
async def test_skill_assessment_and_schema_are_candidate_safe():
    output = SpecialistAssessmentOutput(
        assessor_type=AssessorType.TECHNICAL, status=SpecialistStatus.COMPLETE,
        dimensions=[DomainAssessment(domain="SQL", status=SpecialistStatus.COMPLETE,
            signal_strength=SignalStrength.STRONG, confidence=.9, evidence_turn_ids=[TURN],
            reason_summary="Explained a concrete trade-off.")], signal_strength=SignalStrength.STRONG,
        confidence=.9, evidence_turn_ids=[TURN], reason_summary="Strong evidence.",
    )
    report = await ReportService(FakeReportRepository(result=RESULT, specialists=[{"assessor_type": "TECHNICAL", "result_json": output.model_dump(mode="json")}])).get_report(SESSION, USER)
    assert report.skill_assessments[0].skill == "SQL"
    assert set(report.model_dump()) == {"session", "verdict", "role_readiness", "interview_readiness", "claims_audit", "skill_assessments", "session_moments", "root_cause", "trust_and_limitations", "prescription"}

