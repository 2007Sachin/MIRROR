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
    decision=AdjudicationDecision(affected_dimension="technical_understanding_and_claim_ownership", final_position="Technical understanding is strong; ownership evidence remains weak.", confidence=.8, evidence_ids=[EVIDENCE], reason_summary="These are separate dimensions.", specialist_positions={"TECHNICAL":"strong","CLAIMS":"weak"})
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

