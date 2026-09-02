from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.definitions import AgentExecutionResult
from app.assessment_orchestrator import AssessmentOrchestrator, SpecialistAssessmentRejected
from app.specialist_assessor_models import (
    AssessmentTranscriptTurn, AssessorType, SignalStrength,
    SpecialistAssessmentContext, SpecialistAssessmentOutput, SpecialistStatus,
    StoredSpecialistAssessment,
)


SESSION_ID = uuid4()
USER_ID = uuid4()
TURN_ID = uuid4()


def output(kind, *, status=SpecialistStatus.COMPLETE, quote="I designed the data model."):
    return SpecialistAssessmentOutput(
        assessor_type=kind, status=status,
        signal_strength=SignalStrength.MODERATE if status == SpecialistStatus.COMPLETE else SignalStrength.NONE,
        confidence=0.8, evidence_turn_ids=[TURN_ID] if status == SpecialistStatus.COMPLETE else [],
        evidence_quotes=[{"turn_id": TURN_ID, "quote": quote}] if status == SpecialistStatus.COMPLETE else [],
        reason_summary="Bounded evidence supports this narrow assessment." if status == SpecialistStatus.COMPLETE else "The session did not provide enough evidence.",
    )


class Runner:
    def __init__(self, result): self.result = result
    async def run(self, *args, **kwargs):
        return AgentExecutionResult(execution_id=uuid4(), agent_name="specialist", model="test",
            prompt_version="v1", success=True, output=self.result.model_dump(mode="json"), latency_ms=1, retry_count=0)


class Repository:
    def __init__(self): self.stored = []
    async def load_context(self, session_id, user_id, kind):
        return SpecialistAssessmentContext(session_id=session_id, assessor_type=kind,
            transcript_turns=[AssessmentTranscriptTurn(id=TURN_ID, speaker="CANDIDATE", text="I designed the data model.", turn_type="DEPTH_PROBE", phase="ROLE_CORE")])
    async def store(self, session_id, kind, status, result, model, model_version, prompt_version, rubric_version):
        stored = StoredSpecialistAssessment(id=uuid4(), session_id=session_id, assessor_type=kind,
            status=status, result_json=result, model=model, model_version=model_version,
            prompt_version=prompt_version, rubric_version=rubric_version, created_at=datetime.now(UTC))
        self.stored.append(stored)
        return stored


def orchestrator(*results):
    repo = Repository()
    runners = {kind: Runner(result) for kind, result in zip(AssessorType, results)}
    return AssessmentOrchestrator(repo, runners, None), repo


def test_orchestrator_runs_three_specialists_and_preserves_categories():
    orchestrated, repo = orchestrator(*[output(kind) for kind in AssessorType])
    bundle = asyncio.run(orchestrated.assess(SESSION_ID, USER_ID))
    assert {item.assessor_type for item in repo.stored} == set(AssessorType)
    assert bundle.technical and bundle.behaviour and bundle.claims


def test_not_enough_signal_is_preserved_without_forced_score():
    orchestrated, _ = orchestrator(
        output(AssessorType.TECHNICAL, status=SpecialistStatus.NOT_ENOUGH_SIGNAL),
        output(AssessorType.BEHAVIOUR), output(AssessorType.CLAIMS),
    )
    bundle = asyncio.run(orchestrated.assess(SESSION_ID, USER_ID))
    assert bundle.technical.status == SpecialistStatus.NOT_ENOUGH_SIGNAL
    assert bundle.disagreements


def test_hallucinated_evidence_quote_is_rejected():
    orchestrated, _ = orchestrator(
        output(AssessorType.TECHNICAL, quote="I built every production system."),
        output(AssessorType.BEHAVIOUR), output(AssessorType.CLAIMS),
    )
    with pytest.raises(SpecialistAssessmentRejected):
        asyncio.run(orchestrated.assess(SESSION_ID, USER_ID))


def test_persona_boundaries_are_explicit_in_prompts():
    root = Path(__file__).parents[3] / "apps/api/app/prompts/assessor"
    technical = (root / "technical/v1.md").read_text().casefold()
    behaviour = (root / "behaviour/v1.md").read_text().casefold()
    claims = (root / "claims/v1.md").read_text().casefold()
    assert "speaking style" in technical
    assert "indian-english" in behaviour and "technical competence" in behaviour
    assert "dishonest" in claims and "low skill" in claims
    assert "untrusted" in technical and "untrusted" in behaviour and "untrusted" in claims


def test_p2_p4_p5_p6_p7_expectations_are_representable_without_verdicts():
    # P2/P4 may have complete technical but insufficient behavioural signal;
    # P5 claims stays descriptive; P6 ownership can weaken; P7 can be complete.
    assert output(AssessorType.TECHNICAL).status == SpecialistStatus.COMPLETE
    assert output(AssessorType.BEHAVIOUR, status=SpecialistStatus.NOT_ENOUGH_SIGNAL).signal_strength == SignalStrength.NONE
    assert "dishonest" in (Path(__file__).parents[3] / "apps/api/app/prompts/assessor/claims/v1.md").read_text().casefold()

