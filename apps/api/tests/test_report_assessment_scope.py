from __future__ import annotations

import pytest
from typing import Any, cast
from uuid import UUID, uuid4

from app.report_service import ReportService, ReportUnavailable
from app.role_progress import build_progress, eligible_practices, practice_items
from app.specialist_assessor_models import (
    AssessmentEvidence,
    AssessmentQuestionContext,
    AssessmentScope,
    AssessorType,
    DomainAssessment,
    SignalStrength,
    SpecialistAssessmentOutput,
    SpecialistStatus,
)
from tests.test_report import RESULT, SESSION, TURN, USER, FakeReportRepository, session
from tests.test_role_progress import profile as progress_profile, session as progress_session

CASE_KEYS = ("structured_problem_solving", "quantitative_reasoning", "business_judgement")


def case_scope() -> AssessmentScope:
    return AssessmentScope(
        target_id=uuid4(),
        role_profile_id=uuid4(),
        role_family_key="business_analysis",
        round_key="business_problem_solving",
        round_label="Working through a business case",
        question_family="case_discussion",
        taxonomy_version=1,
        catalog_version=1,
        rubric_key="business_case_v1",
        rubric_version="assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1",
        competency_keys=CASE_KEYS,
        assessor_types=(AssessorType.TECHNICAL,),
        provenance_class="MIRROR_GENERATED",
        dimensions=tuple(
            {"competency_key": key, "title": title, "criteria": "A case-relevant evaluation criterion.", "insufficient_signal": "When no answer evidence is available, mark NOT_ENOUGH_SIGNAL."}
            for key, title in zip(CASE_KEYS, ("Structured problem solving", "Quantitative reasoning", "Business judgment"))
        ),
        questions=(AssessmentQuestionContext(
            position=1,
            template_id="case.cafe_profit",
            family_key="profit_diagnosis",
            competency_key=CASE_KEYS[0],
            question_family="case_discussion",
            text="How would you structure this case?",
        ),),
    )


def specialist(kind: AssessorType, keys: tuple[str, ...], rubric_version: str) -> dict:
    output = SpecialistAssessmentOutput(
        assessor_type=kind,
        status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
        competency_or_domain_assessments=[
            DomainAssessment(
                domain=key,
                status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
                signal_strength=SignalStrength.NONE,
                confidence=0.2,
                reason_summary="There is not enough signal yet.",
            )
            for key in keys
        ],
        signal_strength=SignalStrength.NONE,
        confidence=0.2,
        reason_summary="There is not enough signal yet.",
    )
    return {"assessor_type": kind.value, "status": output.status.value, "rubric_version": rubric_version, "result_json": output.model_dump(mode="json")}


class ScopedReportRepository(FakeReportRepository):
    def __init__(self, scope: AssessmentScope, *, result: dict, current):
        super().__init__(
            current=current,
            result=result,
            specialists=[
                specialist(AssessorType.TECHNICAL, CASE_KEYS, scope.rubric_version),
                specialist(AssessorType.BEHAVIOUR, ("communication",), scope.rubric_version),
                specialist(AssessorType.CLAIMS, ("ownership",), scope.rubric_version),
            ],
        )
        self.scope = scope
        self.scope_lookup = None

    async def get_target_assessment_scope(
        self, session_id: UUID, user_id: UUID, session_role_profile_id: UUID | None,
    ) -> AssessmentScope | None:
        self.scope_lookup = (session_id, user_id, session_role_profile_id)
        return self.scope


@pytest.mark.asyncio
async def test_case_report_shows_only_round_scoped_practice_feedback() -> None:
    scope = case_scope()
    current = session().model_copy(update={"role_profile_id": scope.role_profile_id})
    repository = ScopedReportRepository(
        scope,
        result={**RESULT, "assessment_confidence": 0.0, "rubric_version": scope.rubric_version, "verdict_code": "PRACTICE_ONLY", "root_cause_code": "NOT_APPLICABLE", "availability_status": "ROUND_SCOPED", "role_readiness_low": None, "role_readiness_high": None, "interview_readiness_low": None, "interview_readiness_high": None, "summary": "This reflection covers this practice round only."},
        current=current,
    )

    report = await ReportService(repository).get_report(SESSION, USER)

    assert report.assessment_scope is not None
    assert report.assessment_scope.round_label == "Working through a business case"
    assert report.assessment_scope.provenance_class == "MIRROR_GENERATED"
    assert set(report.assessment_scope.model_dump()) == {"round_label", "competency_titles", "provenance_class"}
    assert report.role_readiness.low is None and report.role_readiness.high is None
    assert report.interview_readiness.low is None and report.interview_readiness.high is None
    assert report.role_readiness.label == "Not enough to say yet"
    assert report.interview_readiness.label == "Not enough to say yet"
    assert report.role_readiness.signal_strength == "NONE"
    assert report.interview_readiness.signal_strength == "NONE"
    assert report.verdict.label == "Practice only"
    assert "practice round only" in report.verdict.summary.casefold()
    assert report.root_cause == "NOT_APPLICABLE"
    assert {item.skill for item in report.skill_assessments} == set(CASE_KEYS)
    assert repository.scope_lookup == (SESSION, USER, scope.role_profile_id)


@pytest.mark.asyncio
async def test_case_report_marks_available_round_signal_as_practice_only() -> None:
    scope = case_scope()
    current = session().model_copy(update={"role_profile_id": scope.role_profile_id})
    repository = ScopedReportRepository(
        scope,
        result={
            **RESULT,
            "assessment_confidence": 0.8,
            "rubric_version": scope.rubric_version,
            "verdict_code": "PRACTICE_ONLY",
            "root_cause_code": "NOT_APPLICABLE",
            "availability_status": "ROUND_SCOPED",
        },
        current=current,
    )
    quote = "I would separate the problem into price, volume, and cost."
    repository.turn_rows = [{"id": TURN, "speaker": "CANDIDATE", "text": quote, "turn_index": 0}]
    domain_rows = [
        DomainAssessment(
            domain=key,
            status=SpecialistStatus.COMPLETE if key == CASE_KEYS[0] else SpecialistStatus.NOT_ENOUGH_SIGNAL,
            signal_strength=SignalStrength.MODERATE if key == CASE_KEYS[0] else SignalStrength.NONE,
            confidence=0.8 if key == CASE_KEYS[0] else 0.2,
            evidence_turn_ids=[TURN] if key == CASE_KEYS[0] else [],
            evidence_quotes=[AssessmentEvidence(turn_id=TURN, quote=quote)] if key == CASE_KEYS[0] else [],
            reason_summary="You showed a reasoned approach here." if key == CASE_KEYS[0] else "There is not enough signal yet.",
        )
        for key in CASE_KEYS
    ]
    output = SpecialistAssessmentOutput(
        assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.COMPLETE,
        competency_or_domain_assessments=domain_rows,
        signal_strength=SignalStrength.MODERATE,
        confidence=0.8,
        evidence_turn_ids=[TURN],
        evidence_quotes=[AssessmentEvidence(turn_id=TURN, quote=quote)],
        reason_summary="This practice round has signal in one dimension.",
    )
    repository.specialists[0]["status"] = SpecialistStatus.COMPLETE.value
    repository.specialists[0]["result_json"] = output.model_dump(mode="json")

    report = await ReportService(repository).get_report(SESSION, USER)

    assert report.role_readiness.label == "This practice only"
    assert report.interview_readiness.label == "This practice only"
    assert report.role_readiness.low is None and report.role_readiness.high is None
    assert {item.status for item in report.skill_assessments} == {
        SpecialistStatus.COMPLETE.value,
        SpecialistStatus.NOT_ENOUGH_SIGNAL.value,
    }


@pytest.mark.asyncio
async def test_report_fails_closed_when_repository_cannot_resolve_target_scope() -> None:
    class RepositoryWithoutScopeReader:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def __getattr__(self, name):
            if name == "get_target_assessment_scope":
                raise AttributeError(name)
            return getattr(self._wrapped, name)

    wrapped = FakeReportRepository(result=RESULT)

    with pytest.raises(ReportUnavailable):
        await ReportService(cast(Any, RepositoryWithoutScopeReader(wrapped))).get_report(SESSION, USER)


@pytest.mark.asyncio
async def test_case_report_fails_closed_when_persisted_rubric_pin_differs() -> None:
    scope = case_scope()
    current = session().model_copy(update={"role_profile_id": scope.role_profile_id})
    repository = ScopedReportRepository(scope, result={**RESULT, "rubric_version": "v1"}, current=current)

    with pytest.raises(ReportUnavailable):
        await ReportService(repository).get_report(SESSION, USER)


@pytest.mark.asyncio
async def test_case_report_fails_closed_when_specialist_rubric_pin_differs() -> None:
    scope = case_scope()
    current = session().model_copy(update={"role_profile_id": scope.role_profile_id})
    repository = ScopedReportRepository(
        scope,
        result={**RESULT, "rubric_version": scope.rubric_version},
        current=current,
    )
    repository.specialists[0]["rubric_version"] = "assessment-rubrics-1"

    with pytest.raises(ReportUnavailable):
        await ReportService(repository).get_report(SESSION, USER)


@pytest.mark.asyncio
async def test_target_round_theme_and_result_stay_on_the_same_progress_item() -> None:
    scope = case_scope()
    current = session().model_copy(update={"role_profile_id": scope.role_profile_id})
    repository = ScopedReportRepository(
        scope,
        result={
            **RESULT,
            "rubric_version": scope.rubric_version,
            "verdict_code": "PRACTICE_ONLY",
            "root_cause_code": "NOT_APPLICABLE",
            "availability_status": "ROUND_SCOPED",
            "role_readiness_low": None,
            "role_readiness_high": None,
            "interview_readiness_low": None,
            "interview_readiness_high": None,
            "summary": "This reflection covers this practice round only.",
        },
        current=current,
    )
    report = await ReportService(repository).get_report(SESSION, USER)
    practice_session = progress_session(scope.role_profile_id, days_ago=1).model_copy(
        update={"id": SESSION, "practice_theme": scope.round_label}
    )
    practices = practice_items(eligible_practices([practice_session], frozenset({scope.role_profile_id})))
    role = progress_profile(USER).model_copy(update={"id": scope.role_profile_id})

    progress = build_progress(role, practices, {SESSION: report})

    assert progress.practice_count == 1
    assert progress.practices[0].session_id == SESSION
    assert progress.practices[0].practice_theme == scope.round_label
    assert all(dimension.state.value == "NOT_EXPLORED" for dimension in progress.dimensions)


@pytest.mark.asyncio
async def test_case_report_rejects_generic_dimensions_even_when_case_dimensions_are_present() -> None:
    scope = case_scope()
    current = session().model_copy(update={"role_profile_id": scope.role_profile_id})
    repository = ScopedReportRepository(
        scope,
        result={**RESULT, "rubric_version": scope.rubric_version},
        current=current,
    )
    generic = DomainAssessment(
        domain="communication",
        status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
        signal_strength=SignalStrength.NONE,
        confidence=0.2,
        reason_summary="There is not enough signal yet.",
    )
    case_domains = [
        DomainAssessment(
            domain=key,
            status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
            signal_strength=SignalStrength.NONE,
            confidence=0.2,
            reason_summary="There is not enough signal yet.",
        )
        for key in CASE_KEYS
    ]
    output = SpecialistAssessmentOutput(
        assessor_type=AssessorType.TECHNICAL,
        status=SpecialistStatus.NOT_ENOUGH_SIGNAL,
        dimensions=[generic],
        competency_or_domain_assessments=case_domains,
        signal_strength=SignalStrength.NONE,
        confidence=0.2,
        reason_summary="There is not enough signal yet.",
    )
    repository.specialists = [{"assessor_type": "TECHNICAL", "result_json": output.model_dump(mode="json")}]

    with pytest.raises(ReportUnavailable):
        await ReportService(repository).get_report(SESSION, USER)


@pytest.mark.asyncio
async def test_case_report_converts_malformed_scope_metadata_to_unavailable() -> None:
    scope = case_scope()
    current = session().model_copy(update={"role_profile_id": scope.role_profile_id})
    repository = ScopedReportRepository(scope, result={**RESULT, "rubric_version": scope.rubric_version}, current=current)

    async def malformed_scope(
        session_id: UUID, user_id: UUID, session_role_profile_id: UUID | None,
    ) -> AssessmentScope | None:
        raise ValueError("malformed target contract")

    repository.get_target_assessment_scope = malformed_scope

    with pytest.raises(ReportUnavailable):
        await ReportService(repository).get_report(SESSION, USER)

