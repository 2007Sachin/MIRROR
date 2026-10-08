from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from app.agents.definitions import AgentExecutionResult
from app.agents.prompts import PromptLoader
from app.agents.specialist_assessors import create_specialist_assessor
from app.assessment_orchestrator import AssessmentOrchestrator, SpecialistAssessmentRejected
from app.specialist_assessor_models import (
    AssessmentEvidence, AssessmentQuestionContext, AssessmentScope, AssessmentTranscriptTurn, AssessorType, DomainAssessment, SignalStrength,
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


def test_orchestrator_preserves_target_scope_and_runs_only_selected_specialist():
    case_quote = "I would separate the profit decline into price, volume, and cost, estimate each change, then compare the options and test the highest-risk cause first."
    dimensions = (
        {"competency_key": "structured_problem_solving", "title": "Structured problem solving", "criteria": "Break the case into relevant parts.", "insufficient_signal": "No framing means NOT_ENOUGH_SIGNAL."},
        {"competency_key": "quantitative_reasoning", "title": "Quantitative reasoning", "criteria": "Explain assumptions and calculations.", "insufficient_signal": "No quantitative signal means NOT_ENOUGH_SIGNAL."},
        {"competency_key": "business_judgement", "title": "Business judgment", "criteria": "Connect recommendations to risks and trade-offs.", "insufficient_signal": "No decision signal means NOT_ENOUGH_SIGNAL."},
    )
    scope = AssessmentScope(
        target_id=uuid4(), role_profile_id=uuid4(), role_family_key="business_analysis",
        round_key="business_problem_solving", round_label="Working through a business case", question_family="case_discussion",
        taxonomy_version=1, catalog_version=1, rubric_key="business_case_v1",
        rubric_version="assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1",
        competency_keys=("structured_problem_solving", "quantitative_reasoning", "business_judgement"),
        assessor_types=(AssessorType.TECHNICAL,), provenance_class="MIRROR_GENERATED",
        dimensions=dimensions,
        questions=(AssessmentQuestionContext(position=1, template_id="case.cafe_profit", family_key="profit_diagnosis", competency_key="structured_problem_solving", question_family="case_discussion", text="How would you structure the problem?"),),
    )

    class ScopedRepository:
        def __init__(self):
            self.stored = []
            self.requested = []

        async def get_latest(self, session_id, user_id, kind):
            return None

        async def load_context(self, session_id, user_id, kind):
            self.requested.append(kind)
            if kind != AssessorType.TECHNICAL:
                return None
            return SpecialistAssessmentContext(
                session_id=session_id,
                assessor_type=kind,
                assessment_scope=scope,
                transcript_turns=[AssessmentTranscriptTurn(id=TURN_ID, speaker="CANDIDATE", text=case_quote, turn_type="DEPTH_PROBE", phase="ROLE_CORE")],
                rubric_version=scope.rubric_version,
            )

        async def store(self, session_id, kind, status, result, model, model_version, prompt_version, rubric_version):
            stored = StoredSpecialistAssessment(
                id=uuid4(), session_id=session_id, assessor_type=kind, status=status,
                result_json=result, model=model, model_version=model_version,
                prompt_version=prompt_version, rubric_version=rubric_version, created_at=datetime.now(UTC),
            )
            self.stored.append(stored)
            return stored

    class ScopedRunner:
        async def run(self, agent_name, assessment_context, **kwargs):
            quote = assessment_context.transcript_turns[0].text
            domain_rows = [
                DomainAssessment(
                    domain=key, status=SpecialistStatus.COMPLETE,
                    signal_strength=SignalStrength.MODERATE, confidence=0.8,
                    evidence_turn_ids=[TURN_ID],
                    evidence_quotes=[AssessmentEvidence(turn_id=TURN_ID, quote=quote)],
                    reason_summary="You showed a reasoned approach in this answer.",
                )
                for key in assessment_context.assessment_scope.competency_keys
            ]
            result = SpecialistAssessmentOutput(
                assessor_type=AssessorType.TECHNICAL, status=SpecialistStatus.COMPLETE,
                dimensions=[], competency_or_domain_assessments=domain_rows,
                signal_strength=SignalStrength.MODERATE, confidence=0.8,
                evidence_turn_ids=[TURN_ID],
                evidence_quotes=[AssessmentEvidence(turn_id=TURN_ID, quote=quote)],
                reason_summary="You showed a reasoned approach in this answer.",
            )
            return AgentExecutionResult(
                execution_id=uuid4(), agent_name=agent_name, model="test", prompt_version="v2",
                success=True, output=result.model_dump(mode="json"), latency_ms=1, retry_count=0,
            )

    repo = ScopedRepository()
    runners: dict[AssessorType, Any] = {kind: Runner(output(kind)) for kind in AssessorType}
    scoped_runners: dict[AssessorType, Any] = {AssessorType.TECHNICAL: ScopedRunner()}
    bundle = asyncio.run(AssessmentOrchestrator(cast(Any, repo), cast(Any, runners), cast(Any, None), scoped_runners=scoped_runners).assess(SESSION_ID, USER_ID))

    assert set(repo.requested) == set(AssessorType)
    assert bundle.assessment_scope == scope
    assert bundle.technical is not None
    assert bundle.behaviour is None and bundle.claims is None




def test_orchestrator_uses_scoped_runner_only_for_round_context():
    keys = ("structured_problem_solving", "quantitative_reasoning", "business_judgement")
    scope = AssessmentScope(
        target_id=uuid4(), role_profile_id=uuid4(), role_family_key="business_analysis",
        round_key="business_problem_solving", round_label="Working through a business case", question_family="case_discussion",
        taxonomy_version=1, catalog_version=1, rubric_key="business_case_v1",
        rubric_version="assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1", competency_keys=keys,
        assessor_types=(AssessorType.TECHNICAL,), provenance_class="MIRROR_GENERATED",
        dimensions=tuple({"competency_key": key, "title": key, "criteria": "Use the listed round-specific reasoning criteria.", "insufficient_signal": "If no signal is present, use NOT_ENOUGH_SIGNAL."} for key in keys),
        questions=(AssessmentQuestionContext(position=1, template_id="case.cafe_profit", family_key="profit_diagnosis", competency_key=keys[0], question_family="case_discussion", text="How would you structure the case?"),),
    )

    class ScopedRepository:
        async def get_latest(self, session_id, user_id, kind):
            return None

        async def load_context(self, session_id, user_id, kind):
            if kind != AssessorType.TECHNICAL:
                return None
            return SpecialistAssessmentContext(session_id=session_id, assessor_type=kind, assessment_scope=scope, rubric_version=scope.rubric_version)

        async def store(self, session_id, kind, status, result, model, model_version, prompt_version, rubric_version):
            return StoredSpecialistAssessment(id=uuid4(), session_id=session_id, assessor_type=kind, status=status, result_json=result, model=model, model_version=model_version, prompt_version=prompt_version, rubric_version=rubric_version, created_at=datetime.now(UTC))

    class CountingRunner(Runner):
        def __init__(self, result):
            super().__init__(result)
            self.calls = 0

        async def run(self, *args, **kwargs):
            self.calls += 1
            return await super().run(*args, **kwargs)

    scoped_domains = [
        DomainAssessment(domain=key, status=SpecialistStatus.NOT_ENOUGH_SIGNAL, signal_strength=SignalStrength.NONE, confidence=0.2, reason_summary="There is not enough signal yet.")
        for key in keys
    ]
    scoped_output = SpecialistAssessmentOutput(
        assessor_type=AssessorType.TECHNICAL, status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
        competency_or_domain_assessments=scoped_domains, signal_strength=SignalStrength.NONE,
        confidence=0.2, reason_summary="There is not enough signal yet.",
    )
    legacy_technical = CountingRunner(output(AssessorType.TECHNICAL))
    scoped_technical = CountingRunner(scoped_output)
    other_legacy = {kind: CountingRunner(output(kind)) for kind in AssessorType if kind != AssessorType.TECHNICAL}
    legacy_runners: dict[AssessorType, Any] = {AssessorType.TECHNICAL: legacy_technical, **other_legacy}

    scoped_bundle = asyncio.run(AssessmentOrchestrator(cast(Any, ScopedRepository()), legacy_runners, cast(Any, None), scoped_runners={AssessorType.TECHNICAL: scoped_technical}).assess(SESSION_ID, USER_ID))
    assert scoped_bundle.assessment_scope == scope
    assert scoped_technical.calls == 1 and legacy_technical.calls == 0
    assert all(runner.calls == 0 for runner in other_legacy.values())

    legacy_bundle = asyncio.run(AssessmentOrchestrator(cast(Any, Repository()), legacy_runners, cast(Any, None), scoped_runners={AssessorType.TECHNICAL: scoped_technical}).assess(SESSION_ID, USER_ID))
    assert legacy_bundle.assessment_scope is None
    assert legacy_technical.calls == 1 and scoped_technical.calls == 1
    assert all(runner.calls == 1 for runner in other_legacy.values())


def test_scoped_assessor_output_rejects_competencies_outside_the_round_contract():
    dimensions = (
        {"competency_key": "structured_problem_solving", "title": "Structured problem solving", "criteria": "Break the case into relevant parts.", "insufficient_signal": "No framing means NOT_ENOUGH_SIGNAL."},
        {"competency_key": "quantitative_reasoning", "title": "Quantitative reasoning", "criteria": "Explain assumptions and calculations.", "insufficient_signal": "No quantitative signal means NOT_ENOUGH_SIGNAL."},
        {"competency_key": "business_judgement", "title": "Business judgment", "criteria": "Connect recommendations to risks and trade-offs.", "insufficient_signal": "No decision signal means NOT_ENOUGH_SIGNAL."},
    )
    scope = AssessmentScope(
        target_id=uuid4(), role_profile_id=uuid4(), role_family_key="business_analysis",
        round_key="business_problem_solving", round_label="Working through a business case", question_family="case_discussion",
        taxonomy_version=1, catalog_version=1, rubric_key="business_case_v1",
        rubric_version="assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1",
        competency_keys=("structured_problem_solving", "quantitative_reasoning", "business_judgement"),
        assessor_types=(AssessorType.TECHNICAL,), provenance_class="MIRROR_GENERATED",
        dimensions=dimensions,
        questions=(AssessmentQuestionContext(position=1, template_id="case.cafe_profit", family_key="profit_diagnosis", competency_key="structured_problem_solving", question_family="case_discussion", text="How would you structure the problem?"),),
    )
    quote = "I designed the data model."
    domains = [
        DomainAssessment(
            domain=key, status=SpecialistStatus.COMPLETE, signal_strength=SignalStrength.MODERATE,
            confidence=0.8, evidence_turn_ids=[TURN_ID],
            evidence_quotes=[AssessmentEvidence(turn_id=TURN_ID, quote=quote)],
            reason_summary="You showed a reasoned approach in this answer.",
        )
        for key in scope.competency_keys
    ]
    domains.append(DomainAssessment(
        domain="coding_quality", status=SpecialistStatus.COMPLETE,
        signal_strength=SignalStrength.MODERATE, confidence=0.8,
        evidence_turn_ids=[TURN_ID], evidence_quotes=[AssessmentEvidence(turn_id=TURN_ID, quote=quote)],
        reason_summary="You showed a reasoned approach in this answer.",
    ))
    invalid_output = SpecialistAssessmentOutput(
        assessor_type=AssessorType.TECHNICAL, status=SpecialistStatus.COMPLETE,
        dimensions=[], competency_or_domain_assessments=domains,
        signal_strength=SignalStrength.MODERATE, confidence=0.8,
        evidence_turn_ids=[TURN_ID], evidence_quotes=[AssessmentEvidence(turn_id=TURN_ID, quote=quote)],
        reason_summary="You showed a reasoned approach in this answer.",
    )

    class ScopedRepository:
        def __init__(self):
            self.stored = []

        async def get_latest(self, session_id, user_id, kind):
            return None

        async def load_context(self, session_id, user_id, kind):
            if kind != AssessorType.TECHNICAL:
                return None
            return SpecialistAssessmentContext(
                session_id=session_id, assessor_type=kind, assessment_scope=scope,
                transcript_turns=[AssessmentTranscriptTurn(id=TURN_ID, speaker="CANDIDATE", text=quote, turn_type="DEPTH_PROBE", phase="ROLE_CORE")],
                rubric_version=scope.rubric_version,
            )

        async def store(self, session_id, kind, status, result, model, model_version, prompt_version, rubric_version):
            stored = StoredSpecialistAssessment(
                id=uuid4(), session_id=session_id, assessor_type=kind, status=status,
                result_json=result, model=model, model_version=model_version,
                prompt_version=prompt_version, rubric_version=rubric_version, created_at=datetime.now(UTC),
            )
            self.stored.append(stored)
            return stored

    repo = ScopedRepository()
    runners = {kind: Runner(output(kind)) for kind in AssessorType}
    scoped_runners: dict[AssessorType, Any] = {AssessorType.TECHNICAL: Runner(invalid_output)}
    with pytest.raises(SpecialistAssessmentRejected):
        asyncio.run(AssessmentOrchestrator(cast(Any, repo), cast(Any, runners), cast(Any, None), scoped_runners=scoped_runners).assess(SESSION_ID, USER_ID))
    assert repo.stored == []


def test_not_enough_signal_is_preserved_without_forced_score():
    orchestrated, _ = orchestrator(
        output(AssessorType.TECHNICAL, status=SpecialistStatus.NOT_ENOUGH_SIGNAL),
        output(AssessorType.BEHAVIOUR), output(AssessorType.CLAIMS),
    )
    bundle = asyncio.run(orchestrated.assess(SESSION_ID, USER_ID))
    assert bundle.technical.status == SpecialistStatus.NOT_ENOUGH_SIGNAL
    assert bundle.disagreements


def test_not_enough_signal_dimension_cannot_keep_evidence_or_quotes():
    with pytest.raises(ValueError):
        DomainAssessment(
            domain="quantitative_reasoning",
            status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
            signal_strength=SignalStrength.NONE,
            confidence=0.2,
            evidence_turn_ids=[TURN_ID],
            evidence_quotes=[AssessmentEvidence(turn_id=TURN_ID, quote="I designed the data model.")],
            reason_summary="There is not enough signal for this dimension.",
        )


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


def test_every_registered_specialist_resolves_its_versioned_prompt():
    loader = PromptLoader()
    for assessor_type in AssessorType:
        agent = create_specialist_assessor(assessor_type, "test-model")
        assert loader.load(agent.name, agent.prompt_version)




def test_round_scoped_technical_prompt_is_versioned_and_contract_bounded():
    agent = create_specialist_assessor(AssessorType.TECHNICAL, "test-model", prompt_version="v2")
    prompt = PromptLoader().load(agent.name, agent.prompt_version)
    assert "assessment_scope" in prompt
    assert "competency_or_domain_assessments" in prompt
    assert "NOT_ENOUGH_SIGNAL" in prompt
    assert "MIRROR_GENERATED" in prompt
    assert "company" in prompt.casefold()


def test_scoped_cache_with_catalog_only_pin_is_regenerated_under_exact_round_pin():
    keys = ("structured_problem_solving", "quantitative_reasoning", "business_judgement")
    contract_version = "assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1"
    quote = "I would split the problem into price, volume, and cost."
    dimensions = tuple(
        {"competency_key": key, "title": key, "criteria": "Use the round-specific case criterion.", "insufficient_signal": "If no direct answer signal is available, use NOT_ENOUGH_SIGNAL."}
        for key in keys
    )
    scope = AssessmentScope(
        target_id=uuid4(), role_profile_id=uuid4(), role_family_key="business_analysis",
        round_key="business_problem_solving", round_label="Working through a business case",
        question_family="case_discussion", taxonomy_version=1, catalog_version=1,
        rubric_key="business_case_v1", rubric_version=contract_version,
        competency_keys=keys, assessor_types=(AssessorType.TECHNICAL,),
        provenance_class="MIRROR_GENERATED", dimensions=dimensions,
        questions=(AssessmentQuestionContext(
            position=1, template_id="case.cafe_profit", family_key="profit_diagnosis",
            competency_key=keys[0], question_family="case_discussion", text="How would you structure the problem?",
        ),),
    )
    not_enough = SpecialistAssessmentOutput(
        assessor_type=AssessorType.TECHNICAL, status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
        competency_or_domain_assessments=[
            DomainAssessment(domain=key, status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
                signal_strength=SignalStrength.NONE, confidence=0.2,
                reason_summary="There is not enough signal yet.")
            for key in keys
        ],
        signal_strength=SignalStrength.NONE, confidence=0.2,
        reason_summary="There is not enough signal yet.",
    )
    cached = StoredSpecialistAssessment(
        id=uuid4(), session_id=SESSION_ID, assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.NOT_ENOUGH_SIGNAL, result_json=not_enough,
        model="mock", model_version="mock", prompt_version="v2",
        rubric_version="assessment-rubrics-1", created_at=datetime.now(UTC),
    )

    class CountingRunner(Runner):
        def __init__(self):
            super().__init__(not_enough)
            self.calls = 0

        async def run(self, *args, **kwargs):
            self.calls += 1
            return await super().run(*args, **kwargs)

    class CachedRepository:
        def __init__(self):
            self.stored = []

        async def get_latest(self, session_id, user_id, kind):
            return cached if kind == AssessorType.TECHNICAL else None

        async def load_context(self, session_id, user_id, kind):
            if kind != AssessorType.TECHNICAL:
                return None
            return SpecialistAssessmentContext(
                session_id=session_id, assessor_type=kind, assessment_scope=scope,
                transcript_turns=[AssessmentTranscriptTurn(
                    id=TURN_ID, speaker="CANDIDATE", text=quote,
                    turn_type="DEPTH_PROBE", phase="ROLE_CORE",
                )],
                rubric_version=contract_version,
            )

        async def store(self, session_id, kind, status, result, model, model_version, prompt_version, rubric_version):
            stored = StoredSpecialistAssessment(
                id=uuid4(), session_id=session_id, assessor_type=kind, status=status,
                result_json=result, model=model, model_version=model_version,
                prompt_version=prompt_version, rubric_version=rubric_version,
                created_at=datetime.now(UTC),
            )
            self.stored.append(stored)
            return stored

    repository = CachedRepository()
    runner = CountingRunner()
    legacy_runners: dict[AssessorType, Any] = {kind: Runner(output(kind)) for kind in AssessorType}
    scoped_runners: dict[AssessorType, Any] = {AssessorType.TECHNICAL: runner}
    bundle = asyncio.run(AssessmentOrchestrator(
        cast(Any, repository), legacy_runners, cast(Any, None),
        scoped_runners=scoped_runners,
    ).assess(SESSION_ID, USER_ID))

    assert runner.calls == 1
    assert repository.stored[0].rubric_version == contract_version
    assert bundle.technical is not None and bundle.technical.id != cached.id


def test_p2_p4_p5_p6_p7_expectations_are_representable_without_verdicts():
    # P2/P4 may have complete technical but insufficient behavioural signal;
    # P5 claims stays descriptive; P6 ownership can weaken; P7 can be complete.
    assert output(AssessorType.TECHNICAL).status == SpecialistStatus.COMPLETE
    assert output(AssessorType.BEHAVIOUR, status=SpecialistStatus.NOT_ENOUGH_SIGNAL).signal_strength == SignalStrength.NONE
    assert "dishonest" in (Path(__file__).parents[3] / "apps/api/app/prompts/assessor/claims/v1.md").read_text().casefold()

