"""Behaviours 5, 7 and the verdict half of 10: specialist assessment, adjudication, aggregation.

Real systems under test: AssessmentOrchestrator, AssessmentDisagreementDetector,
AssessmentAdjudicator, FinalAssessmentAggregator, VerdictLanguageService (all unmodified).
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

import ai_eval_checks as checks
import ai_eval_harness as h
from app.agents import AgentRegistry, AgentRunner, PromptLoader
from app.agents.definitions import AgentExecutionResult, ProviderRequest, ProviderResponse
from app.agents.errors import ProviderFailureError
from app.agents.verdict import create_verdict_agent
from app.assessment_adjudication_models import (
    AdjudicationContext,
    AdjudicationDecision,
    StoredAdjudication,
)
from app.assessment_adjudication_service import AssessmentAdjudicator
from app.assessment_disagreement import AssessmentDisagreementDetector
from app.assessment_orchestrator import AssessmentOrchestrator, SpecialistAssessmentRejected
from app.claim_resolution_models import ClaimsAudit
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
from app.verdict_models import AggregatedAssessment, VerdictLanguageInput, VerdictLanguageOutput
from app.verdict_service import VerdictLanguageService

pytestmark = pytest.mark.ai_eval

SESSION, USER = uuid4(), uuid4()
CAND = h.build_candidate("P7")
TRANSCRIPT = CAND.transcript_text()
ANSWER = CAND.candidate_turns[0]
QUOTE = "Redis read-through cache"


# ------------------------------------------------------------------ doubles / builders
def output(kind, *, status=SpecialistStatus.COMPLETE, strength=SignalStrength.MODERATE,
           quote=QUOTE, turn=None, reason="Bounded evidence supports this narrow assessment."):
    turn = turn or ANSWER.id
    done = status == SpecialistStatus.COMPLETE
    return SpecialistAssessmentOutput(
        assessor_type=kind, status=status, signal_strength=strength if done else SignalStrength.NONE,
        confidence=0.8, evidence_turn_ids=[turn] if done else [],
        evidence_quotes=[{"turn_id": turn, "quote": quote}] if done else [],
        reason_summary=reason if done else "The session did not provide enough evidence.")


class Runner:
    def __init__(self, results):
        self.results = results

    async def run(self, agent_name, payload, *, context=None):
        kind = AssessorType(agent_name.removeprefix("assessor_").upper())
        return AgentExecutionResult(
            execution_id=uuid4(), agent_name=agent_name, model="fake", prompt_version="v1", success=True,
            output=self.results[kind].model_dump(mode="json"), latency_ms=1, retry_count=0)


class Repo:
    def __init__(self):
        self.stored = []

    async def load_context(self, session_id, user_id, kind):
        return SpecialistAssessmentContext(
            session_id=session_id, assessor_type=kind,
            transcript_turns=[AssessmentTranscriptTurn(id=t.id, speaker=t.speaker, text=t.text,
                                                       turn_type="PLANNED", phase="ROLE_CORE")
                              for t in CAND.turns])

    async def store(self, session_id, kind, status, result, model, model_version, prompt_version, rubric_version):
        row = StoredSpecialistAssessment(
            id=uuid4(), session_id=session_id, assessor_type=kind, status=status, result_json=result,
            model=model, model_version=model_version, prompt_version=prompt_version,
            rubric_version=rubric_version, created_at=datetime.now(UTC))
        self.stored.append(row)
        return row


class NoQuoteCheckOrchestrator(AssessmentOrchestrator):
    async def _validate_evidence_b5(self, output, context):  # type: ignore[override]
        """Skip B5 validation to test check layer."""
        return None
    
    async def _validate_quotes(self, output, context, user_id):  # type: ignore[override]
        return None


def assess(results, cls=AssessmentOrchestrator):
    repo = Repo()
    orchestrator = cls(repo, {k: Runner(results) for k in AssessorType}, None)  # type: ignore[arg-type]
    return asyncio.run(orchestrator.assess(SESSION, USER)), repo


def honest():
    return {k: output(k) for k in AssessorType}


def invented(**kw):
    return {**honest(), AssessorType.TECHNICAL: output(AssessorType.TECHNICAL, **kw)}


# ------------------------------------------------------------------ (5) no invented evidence
def test_b5_every_cited_span_exists_in_transcript():
    bundle, repo = assess(honest())
    assert len(repo.stored) == 3
    assert checks.check_no_invented_evidence(repo.stored, TRANSCRIPT) == []
    assert checks.check_no_numeric_publish_without_evidence(
        bundle, FinalAssessmentAggregator().aggregate(bundle), transcript=TRANSCRIPT) == []


@pytest.mark.parametrize("bad", [
    {"quote": "I built every production system at Lindqvist."},
    {"turn": uuid4()},
], ids=["invented-quote", "unknown-turn"])
def test_b5_orchestrator_rejects_invented_evidence_and_stores_nothing(bad):
    repo = Repo()
    orchestrator = AssessmentOrchestrator(repo, {k: Runner(invented(**bad)) for k in AssessorType}, None)  # type: ignore[arg-type]
    with pytest.raises(SpecialistAssessmentRejected):
        asyncio.run(orchestrator.assess(SESSION, USER))
    assert checks.check_no_invented_evidence(repo.stored, TRANSCRIPT) == []


@pytest.mark.parametrize("bad", [
    {"quote": "I built every production system at Lindqvist."},
    {"turn": uuid4()},
], ids=["invented-quote", "unknown-turn"])
def test_b5_negative_control_orchestrator_without_quote_validation(bad):
    _, repo = assess(invented(**bad), cls=NoQuoteCheckOrchestrator)
    assert checks.check_no_invented_evidence(repo.stored, TRANSCRIPT)


def _rows(status):
    return assess({k: output(k, status=status) for k in AssessorType})[0]


def test_b5_no_numeric_publish_without_evidence():
    bundle = _rows(SpecialistStatus.NOT_ENOUGH_SIGNAL)
    aggregated = FinalAssessmentAggregator().aggregate(bundle)
    assert checks.check_no_numeric_publish_without_evidence(bundle, aggregated) == []
    empty = SpecialistAssessmentBundle(session_id=SESSION)
    assert checks.check_no_numeric_publish_without_evidence(empty, FinalAssessmentAggregator().aggregate(empty)) == []


def test_b5_negative_control_confident_numbers_without_evidence():
    bundle = _rows(SpecialistStatus.NOT_ENOUGH_SIGNAL)
    overconfident = AggregatedAssessment(
        role_readiness_internal=82, interview_readiness_internal=82, role_readiness_low=80,
        role_readiness_high=84, interview_readiness_low=80, interview_readiness_high=84,
        overall_signal_confidence=1.0, availability_status="AVAILABLE", verdict_code="READY",
        root_cause_code="TECHNICAL_DEPTH")
    assert len(checks.check_no_numeric_publish_without_evidence(bundle, overconfident)) >= 4


# ------------------------------------------------------------------ (7) adjudication
def stored(kind, strength, reason, status=SpecialistStatus.COMPLETE):
    out = output(kind, status=status, strength=strength, reason=reason)
    return StoredSpecialistAssessment(
        id=uuid4(), session_id=SESSION, assessor_type=kind, status=status, result_json=out, model="m",
        model_version="m", prompt_version="v1", rubric_version="v1", created_at=datetime.now(UTC))


DIM = "technical_understanding_and_claim_ownership"
EVIDENCE = uuid4()


def disagreeing():
    return SpecialistAssessmentBundle(
        session_id=SESSION,
        technical=stored(AssessorType.TECHNICAL, SignalStrength.STRONG, "SQL trade-off understanding is strong."),
        claims=stored(AssessorType.CLAIMS, SignalStrength.WEAK, "Personal ownership evidence is weak."))


def agreeing():
    return SpecialistAssessmentBundle(
        session_id=SESSION,
        technical=stored(AssessorType.TECHNICAL, SignalStrength.MODERATE, "Adequate technical detail."),
        claims=stored(AssessorType.CLAIMS, SignalStrength.MODERATE, "Adequate ownership detail."))


class AdjRepo:
    def __init__(self, mutate=False):
        self.records, self.mutate = [], mutate

    async def load_context(self, session, user, disagreement, bundle):
        if self.mutate:  # broken double: tampers with a specialist's immutable output
            bundle.technical.result_json.reason_summary = "Technical evidence was actually weak."
        return AdjudicationContext(session_id=session, disagreement=disagreement, specialist_bundle=bundle,
                                   validated_evidence=[{"id": str(EVIDENCE), "quote_text": "stored"}])

    async def store(self, context, decision, model, prompt):
        rec = StoredAdjudication(
            id=uuid4(), session_id=context.session_id, affected_dimension=decision.affected_dimension,
            specialist_inputs=context.disagreement.specialist_positions, final_decision=decision,
            confidence=decision.confidence, model=model, prompt_version=prompt, created_at=datetime.now(UTC))
        self.records.append(rec)
        return rec


class AdjRunner:
    def __init__(self, decision_for):
        self.calls, self.decision_for = 0, decision_for

    async def run(self, name, payload, *, context=None):
        self.calls += 1
        decision = self.decision_for(payload)
        return AgentExecutionResult(execution_id=uuid4(), agent_name=name, model="fake", prompt_version="v1",
                                    success=True, output=decision.model_dump(mode="json"), latency_ms=1,
                                    retry_count=0)


def faithful(context, **over):
    d = context.disagreement
    fields = dict(affected_dimension=d.affected_dimension, final_position="Both specialist findings stand.",
                  confidence=0.8, evidence_ids=[EVIDENCE], reason_summary="They measure separate dimensions.",
                  specialist_positions=dict(d.specialist_positions))
    fields.update(over)
    return AdjudicationDecision(**fields)


class FlakyDetector(AssessmentDisagreementDetector):
    """Negative control: detection depends on call count (non-deterministic)."""

    n = 0

    def detect(self, bundle):
        FlakyDetector.n += 1
        return super().detect(bundle) if FlakyDetector.n % 2 else []


class RewritingAdjudicator:
    """Deliberately broken negative-control service: persists arbitrary rewritten positions."""

    def __init__(self, detector, repo, runner):
        self.detector, self.repo, self.runner = detector, repo, runner

    async def adjudicate(self, session, user, bundle):
        records = []
        for disagreement in self.detector.detect(bundle):
            context = await self.repo.load_context(session, user, disagreement, bundle)
            execution = await self.runner.run("broken_adjudicator", context)
            decision = AdjudicationDecision.model_validate(execution.output)
            records.append(await self.repo.store(context, decision, execution.model, execution.prompt_version))
        return records


def adjudicate(bundle, *, decision_for=faithful, detector=None, repo=None, cls=AssessmentAdjudicator):
    repo = repo or AdjRepo()
    runner = AdjRunner(decision_for)
    adjudicator = cls(detector or AssessmentDisagreementDetector(), repo, runner)  # type: ignore[arg-type]
    before = bundle.model_dump()
    records = asyncio.run(adjudicator.adjudicate(SESSION, USER, bundle))
    return before, records, runner


@pytest.mark.parametrize("make,expect", [(disagreeing, True), (agreeing, False)], ids=["disagree", "agree"])
def test_b7_adjudication_respects_specialists_and_detects_deterministically(make, expect):
    bundle = make()
    before, records, runner = adjudicate(bundle)
    assert checks.check_adjudication(
        detector=AssessmentDisagreementDetector(), bundle=bundle, snapshot_before=before, bundle_after=bundle,
        calls_to_model_in_detect=0, records=records, expect_disagreement=expect) == []
    assert runner.calls == (1 if expect else 0)


def test_b7_real_service_drops_decisions_that_break_the_contract():
    for bad in (lambda c: faithful(c, affected_dimension="some_other_dimension"),
                lambda c: faithful(c, evidence_ids=[uuid4()])):
        _, records, _ = adjudicate(disagreeing(), decision_for=bad)
        assert records == []


def test_b7_real_service_isolates_specialist_rows_from_a_tampering_repository():
    bundle = disagreeing()
    before, records, _ = adjudicate(bundle, repo=AdjRepo(mutate=True))
    assert bundle.model_dump() == before and records == []


def test_b7_negative_controls():
    bundle = disagreeing()
    # (a) non-deterministic detector
    FlakyDetector.n = 0
    flaky = checks.check_adjudication(detector=FlakyDetector(), bundle=bundle, snapshot_before=bundle.model_dump(),
                                      bundle_after=bundle, calls_to_model_in_detect=0, records=[],
                                      expect_disagreement=True)
    assert any("not deterministic" in v for v in flaky)
    # (b) adjudication that tampers with specialist output
    bundle = disagreeing()
    before = bundle.model_dump()
    bundle.technical.result_json.reason_summary = "Technical evidence was actually weak."  # simulated tampering
    records = []
    tamper = checks.check_adjudication(detector=AssessmentDisagreementDetector(), bundle=disagreeing(),
                                       snapshot_before=before, bundle_after=bundle, calls_to_model_in_detect=0,
                                       records=records, expect_disagreement=True)
    assert any("mutated" in v for v in tamper)
    # (c) decision that rewrites the specialists' positions
    bundle = disagreeing()
    before, records, _ = adjudicate(
        bundle, cls=RewritingAdjudicator,
        decision_for=lambda c: faithful(c, specialist_positions={"TECHNICAL": "weak", "CLAIMS": "strong"}))
    rewrite = checks.check_adjudication(detector=AssessmentDisagreementDetector(), bundle=bundle,
                                        snapshot_before=before, bundle_after=bundle, calls_to_model_in_detect=0,
                                        records=records, expect_disagreement=True)
    assert any("altered the specialists' recorded positions" in v for v in rewrite)
    # (d) adjudicating although specialists agree
    bundle = agreeing()
    before, records, _ = adjudicate(bundle, detector=FlakyDetector())
    FlakyDetector.n = 1  # next detect() call returns []
    assert checks.check_adjudication(detector=AssessmentDisagreementDetector(), bundle=disagreeing(),
                                     snapshot_before=before, bundle_after=bundle, calls_to_model_in_detect=1,
                                     records=records, expect_disagreement=False)


# ------------------------------------------------------------------ real-service contracts (initially unmarked RED)
def quote_free_invented():
    return {k: output(k, strength=SignalStrength.STRONG).model_copy(
        update={"evidence_turn_ids": [uuid4()], "evidence_quotes": []}) for k in AssessorType}


def test_b5_known_gap_quote_free_invented_ids_rejected_before_persistence():
    repo = Repo()
    results = quote_free_invented()
    orchestrator = AssessmentOrchestrator(repo, {k: Runner(results) for k in AssessorType}, None)
    try:
        asyncio.run(orchestrator.assess(SESSION, USER))
    except SpecialistAssessmentRejected:
        pass
    else:
        pytest.fail(f"unknown quote-free IDs accepted; persisted={len(repo.stored)}")
    assert repo.stored == []


def test_b5_known_gap_invented_ids_do_not_publish_confident_readiness():
    try:
        bundle, repo = assess(quote_free_invented())
    except SpecialistAssessmentRejected:
        return  # rejection also satisfies the end-to-end no-publish contract
    aggregated = FinalAssessmentAggregator().aggregate(bundle)
    assert checks.check_no_invented_evidence(repo.stored, TRANSCRIPT)
    violations = checks.check_no_numeric_publish_without_evidence(bundle, aggregated, transcript=TRANSCRIPT)
    assert violations == [], aggregated.model_dump()


def test_b7_real_service_rejects_rewritten_positions_without_persistence():
    repo = AdjRepo()
    _, records, _ = adjudicate(disagreeing(), repo=repo, decision_for=lambda c: faithful(
        c, specialist_positions={"TECHNICAL": "weak", "CLAIMS": "strong"}))
    assert records == []
    assert repo.records == []


# ------------------------------------------------------------------ (10) verdict degrades safely
class Failing:
    def __init__(self, exc):
        self.exc = exc

    async def complete(self, request: ProviderRequest, *, timeout_seconds: float) -> ProviderResponse:
        raise self.exc


def verdict_runner(provider):
    registry = AgentRegistry()
    registry.register(create_verdict_agent("fake"))
    return AgentRunner(registry, provider, PromptLoader(), execution_logger=h.NullLogger())


def verdict_input():
    bundle = _rows(SpecialistStatus.COMPLETE)
    return VerdictLanguageInput(aggregate=FinalAssessmentAggregator().aggregate(bundle),
                                specialist_summaries={}, claims_audit=ClaimsAudit())


class FabricatingVerdict(VerdictLanguageService):
    """Negative control: invents reassuring text when the model fails."""

    async def write(self, context, *, session_id, user_id):
        return VerdictLanguageOutput(verdict_summary="You are clearly ready for any interview.",
                                     root_cause_explanation="Nothing needs improving at all.",
                                     confidence_note="We are completely certain about this.")


@pytest.mark.parametrize("exc", [ProviderFailureError("down"), ], ids=["provider-failure"])
def test_b10_verdict_failure_returns_nothing_instead_of_fabricating(exc):
    service = VerdictLanguageService(verdict_runner(Failing(exc)))
    result = asyncio.run(service.write(verdict_input(), session_id=SESSION, user_id=USER))
    assert result is None  # no service-level typed error, persistence or flow result
    assert checks.check_safe_degradation(
        [{"name": "verdict", "content": result}], require_typed_error=False) == []


def test_b10_negative_control_verdict_fabrication_detected():
    service = FabricatingVerdict(verdict_runner(Failing(ProviderFailureError("down"))))
    result = asyncio.run(service.write(verdict_input(), session_id=SESSION, user_id=USER))
    assert checks.check_safe_degradation(
        [{"name": "verdict", "content": result}], require_typed_error=False)
