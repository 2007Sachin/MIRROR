from __future__ import annotations

from .assessment_adjudication_models import AssessmentDisagreement
from .specialist_assessor_models import (
    AssessorType, SignalStrength, SpecialistAssessmentBundle, SpecialistStatus,
)


class AssessmentDisagreementDetector:
    """Deterministic gate; the model never decides whether to invoke itself."""

    def __init__(self, *, material_signal_gap: int = 2) -> None:
        if material_signal_gap < 1 or material_signal_gap > 3:
            raise ValueError("material signal gap must be between one and three")
        self._gap = material_signal_gap

    def detect(self, bundle: SpecialistAssessmentBundle) -> list[AssessmentDisagreement]:
        results = {
            AssessorType.TECHNICAL: bundle.technical,
            AssessorType.BEHAVIOUR: bundle.behaviour,
            AssessorType.CLAIMS: bundle.claims,
        }
        available = {kind: row for kind, row in results.items() if row is not None}
        found: list[AssessmentDisagreement] = []
        technical, claims = available.get(AssessorType.TECHNICAL), available.get(AssessorType.CLAIMS)
        if technical and claims and self._material_gap(technical.result_json.signal_strength, claims.result_json.signal_strength):
            found.append(AssessmentDisagreement(
                affected_dimension="technical_understanding_and_claim_ownership",
                specialist_positions={"TECHNICAL": technical.result_json.reason_summary, "CLAIMS": claims.result_json.reason_summary},
                reason="Technical and claims evidence have a material signal-strength gap.",
            ))
        technical, behaviour = available.get(AssessorType.TECHNICAL), available.get(AssessorType.BEHAVIOUR)
        if technical and behaviour and technical.status != behaviour.status:
            found.append(AssessmentDisagreement(
                affected_dimension="signal_availability",
                specialist_positions={"TECHNICAL": technical.status.value, "BEHAVIOUR": behaviour.status.value},
                reason="Specialist signal availability conflicts and needs interpretation.",
            ))
        return found

    def _material_gap(self, left: SignalStrength, right: SignalStrength) -> bool:
        rank = {SignalStrength.NONE: 0, SignalStrength.WEAK: 1, SignalStrength.MODERATE: 2, SignalStrength.STRONG: 3}
        return abs(rank[left] - rank[right]) >= self._gap

