"""B5: report/aggregator trust boundaries. Behavioural tests, no model calls."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.claims_models import ClaimStatus
from app.final_assessment_aggregator import FinalAssessmentAggregator
from app.report_service import ReportService
from app.specialist_assessor_models import (
    AssessmentEvidence,
    AssessorType,
    DomainAssessment,
    SignalStrength,
    SpecialistAssessmentBundle,
    SpecialistAssessmentOutput,
    SpecialistStatus,
    StoredSpecialistAssessment,
)
from tests.test_report import RESULT, SESSION, TURN, USER, FakeReportRepository, claim, default_turns, verified_specialists

QUOTE = "I only supported the dashboard filters."


def strong_row(kind=AssessorType.TECHNICAL, *, turn=TURN, quote=QUOTE, nested_turn=None, depth=0):
    domain = DomainAssessment(
        domain="SQL", status=SpecialistStatus.COMPLETE, signal_strength=SignalStrength.STRONG, confidence=.9,
        evidence_turn_ids=[nested_turn or turn], evidence_quotes=[AssessmentEvidence(turn_id=nested_turn or turn, quote=quote)],
        reason_summary="Concrete trade-off.",
    )
    out = SpecialistAssessmentOutput(
        assessor_type=kind, status=SpecialistStatus.COMPLETE, dimensions=[domain], signal_strength=SignalStrength.STRONG,
        confidence=.9, evidence_turn_ids=[turn], evidence_quotes=[AssessmentEvidence(turn_id=turn, quote=quote)],
        reason_summary="Strong.",
    )
    return {"assessor_type": kind.value, "status": "COMPLETE", "result_json": out.model_dump(mode="json")}


def specialists_with(row):
    return [row] + [r for r in verified_specialists() if r["assessor_type"] != row["assessor_type"]]


async def report(**kw):
    return await ReportService(FakeReportRepository(result=RESULT, **kw)).get_report(SESSION, USER)


@pytest.mark.asyncio
async def test_verified_report_preserved_with_numbers_and_skills():
    r = await report(specialists=specialists_with(strong_row()))
    assert r.role_readiness.low == 61 and r.role_readiness.high == 68
    assert r.skill_assessments and r.skill_assessments[0].evidence[0].quote == QUOTE
    assert r.root_cause == "TECHNICAL_DEPTH"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    dict(turn=uuid4()),                                    # fabricated / nonexistent turn
    dict(quote="I architected the entire platform solo."),  # quote not in turn
])
async def test_unverifiable_specialist_makes_result_unavailable_not_weak(bad):
    r = await report(specialists=specialists_with(strong_row(**bad)))
    assert r.role_readiness.low is None and r.role_readiness.high is None
    assert r.interview_readiness.low is None
    assert r.skill_assessments == []                        # evidence not exposed as trusted
    assert r.root_cause == "UNAVAILABLE"                    # no weakness diagnosis from unknown data
    assert r.role_readiness.label == "Not enough to say yet"


@pytest.mark.asyncio
async def test_interviewer_turn_is_not_candidate_evidence():
    iv = uuid4()
    turns = default_turns() + [{"id": iv, "speaker": "INTERVIEWER", "text": QUOTE, "turn_index": 1}]
    r = await report(turns=turns, specialists=specialists_with(strong_row(turn=iv)))
    assert r.role_readiness.low is None and r.skill_assessments == []


@pytest.mark.asyncio
async def test_nested_fabricated_evidence_is_caught():
    r = await report(specialists=specialists_with(strong_row(nested_turn=uuid4())))
    assert r.role_readiness.low is None


@pytest.mark.asyncio
async def test_legacy_result_without_specialist_rows_is_unavailable_and_non_destructive():
    repo = FakeReportRepository(result=RESULT, specialists=[])
    r = await ReportService(repo).get_report(SESSION, USER)
    assert r.role_readiness.low is None and r.interview_readiness.high is None
    assert repo.result == RESULT and repo.turn_rows == default_turns()   # nothing mutated, transcript preserved
    # recovery stays possible: once provenance exists the same stored result reads normally
    repo.specialists = verified_specialists()
    assert (await ReportService(repo).get_report(SESSION, USER)).role_readiness.low == 61


@pytest.mark.asyncio
async def test_unknown_turn_source_fails_closed():
    r = await report(turns=None)                            # turns cannot be loaded
    assert r.role_readiness.low is None


@pytest.mark.asyncio
async def test_claim_evidence_must_resolve_to_candidate_turn():
    walked = claim(ClaimStatus.WALKED_BACK)
    rows = [
        {"claim_id": str(walked.id), "turn_id": str(TURN), "quote_text": QUOTE, "evidence_direction": "WEAKENS", "strength": "STRONG"},
        {"claim_id": str(walked.id), "turn_id": str(uuid4()), "quote_text": "invented", "evidence_direction": "SUPPORTS", "strength": "STRONG"},
        {"claim_id": str(walked.id), "turn_id": str(TURN), "quote_text": "never said this", "evidence_direction": "SUPPORTS", "strength": "STRONG"},
    ]
    r = await report(claims=[walked], evidence=rows)
    quotes = [e.quote for e in r.claims_audit.walked_back[0].evidence]
    assert quotes == [QUOTE]
    assert [m.quote for m in r.session_moments if m.quote] == [QUOTE]


# ---- aggregator: unknown is neither strength nor weakness
class _Bundle:
    def __init__(self, **rows):
        self.technical = rows.get("technical")
        self.behaviour = rows.get("behaviour")
        self.claims = rows.get("claims")


def stored(kind, strength, status=SpecialistStatus.COMPLETE):
    row = strong_row(kind)["result_json"]
    row["signal_strength"] = strength.value
    return StoredSpecialistAssessment.model_construct(
        id=uuid4(), session_id=SESSION, assessor_type=kind, status=status,
        result_json=SpecialistAssessmentOutput.model_validate(row), prompt_version="v1", rubric_version="v1",
    )


def test_missing_input_is_excluded_not_scored_as_weakness():
    agg = FinalAssessmentAggregator()
    full = agg.aggregate(_Bundle(technical=stored(AssessorType.TECHNICAL, SignalStrength.STRONG),
                                 behaviour=stored(AssessorType.BEHAVIOUR, SignalStrength.STRONG),
                                 claims=stored(AssessorType.CLAIMS, SignalStrength.STRONG)))
    partial = agg.aggregate(_Bundle(technical=stored(AssessorType.TECHNICAL, SignalStrength.STRONG)))
    # With claims/behaviour unknown, the technical-only role score is not dragged down.
    assert partial.role_readiness_internal == full.role_readiness_internal == 82
    assert partial.overall_signal_confidence < full.overall_signal_confidence
    assert partial.availability_status == "LIMITED_SIGNAL"


def test_missing_input_does_not_raise_either():
    agg = FinalAssessmentAggregator()
    base = agg.aggregate(_Bundle(technical=stored(AssessorType.TECHNICAL, SignalStrength.WEAK),
                                 claims=stored(AssessorType.CLAIMS, SignalStrength.WEAK)))
    assert base.role_readiness_internal == 40
    more_unknown = agg.aggregate(_Bundle(technical=stored(AssessorType.TECHNICAL, SignalStrength.WEAK)))
    assert more_unknown.role_readiness_internal == 40       # unknown claims neither lowers nor raises


@pytest.mark.asyncio
async def test_string_turn_ids_from_postgrest_still_verify():
    rows = [{**t, "id": str(t["id"])} for t in default_turns()]
    r = await report(turns=rows, specialists=specialists_with(strong_row()))
    assert r.role_readiness.low == 61 and r.skill_assessments


@pytest.mark.asyncio
async def test_claim_evidence_with_no_turn_and_no_document_is_dropped():
    walked = claim(ClaimStatus.WALKED_BACK)
    rows = [{"claim_id": str(walked.id), "quote_text": "FABRICATED", "evidence_direction": "SUPPORTS", "strength": "STRONG"}]
    r = await report(claims=[walked], evidence=rows)
    assert r.claims_audit.walked_back[0].evidence == []
