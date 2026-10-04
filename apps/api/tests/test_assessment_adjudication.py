from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.agents.definitions import AgentExecutionResult
from app.assessment_adjudication_models import AdjudicationContext, AdjudicationDecision
from app.assessment_adjudication_service import AssessmentAdjudicator
from app.assessment_disagreement import AssessmentDisagreementDetector
from app.specialist_assessor_models import (
    AssessorType, SignalStrength, SpecialistAssessmentBundle,
    SpecialistAssessmentOutput, SpecialistStatus, StoredSpecialistAssessment,
)


SESSION, USER, EVIDENCE = uuid4(), uuid4(), uuid4()


def stored(kind, strength, reason):
    output = SpecialistAssessmentOutput(assessor_type=kind, status=SpecialistStatus.COMPLETE,
        signal_strength=strength, confidence=.8, evidence_turn_ids=[uuid4()], evidence_quotes=[], reason_summary=reason)
    return StoredSpecialistAssessment(id=uuid4(), session_id=SESSION, assessor_type=kind,
        status=SpecialistStatus.COMPLETE, result_json=output, model="m", model_version="m",
        prompt_version="v1", rubric_version="v1", created_at=datetime.now(UTC))


class Repo:
    def __init__(self): self.records=[]
    async def load_context(self, session, user, disagreement, bundle):
        return AdjudicationContext(session_id=session, disagreement=disagreement, specialist_bundle=bundle,
            validated_evidence=[{"id": str(EVIDENCE), "quote_text": "stored"}])
    async def store(self, context, decision, model, prompt):
        self.records.append(decision)
        return decision


class Runner:
    def __init__(self, decision=None, fail=False): self.calls=0; self.decision=decision; self.fail=fail
    async def run(self, *args, **kwargs):
        self.calls+=1
        if self.fail: return AgentExecutionResult(execution_id=uuid4(), agent_name="x", model="m", prompt_version="v1", success=False, latency_ms=1, retry_count=0)
        return AgentExecutionResult(execution_id=uuid4(), agent_name="x", model="m", prompt_version="v1", success=True, output=self.decision.model_dump(mode="json"), latency_ms=1, retry_count=0)


def test_no_disagreement_does_not_call_adjudicator():
    bundle=SpecialistAssessmentBundle(session_id=SESSION, technical=stored(AssessorType.TECHNICAL, SignalStrength.MODERATE,"tech"), claims=stored(AssessorType.CLAIMS, SignalStrength.MODERATE,"claims"))
    runner=Runner()
    assert asyncio.run(AssessmentAdjudicator(AssessmentDisagreementDetector(),Repo(),runner).adjudicate(SESSION,USER,bundle)) == []
    assert runner.calls == 0


def test_material_disagreement_calls_adjudicator_and_preserves_two_truths():
    bundle=SpecialistAssessmentBundle(session_id=SESSION, technical=stored(AssessorType.TECHNICAL, SignalStrength.STRONG,"SQL trade-off understanding is strong."), claims=stored(AssessorType.CLAIMS, SignalStrength.WEAK,"Personal ownership evidence is weak."))
    decision=AdjudicationDecision(affected_dimension="technical_understanding_and_claim_ownership", final_position="Technical understanding is strong; ownership evidence remains weak.", confidence=.8, evidence_ids=[EVIDENCE], reason_summary="These are separate dimensions.", specialist_positions={"TECHNICAL":"SQL trade-off understanding is strong.","CLAIMS":"Personal ownership evidence is weak."})
    runner=Runner(decision); repo=Repo()
    records=asyncio.run(AssessmentAdjudicator(AssessmentDisagreementDetector(),repo,runner).adjudicate(SESSION,USER,bundle))
    assert runner.calls == 1 and records[0].final_position == decision.final_position


def test_invalid_evidence_and_model_failure_are_safe_noops():
    bundle=SpecialistAssessmentBundle(session_id=SESSION, technical=stored(AssessorType.TECHNICAL, SignalStrength.STRONG,"technical"), claims=stored(AssessorType.CLAIMS, SignalStrength.WEAK,"claims"))
    invalid=AdjudicationDecision(affected_dimension="technical_understanding_and_claim_ownership", final_position="invalid position", confidence=.5, evidence_ids=[uuid4()], reason_summary="invalid evidence", specialist_positions={"TECHNICAL":"x","CLAIMS":"x"})
    assert asyncio.run(AssessmentAdjudicator(AssessmentDisagreementDetector(),Repo(),Runner(invalid)).adjudicate(SESSION,USER,bundle)) == []
    assert asyncio.run(AssessmentAdjudicator(AssessmentDisagreementDetector(),Repo(),Runner(fail=True)).adjudicate(SESSION,USER,bundle)) == []


def test_prompt_resists_injection_and_bans_averaging():
    prompt=(Path(__file__).parents[3]/"apps/api/app/prompts/adjudicator/v1.md").read_text().casefold()
    assert "untrusted" in prompt and "do not average" in prompt and "never invent" in prompt



# ---------------------------------------------------------------- B7: specialist position integrity
import pytest

from app.assessment_adjudication_models import StoredAdjudication


def _disagreeing():
    return SpecialistAssessmentBundle(
        session_id=SESSION,
        technical=stored(AssessorType.TECHNICAL, SignalStrength.STRONG, "SQL trade-off understanding is strong."),
        claims=stored(AssessorType.CLAIMS, SignalStrength.WEAK, "Personal ownership evidence is weak."))


def _decision(context, **over):
    d = context.disagreement
    fields = dict(affected_dimension=d.affected_dimension, final_position="Adjudicator reads both as partly true.",
                  confidence=.7, evidence_ids=[EVIDENCE], reason_summary="Separate dimensions.",
                  specialist_positions=dict(d.specialist_positions))
    fields.update(over)
    return AdjudicationDecision(**fields)


class Runner2:
    def __init__(self, make): self.make, self.calls = make, 0
    async def run(self, name, payload, **kw):
        self.calls += 1
        out = self.make(payload)
        return AgentExecutionResult(execution_id=uuid4(), agent_name=name, model="m", prompt_version="v1",
                                    success=True, output=out.model_dump(mode="json"), latency_ms=1, retry_count=0)


class RecordingRepo(Repo):
    def __init__(self, mutate=False, fail_store=False): super().__init__(); self.mutate, self.fail_store, self.stored = mutate, fail_store, []
    async def load_context(self, session, user, disagreement, bundle):
        if self.mutate:  # hostile/buggy repository or agent touching what it was handed
            bundle.technical.result_json.reason_summary = "TAMPERED"
            bundle.technical.status = SpecialistStatus.NOT_ENOUGH_SIGNAL
        return await super().load_context(session, user, disagreement, bundle)
    async def store(self, context, decision, model, prompt):
        if self.fail_store:
            context.specialist_bundle.claims.result_json.reason_summary = "PARTIAL WRITE"
            raise RuntimeError("db down")
        rec = StoredAdjudication(id=uuid4(), session_id=context.session_id, affected_dimension=decision.affected_dimension,
            specialist_inputs=context.specialist_bundle.model_dump(mode="json"), final_decision=decision,
            confidence=decision.confidence, model=model, prompt_version=prompt, created_at=datetime.now(UTC))
        self.stored.append(rec)
        return rec


def _run(bundle, make, repo=None):
    repo = repo or RecordingRepo()
    out = asyncio.run(AssessmentAdjudicator(AssessmentDisagreementDetector(), repo, Runner2(make)).adjudicate(SESSION, USER, bundle))
    return repo, out


def test_disagreement_keeps_specialist_position_and_adjudicator_conclusion_separate():
    bundle = _disagreeing(); before = bundle.model_dump(mode="json")
    repo, out = _run(bundle, _decision)
    assert bundle.model_dump(mode="json") == before
    rec = out[0]
    assert rec.final_decision.specialist_positions == {"TECHNICAL": "SQL trade-off understanding is strong.", "CLAIMS": "Personal ownership evidence is weak."}
    assert rec.final_decision.final_position == "Adjudicator reads both as partly true."   # Y stays Y
    assert rec.specialist_inputs["technical"]["result_json"]["signal_strength"] == "STRONG"   # X stays X
    assert rec.specialist_inputs["claims"]["result_json"]["signal_strength"] == "WEAK"


@pytest.mark.parametrize("rewrite", [
    {"TECHNICAL": "weak", "CLAIMS": "strong"},
    {"TECHNICAL": "SQL trade-off understanding is strong.", "CLAIMS": "Ownership is fine."},
    {"TECHNICAL": "SQL trade-off understanding is strong.", "CLAIMS": "Personal ownership evidence is weak.", "EXTRA": "x"},
])
def test_confident_override_attempt_is_dropped_not_persisted(rewrite):
    bundle = _disagreeing(); before = bundle.model_dump(mode="json")
    repo, out = _run(bundle, lambda c: _decision(c, confidence=1.0, specialist_positions=rewrite))
    assert out == [] and repo.stored == [] and bundle.model_dump(mode="json") == before


def test_repository_or_agent_mutation_cannot_reach_specialist_rows_or_cache():
    bundle = _disagreeing(); cached = bundle.technical; before = bundle.model_dump(mode="json")
    repo, out = _run(bundle, _decision, RecordingRepo(mutate=True))
    assert bundle.model_dump(mode="json") == before and bundle.technical is cached
    assert cached.status == SpecialistStatus.COMPLETE and cached.result_json.reason_summary.startswith("SQL")
    assert out == [] and repo.stored == []        # a context that diverges from persisted state is never adjudicated or stored


def test_failed_adjudication_attempt_cannot_partially_modify_specialist_state():
    bundle = _disagreeing(); before = bundle.model_dump(mode="json")
    repo, out = _run(bundle, _decision, RecordingRepo(fail_store=True))
    assert out == [] and bundle.model_dump(mode="json") == before


def test_retry_does_not_mutate_specialist_history():
    bundle = _disagreeing(); before = bundle.model_dump(mode="json")
    repo = RecordingRepo(mutate=True)
    for _ in range(3):
        _run(bundle, _decision, repo)
    assert bundle.model_dump(mode="json") == before and repo.stored == []


def test_multiple_disagreements_leave_every_specialist_intact():
    bundle = SpecialistAssessmentBundle(session_id=SESSION,
        technical=stored(AssessorType.TECHNICAL, SignalStrength.STRONG, "tech strong"),
        claims=stored(AssessorType.CLAIMS, SignalStrength.WEAK, "claims weak"),
        behaviour=stored(AssessorType.BEHAVIOUR, SignalStrength.MODERATE, "behaviour moderate")
            .model_copy(update={"status": SpecialistStatus.NOT_ENOUGH_SIGNAL}))
    before = bundle.model_dump(mode="json")
    repo, out = _run(bundle, _decision, RecordingRepo(mutate=True))
    assert out == [] and bundle.model_dump(mode="json") == before
    repo, out = _run(bundle, _decision)           # honest repository: both disagreements adjudicated, specialists intact
    assert len(out) == 2 and bundle.model_dump(mode="json") == before


def test_specialist_position_survives_serialization_round_trip():
    bundle = _disagreeing()
    _, out = _run(bundle, _decision)
    again = StoredAdjudication.model_validate_json(out[0].model_dump_json())
    assert again == out[0]
    assert SpecialistAssessmentBundle.model_validate(again.specialist_inputs) == bundle


def test_runner_tampering_with_its_payload_cannot_change_the_stored_record_or_allow_list():
    bundle = _disagreeing(); before = bundle.model_dump(mode="json"); fabricated = uuid4()

    def hostile(payload):
        payload.specialist_bundle.technical.result_json.reason_summary = "TAMPERED"
        payload.specialist_bundle.claims.status = SpecialistStatus.NOT_ENOUGH_SIGNAL
        payload.validated_evidence.append({"id": str(fabricated), "quote_text": "invented"})
        return _decision(payload, evidence_ids=[fabricated])

    repo, out = _run(bundle, hostile)
    assert out == [] and repo.stored == [] and bundle.model_dump(mode="json") == before

    def tamper_but_stay_honest(payload):
        payload.specialist_bundle.technical.result_json.reason_summary = "TAMPERED"
        return _decision(payload)

    repo, out = _run(bundle, tamper_but_stay_honest)
    assert len(out) == 1 and out[0].specialist_inputs == before          # stored audit record is the original, not the runner's edit
