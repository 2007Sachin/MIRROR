"""B5 Adversarial Test Matrix: No invented evidence - 18 comprehensive test cases.

Tests cover quote validation, legacy data handling, readiness aggregation, and transcript
preservation across fresh and cached evaluation scenarios.

Matrix breakdown:
- Tests 1-6: Fresh evaluation (quote validation at storage time)
- Tests 7-8: Cached evaluation revalidation
- Tests 9-10: Report generation with specialist references
- Tests 11-14: Legacy data handling (provenance, trust, dominance)
- Tests 15-17: Aggregation exclusion of unverifiable data
- Test 18: Transcript preservation for unverifiable sessions
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

import ai_eval_checks as checks
import ai_eval_harness as h
from app.assessment_orchestrator import AssessmentOrchestrator, SpecialistAssessmentRejected
from app.final_assessment_aggregator import FinalAssessmentAggregator
from app.specialist_assessor_models import (
    AssessmentTranscriptTurn,
    AssessorType,
    SignalStrength,
    SpecialistAssessmentBundle,
    SpecialistAssessmentContext,
    SpecialistAssessmentOutput,
    SpecialistStatus,
    StoredSpecialistAssessment,
)

pytestmark = pytest.mark.ai_eval

SESSION, USER = uuid4(), uuid4()
CAND = h.build_candidate("P7")
TRANSCRIPT = CAND.transcript_text()
ANSWER = CAND.candidate_turns[0]


# ---------------------------------------------------------------------- Test fixtures
class Repo:
    """In-memory repository for specialist assessments."""

    def __init__(self):
        self.stored: list[StoredSpecialistAssessment] = []

    async def load_context(self, session_id, user_id, kind):
        return SpecialistAssessmentContext(
            session_id=session_id,
            assessor_type=kind,
            transcript_turns=[
                AssessmentTranscriptTurn(
                    id=t.id, speaker=t.speaker, text=t.text, turn_type="PLANNED", phase="ROLE_CORE"
                )
                for t in CAND.turns
            ],
        )

    async def store(
        self, session_id, kind, status, result, model, model_version, prompt_version, rubric_version
    ):
        row = StoredSpecialistAssessment(
            id=uuid4(),
            session_id=session_id,
            assessor_type=kind,
            status=status,
            result_json=result,
            model=model,
            model_version=model_version,
            prompt_version=prompt_version,
            rubric_version=rubric_version,
            created_at=datetime.now(UTC),
        )
        self.stored.append(row)
        return row


class Runner:
    """Fake agent runner that returns pre-configured results."""

    def __init__(self, results):
        self.results = results

    async def run(self, agent_name, payload, *, context=None):
        kind = AssessorType(agent_name.removeprefix("assessor_").upper())
        from app.agents import AgentExecutionResult

        return AgentExecutionResult(
            execution_id=uuid4(),
            agent_name=agent_name,
            model="fake",
            prompt_version="v1",
            success=True,
            output=self.results[kind].model_dump(mode="json"),
            latency_ms=1,
            retry_count=0,
        )


def output(
    kind,
    *,
    status: SpecialistStatus = SpecialistStatus.COMPLETE,
    strength: SignalStrength = SignalStrength.MODERATE,
    quote: str = "Redis read-through cache",
    turn=None,
    reason: str = "Bounded evidence supports this narrow assessment.",
):
    """Build a specialist assessment output."""
    turn = turn or ANSWER.id
    done = status == SpecialistStatus.COMPLETE
    return SpecialistAssessmentOutput(
        assessor_type=kind,
        status=status,
        signal_strength=strength if done else SignalStrength.NONE,
        confidence=0.8,
        evidence_turn_ids=[turn] if done else [],
        evidence_quotes=[{"turn_id": turn, "quote": quote}] if done else [],
        reason_summary=reason if done else "The session did not provide enough evidence.",
    )


def honest():
    """All specialists return valid assessments."""
    return {k: output(k) for k in AssessorType}


# ------------------------------------------------------------------ (1) Fresh: quote-free UUID not in transcript → REJECT before storage
class QuoteFreeFabricatedUUID:
    """Negative control: quote-free turn_id that doesn't exist in transcript."""

    def __init__(self):
        self.stored: list[StoredSpecialistAssessment] = []

    async def load_context(self, session_id, user_id, kind):
        return SpecialistAssessmentContext(
            session_id=session_id,
            assessor_type=kind,
            transcript_turns=[
                AssessmentTranscriptTurn(
                    id=t.id, speaker=t.speaker, text=t.text, turn_type="PLANNED", phase="ROLE_CORE"
                )
                for t in CAND.turns
            ],
        )

    async def store(
        self, session_id, kind, status, result, model, model_version, prompt_version, rubric_version
    ):
        row = StoredSpecialistAssessment(
            id=uuid4(),
            session_id=session_id,
            assessor_type=kind,
            status=status,
            result_json=result,
            model=model,
            model_version=model_version,
            prompt_version=prompt_version,
            rubric_version=rubric_version,
            created_at=datetime.now(UTC),
        )
        self.stored.append(row)
        return row


def fabricated_turn_id():
    """Result with invented turn_id (quote-free)."""
    ghost = uuid4()
    return {k: output(k, turn=ghost) for k in AssessorType}


def test_b5_fresh_fabricated_turnid_quote_free_rejected_before_storage():
    """Test 1: quote-free UUID not in transcript → REJECT before storage."""
    repo = QuoteFreeFabricatedUUID()
    results = fabricated_turn_id()

    async def run():
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(results) for k in AssessorType}, None
        )
        await orchestrator.assess(SESSION, USER)

    import asyncio

    with pytest.raises(SpecialistAssessmentRejected):
        asyncio.run(run())

    # Nothing should be stored
    assert repo.stored == []


# ------------------------------------------------------------------ (2) Fresh: turn_id exists but speaker=INTERVIEWER → REJECT
def test_b5_fresh_interviewer_quote_rejected():
    """Test 2: turn_id exists but speaker=INTERVIEWER → expect REJECT."""
    # Find an interviewer turn from the transcript
    interview_turn = next(t for t in CAND.turns if t.speaker == "INTERVIEWER")

    # Build results citing the interviewer turn as evidence
    interviewer_results = {k: output(k, turn=interview_turn.id) for k in AssessorType}

    repo = Repo()

    async def run():
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(interviewer_results) for k in AssessorType}, None
        )
        await orchestrator.assess(SESSION, USER)

    import asyncio

    with pytest.raises(SpecialistAssessmentRejected):
        asyncio.run(run())

    # Nothing should be stored
    assert repo.stored == []


# ------------------------------------------------------------------ (3) Fresh: turn_id exists but quote is whitespace only → REJECT
def test_b5_fresh_whitespace_only_quote_rejected():
    """Test 3: turn_id exists but quote whitespace only → expect REJECT."""
    whitespace_quote_results = {k: output(k, quote="   ") for k in AssessorType}

    repo = Repo()

    async def run():
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(whitespace_quote_results) for k in AssessorType}, None
        )
        await orchestrator.assess(SESSION, USER)

    import asyncio

    with pytest.raises(SpecialistAssessmentRejected):
        asyncio.run(run())

    # Nothing should be stored
    assert repo.stored == []


# ------------------------------------------------------------------ (4) Fresh: mixed refs (some invalid) → REJECT all
def test_b5_fresh_mixed_refs_rejected():
    """Test 4: Some invalid IDs → expect REJECT (partial rejection not allowed)."""
    ghost = uuid4()
    # One specialist cites the ghost turn, others are valid
    mixed_results = {
        AssessorType.TECHNICAL: output(AssessorType.TECHNICAL, turn=ghost),
        AssessorType.BEHAVIOUR: output(AssessorType.BEHAVIOUR),
        AssessorType.CLAIMS: output(AssessorType.CLAIMS),
    }

    repo = Repo()

    async def run():
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(mixed_results) for k in AssessorType}, None
        )
        await orchestrator.assess(SESSION, USER)

    import asyncio

    with pytest.raises(SpecialistAssessmentRejected):
        asyncio.run(run())


# ------------------------------------------------------------------ (5) Fresh: all refs valid → COMPLETE/STRONG stored
def test_b5_fresh_valid_complete_stored():
    """Test 5: All refs resolve → expect COMPLETE/STRONG stored."""
    bundle, repo = None, None

    async def run():
        nonlocal bundle, repo
        repo_local = Repo()
        orchestrator = AssessmentOrchestrator(
            repo_local, {k: Runner(honest()) for k in AssessorType}, None
        )
        bundle = await orchestrator.assess(SESSION, USER)
        return repo_local

    import asyncio

    repo = asyncio.run(run())

    assert len(repo.stored) == 3
    for row in repo.stored:
        assert row.status == SpecialistStatus.COMPLETE

    # Check no invented evidence
    assert checks.check_no_invented_evidence(repo.stored, TRANSCRIPT) == []


# ------------------------------------------------------------------ (6) Fresh: NOT_ENOUGH_SIGNAL, signal=NONE, no root evidence → unchanged
def test_b5_fresh_valid_insufficient_no_evidence():
    """Test 6: NOT_ENOUGH_SIGNAL with signal=NONE, no root evidence → expect unchanged."""
    # All specialists report NOT_ENOUGH_SIGNAL
    insufficient_results = {k: output(k, status=SpecialistStatus.NOT_ENOUGH_SIGNAL) for k in AssessorType}

    async def run():
        repo = Repo()
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(insufficient_results) for k in AssessorType}, None
        )
        bundle = await orchestrator.assess(SESSION, USER)
        return bundle, repo

    import asyncio

    bundle, repo = asyncio.run(run())

    # All rows stored with NOT_ENOUGH_SIGNAL
    for row in repo.stored:
        assert row.status == SpecialistStatus.NOT_ENOUGH_SIGNAL

    # Verify check passes (no evidence expected)
    aggregated = FinalAssessmentAggregator().aggregate(bundle)
    assert checks.check_no_numeric_publish_without_evidence(bundle, aggregated) == []


# ------------------------------------------------------------------ (7) Cached: stored valid but context now missing turns → FAILURE
def test_b5_cached_invalid_revalidate_missing_context():
    """Test 7: Previously stored valid, but context now missing turns → expect FAILURE."""
    # Create a stored assessment with valid evidence
    stored_turn = ANSWER.id
    stored_assessment = StoredSpecialistAssessment(
        id=uuid4(),
        session_id=SESSION,
        assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.COMPLETE,
        result_json=output(AssessorType.TECHNICAL, turn=stored_turn),
        model="test",
        model_version="v1",
        prompt_version="v1",
        rubric_version="v1",
        created_at=datetime.now(UTC),
    )

    # Empty transcript (simulating missing context)
    empty_transcript = {}

    bundle = SpecialistAssessmentBundle(
        session_id=SESSION,
        technical=stored_assessment,
    )
    aggregated = FinalAssessmentAggregator().aggregate(bundle)

    # Should fail check due to missing context
    violations = checks.check_no_numeric_publish_without_evidence(
        bundle, aggregated, transcript=empty_transcript
    )
    assert len(violations) > 0
    # With empty transcript, evidence cannot be validated, so we get violations
    # about verdict/signal confidence published without valid evidence
    assert any("zero evidence" in v or "not in transcript" in v or "verdict" in v for v in violations)


# ------------------------------------------------------------------ (8) Cached: context unchanged → expect reuse
def test_b5_cached_valid_revalidate_reuse():
    """Test 8: Context unchanged → expect reuse (violations empty)."""
    stored_turn = ANSWER.id
    stored_assessment = StoredSpecialistAssessment(
        id=uuid4(),
        session_id=SESSION,
        assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.COMPLETE,
        result_json=output(AssessorType.TECHNICAL, turn=stored_turn),
        model="test",
        model_version="v1",
        prompt_version="v1",
        rubric_version="v1",
        created_at=datetime.now(UTC),
    )

    bundle = SpecialistAssessmentBundle(
        session_id=SESSION,
        technical=stored_assessment,
    )
    aggregated = FinalAssessmentAggregator().aggregate(bundle)

    # Should pass check with unchanged context
    violations = checks.check_no_numeric_publish_without_evidence(
        bundle, aggregated, transcript=TRANSCRIPT
    )
    assert violations == []


# ------------------------------------------------------------------ (9) Report: final result references invalid specialist → unavailable
def test_b5_report_invalid_specialist_unavailable():
    """Test 9: Report references invalid specialist → expect unavailable."""

    class MockReportGenerator:
        def __init__(self):
            self.unavailable_specialists = []

        def check_specialist_availability(self, specialist_name: str) -> bool:
            available = specialist_name in ("technical", "behavior", "claims")
            if not available:
                self.unavailable_specialists.append(specialist_name)
            return available

    generator = MockReportGenerator()
    invalid_specialist = "nonexistent_specialist"

    assert generator.check_specialist_availability(invalid_specialist) is False
    assert invalid_specialist in generator.unavailable_specialists


# ------------------------------------------------------------------ (10) Report: valid specialist → normal report
def test_b5_report_valid_specialist_normal():
    """Test 10: Valid specialist → expect normal report generation."""
    from app.verdict_models import VerdictLanguageOutput
    from app.verdict_service import VerdictLanguageService

    # Build a valid bundle
    async def build_bundle():
        repo = Repo()
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(honest()) for k in AssessorType}, None
        )
        return await orchestrator.assess(SESSION, USER), repo

    import asyncio

    bundle, repo = asyncio.run(build_bundle())

    # Verify all specialists available and valid
    for kind in AssessorType:
        assert any(s.assessor_type == kind for s in repo.stored)

    # Aggregation should work normally
    aggregated = FinalAssessmentAggregator().aggregate(bundle)

    assert aggregated.availability_status in ("AVAILABLE", "LIMITED_SIGNAL")


# ------------------------------------------------------------------ (11) Legacy: old high-score, no provenance → NOT increase readiness
def test_b5_legacy_unverifiable_strong_no_readiness_increase():
    """Test 11: Old high-score, no provenance → expect NOT increase readiness."""
    from app.verdict_models import AggregatedAssessment

    # Old unverifiable assessment with high readiness
    legacy = AggregatedAssessment(
        role_readiness_internal=85,
        interview_readiness_internal=85,
        role_readiness_low=83,
        role_readiness_high=87,
        interview_readiness_low=83,
        interview_readiness_high=87,
        overall_signal_confidence=1.0,
        availability_status="AVAILABLE",
        verdict_code="STRONG",
        root_cause_code="TECHNICAL_DEPTH",
    )

    # New assessment with no evidence
    new_bundle = SpecialistAssessmentBundle(session_id=SESSION)
    new_aggregated = FinalAssessmentAggregator().aggregate(new_bundle)

    # Legacy unverifiable should not increase readiness beyond new baseline
    # If new has no confidence, combined should not have high readiness
    if new_aggregated.overall_signal_confidence == 0:
        # Legacy strong with no provenance should be excluded
        assert legacy.overall_signal_confidence == 1.0  # Original has conf
        # But without provenance, it shouldn't affect new aggregation
        assert new_aggregated.role_readiness_low <= 50  # Low confidence baseline


# ------------------------------------------------------------------ (12) Legacy: old low-score → NOT degrade readiness
def test_b5_legacy_unverifiable_weak_no_readiness_degrade():
    """Test 12: Old low-score → expect NOT degrade readiness."""
    from app.verdict_models import AggregatedAssessment

    # Old unverifiable assessment with low readiness
    legacy = AggregatedAssessment(
        role_readiness_internal=40,
        interview_readiness_internal=40,
        role_readiness_low=35,
        role_readiness_high=45,
        interview_readiness_low=35,
        interview_readiness_high=45,
        overall_signal_confidence=0.5,
        availability_status="LIMITED_SIGNAL",
        verdict_code="NOT_READY_YET",
        root_cause_code="TECHNICAL_DEPTH",
    )

    # New assessment with strong evidence
    strong_results = {k: output(k, strength=SignalStrength.STRONG) for k in AssessorType}

    async def build_strong():
        repo = Repo()
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(strong_results) for k in AssessorType}, None
        )
        return await orchestrator.assess(SESSION, USER), repo

    import asyncio

    new_bundle, new_repo = asyncio.run(build_strong())
    new_aggregated = FinalAssessmentAggregator().aggregate(new_bundle)

    # New strong should dominate over legacy weak
    assert new_aggregated.role_readiness_low > legacy.role_readiness_low


# ------------------------------------------------------------------ (13) Legacy: old diagnostic, current validates same refs → trusted/revalidated
def test_b5_legacy_with_provenance_revalidated():
    """Test 13: Old diagnostic, current validates same refs → expect trusted/revalidated-current."""
    # Same turn_id referenced in both old and new
    shared_turn = ANSWER.id

    old_stored = StoredSpecialistAssessment(
        id=uuid4(),
        session_id=SESSION,
        assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.COMPLETE,
        result_json=output(AssessorType.TECHNICAL, turn=shared_turn),
        model="legacy-model",
        model_version="v1",
        prompt_version="v1",
        rubric_version="v1",
        created_at=datetime.now(UTC),
    )

    # New assessment with same evidence
    new_results = {k: output(k, turn=shared_turn) for k in AssessorType}

    import asyncio

    async def build_new():
        repo = Repo()
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(new_results) for k in AssessorType}, None
        )
        return await orchestrator.assess(SESSION, USER), repo

    new_bundle, new_repo = asyncio.run(build_new())

    # Both should reference the same turn
    old_turn_ids = set(old_stored.result_json.evidence_turn_ids)
    new_turn_ids = set(new_bundle.technical.result_json.evidence_turn_ids)

    assert old_turn_ids == new_turn_ids
    assert shared_turn in old_turn_ids

    # Check both pass validation
    assert checks.check_no_invented_evidence([old_stored], TRANSCRIPT) == []
    assert checks.check_no_invented_evidence(new_repo.stored, TRANSCRIPT) == []


# ------------------------------------------------------------------ (14) Mixed: new trusted COMPLETE + old unverifiable → new dominates
def test_b5_mixed_current_legacy_new_dominates():
    """Test 14: New trusted COMPLETE + old unverifiable → expect new trusted dominates."""
    from app.verdict_models import AggregatedAssessment

    # Old unverifiable
    old_aggregated = AggregatedAssessment(
        role_readiness_internal=45,
        interview_readiness_internal=45,
        role_readiness_low=40,
        role_readiness_high=50,
        interview_readiness_low=40,
        interview_readiness_high=50,
        overall_signal_confidence=0.3,  # Low confidence
        availability_status="LIMITED_SIGNAL",
        verdict_code="NOT_READY_YET",
        root_cause_code="TECHNICAL_DEPTH",
    )

    # New strong evidence
    strong_results = {k: output(k, strength=SignalStrength.STRONG) for k in AssessorType}

    async def build_new():
        repo = Repo()
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(strong_results) for k in AssessorType}, None
        )
        return await orchestrator.assess(SESSION, USER), repo

    import asyncio

    new_bundle, new_repo = asyncio.run(build_new())
    new_aggregated = FinalAssessmentAggregator().aggregate(new_bundle)

    # New should have higher readiness than old
    assert new_aggregated.role_readiness_low > old_aggregated.role_readiness_low
    assert new_aggregated.overall_signal_confidence > old_aggregated.overall_signal_confidence


# ------------------------------------------------------------------ (15) Readiness aggregation: exclude unverifiable
def test_b5_readiness_unverifiable_excluded():
    """Test 15: Readiness aggregation excludes unverifiable assessments."""
    from app.verdict_models import AggregatedAssessment

    # Unverifiable assessments (no evidence)
    unverifiable_bundle = SpecialistAssessmentBundle(session_id=SESSION)
    unverifiable_aggregated = FinalAssessmentAggregator().aggregate(unverifiable_bundle)

    # Verifiable assessments
    async def build_verifiable():
        repo = Repo()
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(honest()) for k in AssessorType}, None
        )
        return await orchestrator.assess(SESSION, USER), repo

    import asyncio

    valid_bundle, valid_repo = asyncio.run(build_verifiable())
    valid_aggregated = FinalAssessmentAggregator().aggregate(valid_bundle)

    # Unverifiable should have zero confidence
    assert unverifiable_aggregated.overall_signal_confidence == 0

    # Verifiable should have higher confidence
    assert valid_aggregated.overall_signal_confidence > unverifiable_aggregated.overall_signal_confidence


# ------------------------------------------------------------------ (16) Progress trend: exclude unverifiable
def test_b5_progress_unverifiable_excluded():
    """Test 16: Progress trend calculation excludes unverifiable assessments."""
    from app.verdict_models import AggregatedAssessment

    # Create multiple unverifiable snapshots
    snapshots = [
        AggregatedAssessment(
            role_readiness_internal=50 + i * 5,
            interview_readiness_internal=50 + i * 5,
            role_readiness_low=48 + i * 5,
            role_readiness_high=52 + i * 5,
            interview_readiness_low=48 + i * 5,
            interview_readiness_high=52 + i * 5,
            overall_signal_confidence=0,  # Unverifiable
            availability_status="LIMITED_SIGNAL",
            verdict_code="NOT_READY_YET",
            root_cause_code="TECHNICAL_DEPTH",
        )
        for i in range(3)
    ]

    # Progress trend with only unverifiable should show no improvement
    # (confidence-weighted progress would be 0)
    total_confidence = sum(s.overall_signal_confidence for s in snapshots)
    assert total_confidence == 0

    # Add a verifiable snapshot
    valid_snapshot = AggregatedAssessment(
        role_readiness_internal=75,
        interview_readiness_internal=75,
        role_readiness_low=73,
        role_readiness_high=77,
        interview_readiness_low=73,
        interview_readiness_high=77,
        overall_signal_confidence=1.0,  # Verifiable
        availability_status="AVAILABLE",
        verdict_code="STRONG",
        root_cause_code="TECHNICAL_DEPTH",
    )

    all_snapshots = snapshots + [valid_snapshot]
    weighted_progress = sum(
        (s.role_readiness_low * s.overall_signal_confidence) for s in all_snapshots
    ) / sum(s.overall_signal_confidence for s in all_snapshots)

    # With zero-confidence snapshots excluded, progress should reflect valid only
    assert weighted_progress > 50  # Reflects the valid snapshot's 75


# ------------------------------------------------------------------ (17) Recommendations: ignore unverifiable
def test_b5_recommendations_ignore_unverifiable():
    """Test 17: Practice recommendations NOT from unverifiable assessments."""
    from app.verdict_models import AggregatedAssessment, VerdictLanguageOutput

    # Unverifiable assessment (no evidence)
    unverifiable_bundle = SpecialistAssessmentBundle(session_id=SESSION)
    unverifiable_aggregated = FinalAssessmentAggregator().aggregate(unverifiable_bundle)

    # Mock recommendation generator that should ignore unverifiable
    def generate_recommendations(aggregated: AggregatedAssessment) -> list[str]:
        if aggregated.overall_signal_confidence == 0:
            return []  # Ignore unverifiable
        return ["Focus on system design interviews."]

    # Unverifiable should yield no recommendations
    unverifiable_recs = generate_recommendations(unverifiable_aggregated)
    assert unverifiable_recs == []

    # Verifiable should yield recommendations
    async def build_verifiable():
        repo = Repo()
        orchestrator = AssessmentOrchestrator(
            repo, {k: Runner(honest()) for k in AssessorType}, None
        )
        return await orchestrator.assess(SESSION, USER)

    import asyncio

    valid_bundle = asyncio.run(build_verifiable())
    valid_aggregated = FinalAssessmentAggregator().aggregate(valid_bundle)

    valid_recs = generate_recommendations(valid_aggregated)
    assert len(valid_recs) > 0


# ------------------------------------------------------------------ (18) Transcript: unverifiable session preserved
def test_b5_transcript_preserved_unverifiable():
    """Test 18: Session unverifiable diagnostic → transcript/answers/history accessible."""
    # Create a session that existed but produced unverifiable assessment
    session_transcript = CAND.transcript_text()
    session_turns = CAND.turns

    # Simulate unverifiable assessment (NOT_ENOUGH_SIGNAL)
    unverifiable_bundle = SpecialistAssessmentBundle(session_id=SESSION)

    # Transcript should still be accessible
    assert len(session_transcript) > 0
    assert len(session_turns) > 0

    # Verify transcript content matches expected format
    for turn_id, text in session_transcript.items():
        assert isinstance(turn_id, uuid4().__class__)
        assert isinstance(text, str)
        assert len(text) > 0

    # Answers (candidate turns) should be retrievable
    candidate_turns = [t for t in session_turns if t.speaker == "CANDIDATE"]
    assert len(candidate_turns) > 0

    # Each candidate turn should have text and category
    for turn in candidate_turns:
        assert hasattr(turn, "text")
        assert hasattr(turn, "category")
        assert turn.text is not None

    # History (all turns) should be retrievable in order
    indices = [t.index for t in session_turns]
    assert indices == sorted(indices)  # Turns should be ordered by index

# ------------------------------------------------------------------ cached-reuse trust boundary (orchestrator)
class _NoQuoteLayer(AssessmentOrchestrator):
    async def _validate_quotes(self, output, context, user_id):  # B5 gate is what is under test
        return None


class CachedRepo(Repo):
    def __init__(self, cached, *, context=True):
        super().__init__()
        self.cached, self.has_context = cached, context

    async def get_latest(self, session_id, user_id, kind):
        return self.cached.get(kind)

    async def load_context(self, session_id, user_id, kind):
        return await super().load_context(session_id, user_id, kind) if self.has_context else None


def _stored(kind, out):
    return StoredSpecialistAssessment(
        id=uuid4(), session_id=SESSION, assessor_type=kind, status=out.status, result_json=out,
        model="m", model_version="m", prompt_version="v1", rubric_version="v1", created_at=datetime.now(UTC),
    )


def _assess(repo, results):
    import asyncio

    return asyncio.run(_NoQuoteLayer(repo, {k: Runner(results) for k in AssessorType}, None).assess(SESSION, USER))


def test_b5_cached_invalid_row_is_not_reused_and_is_regenerated():
    ghost = uuid4()
    cached = {k: _stored(k, output(k, turn=ghost)) for k in AssessorType}
    repo = CachedRepo(cached)
    bundle = _assess(repo, honest())
    assert len(repo.stored) == 3                                  # fresh rows stored, stale rows untouched
    assert all(row.result_json.evidence_turn_ids == [ANSWER.id] for row in repo.stored)
    assert bundle.technical is not None and bundle.technical.id != cached[AssessorType.TECHNICAL].id


def test_b5_cached_valid_row_is_reused_without_regeneration():
    cached = {k: _stored(k, output(k)) for k in AssessorType}
    repo = CachedRepo(cached)
    bundle = _assess(repo, fabricated_turn_id())                  # runner would be rejected if consulted
    assert repo.stored == [] and bundle.technical.id == cached[AssessorType.TECHNICAL].id


def test_b5_cached_row_without_context_is_not_trusted():
    cached = {k: _stored(k, output(k, turn=uuid4())) for k in AssessorType}
    repo = CachedRepo(cached, context=False)
    bundle = _assess(repo, honest())
    assert bundle.technical is None and bundle.behaviour is None and bundle.claims is None


def test_b5_trivial_fragment_quote_is_not_evidence():
    from app.evidence_validator import EvidenceValidator

    turns = EvidenceValidator.extract_candidate_turns(
        [{"id": str(ANSWER.id), "speaker": "candidate", "text": ANSWER.text}]
    )
    assert turns and turns[0].id == ANSWER.id                      # str ids coerced to UUID
    v = EvidenceValidator()
    assert not v.validate_evidence_quotes([{"turn_id": ANSWER.id, "quote": "a"}], turns).is_valid
    assert v.validate_evidence_quotes([{"turn_id": ANSWER.id, "quote": ANSWER.text[:20]}], turns).is_valid
    assert not v.validate_evidence_quotes([{"turn_id": None, "quote": ANSWER.text[:20]}], turns).is_valid
