from __future__ import annotations

from .specialist_assessor_models import AssessorType, SignalStrength, SpecialistStatus
from .verdict_models import AggregatedAssessment, RootCauseCode, VerdictCode


class FinalAssessmentAggregator:
    """Deterministic score/range authority; no LLM participates here."""
    def __init__(self, *, low_signal_half_width: int = 18, high_signal_half_width: int = 4) -> None:
        self._low_width = low_signal_half_width
        self._high_width = high_signal_half_width

    def aggregate(self, bundle) -> AggregatedAssessment:
        scope = getattr(bundle, "assessment_scope", None)
        if scope is not None:
            return self._aggregate_round_scoped(bundle)
        # A missing row (never produced, rejected by B5 evidence validation, or
        # otherwise unverifiable) is UNKNOWN: it is excluded from the weighted
        # score instead of being scored as weakness, and lowers confidence only.
        rows = {AssessorType.TECHNICAL: bundle.technical, AssessorType.BEHAVIOUR: bundle.behaviour, AssessorType.CLAIMS: bundle.claims}
        values = {kind: self._value(rows[kind]) for kind in rows}
        confidence = sum(row is not None and row.status == SpecialistStatus.COMPLETE for row in rows.values()) / 3
        role = self._weighted(((values[AssessorType.TECHNICAL], .7, rows[AssessorType.TECHNICAL]), (values[AssessorType.CLAIMS], .3, rows[AssessorType.CLAIMS])))
        interview = self._weighted(((values[AssessorType.BEHAVIOUR], .7, rows[AssessorType.BEHAVIOUR]), (values[AssessorType.CLAIMS], .3, rows[AssessorType.CLAIMS])))
        width = round(self._low_width - (self._low_width - self._high_width) * confidence)
        verdict = self._verdict(role, interview, confidence)
        root = self._root_cause({k: v for k, v in values.items() if rows[k] is not None} or values)
        return AggregatedAssessment(
            role_readiness_internal=role, interview_readiness_internal=interview,
            role_readiness_low=max(0, round(role-width)), role_readiness_high=min(100, round(role+width)),
            interview_readiness_low=max(0, round(interview-width)), interview_readiness_high=min(100, round(interview+width)),
            overall_signal_confidence=confidence,
            availability_status="AVAILABLE" if confidence >= 2/3 else "LIMITED_SIGNAL",
            verdict_code=verdict, root_cause_code=root,
            rubric_version="v1",
        )

    # Scoped practice feedback is intentionally not a global readiness aggregate.
    def _aggregate_round_scoped(self, bundle) -> AggregatedAssessment:
        scope = bundle.assessment_scope
        rows = {
            AssessorType.TECHNICAL: bundle.technical,
            AssessorType.BEHAVIOUR: bundle.behaviour,
            AssessorType.CLAIMS: bundle.claims,
        }
        selected_rows = [rows[kind] for kind in scope.assessor_types]
        if not selected_rows or any(row is None for row in selected_rows):
            raise ValueError("round-scoped assessment is missing a required specialist result")
        dimensions = {}
        for row in selected_rows:
            for dimension in row.result_json.competency_or_domain_assessments:
                if dimension.domain not in scope.competency_keys or dimension.domain in dimensions:
                    raise ValueError("round-scoped aggregate contains an unapproved or duplicate competency")
                dimensions[dimension.domain] = dimension
        if tuple(dimensions) != scope.competency_keys:
            raise ValueError("round-scoped aggregate does not contain the exact selected competencies")
        available_dimensions = [
            dimension for dimension in dimensions.values()
            if dimension.status == SpecialistStatus.COMPLETE
        ]
        confidence = (
            sum(dimension.confidence for dimension in available_dimensions) / len(available_dimensions)
            if available_dimensions else 0.0
        )
        return AggregatedAssessment(
            role_readiness_internal=None,
            interview_readiness_internal=None,
            role_readiness_low=None,
            role_readiness_high=None,
            interview_readiness_low=None,
            interview_readiness_high=None,
            overall_signal_confidence=confidence,
            availability_status="ROUND_SCOPED",
            verdict_code=VerdictCode.PRACTICE_ONLY,
            root_cause_code=RootCauseCode.NOT_APPLICABLE,
            rubric_version=scope.rubric_version,
        )

    @staticmethod
    def _weighted(parts) -> float:
        known = [(value, weight) for value, weight, row in parts if row is not None]
        if not known:  # no verified input: unchanged legacy floor; confidence is 0 so the range stays widest and availability LIMITED_SIGNAL
            return 25
        total = sum(weight for _, weight in known)
        return round(sum(value * weight for value, weight in known) / total, 1)

    @staticmethod
    def _value(row) -> float:
        if row is None or row.status == SpecialistStatus.NOT_ENOUGH_SIGNAL: return 25
        return {SignalStrength.NONE: 25, SignalStrength.WEAK: 40, SignalStrength.MODERATE: 62, SignalStrength.STRONG: 82}[row.result_json.signal_strength]
    @staticmethod
    def _verdict(role, interview, confidence):
        score=min(role, interview)
        if confidence < 1/3 or score < 40: return VerdictCode.NOT_READY_YET
        if score < 55: return VerdictCode.DEVELOPING
        if score < 68: return VerdictCode.NEAR_READY
        if score < 82: return VerdictCode.READY
        return VerdictCode.STRONG
    @staticmethod
    def _root_cause(values):
        weakest=min(values, key=values.get)
        return {AssessorType.TECHNICAL: RootCauseCode.TECHNICAL_DEPTH, AssessorType.BEHAVIOUR: RootCauseCode.ANSWER_STRUCTURE, AssessorType.CLAIMS: RootCauseCode.OWNERSHIP_SPECIFICITY}[weakest]

