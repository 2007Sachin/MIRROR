from __future__ import annotations

from .specialist_assessor_models import AssessorType, SignalStrength, SpecialistStatus
from .verdict_models import AggregatedAssessment, RootCauseCode, VerdictCode


class FinalAssessmentAggregator:
    """Deterministic score/range authority; no LLM participates here."""
    def __init__(self, *, low_signal_half_width: int = 18, high_signal_half_width: int = 4) -> None:
        self._low_width = low_signal_half_width
        self._high_width = high_signal_half_width

    def aggregate(self, bundle) -> AggregatedAssessment:
        rows = {AssessorType.TECHNICAL: bundle.technical, AssessorType.BEHAVIOUR: bundle.behaviour, AssessorType.CLAIMS: bundle.claims}
        values = {kind: self._value(rows[kind]) for kind in rows}
        confidence = sum(row is not None and row.status == SpecialistStatus.COMPLETE for row in rows.values()) / 3
        role = round(values[AssessorType.TECHNICAL] * .7 + values[AssessorType.CLAIMS] * .3, 1)
        interview = round(values[AssessorType.BEHAVIOUR] * .7 + values[AssessorType.CLAIMS] * .3, 1)
        width = round(self._low_width - (self._low_width - self._high_width) * confidence)
        verdict = self._verdict(role, interview, confidence)
        root = self._root_cause(values)
        return AggregatedAssessment(
            role_readiness_internal=role, interview_readiness_internal=interview,
            role_readiness_low=max(0, round(role-width)), role_readiness_high=min(100, round(role+width)),
            interview_readiness_low=max(0, round(interview-width)), interview_readiness_high=min(100, round(interview+width)),
            overall_signal_confidence=confidence,
            availability_status="AVAILABLE" if confidence >= 2/3 else "LIMITED_SIGNAL",
            verdict_code=verdict, root_cause_code=root,
        )

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

