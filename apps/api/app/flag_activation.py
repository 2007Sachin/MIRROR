from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .interviewer_models import InterviewerTurnType, PendingInterviewerFlag
from .skeptic_models import ObservationType, SkepticSeverity


class FlagActivationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EligibleFlagCandidate(FlagActivationModel):
    id: UUID
    claim_id: UUID | None = None
    flag_type: ObservationType
    severity: SkepticSeverity
    confidence: float = Field(ge=0, le=1)
    reason: str
    suggested_probe: str
    detected_at_turn: int = Field(ge=0)
    created_at: datetime
    claim_summary: str | None = None
    claim_verification_priority: str | None = None
    consumed: bool = False
    safe_to_surface: bool = True
    shadow_mode: bool = False
    disputed: bool = False
    resolved_at: datetime | None = None


class FlagActivationRepository(Protocol):
    async def list_eligible(
        self,
        session_id: UUID,
        user_id: UUID,
        current_candidate_turn_index: int,
        min_confidence: float,
        allow_shadow: bool,
    ) -> list[EligibleFlagCandidate]: ...

    async def consume(
        self,
        flag_id: UUID,
        session_id: UUID,
        user_id: UUID,
        current_candidate_turn_index: int,
        interviewer_turn_id: UUID,
        min_confidence: float,
        allow_shadow: bool,
    ) -> bool: ...


class FlagEligibilityService:
    """Selects one safe flag; prompts never decide activation eligibility."""

    def __init__(
        self,
        repository: FlagActivationRepository,
        *,
        live_probes: bool,
        shadow_mode: bool,
        min_confidence: float,
    ) -> None:
        if not 0 <= min_confidence <= 1:
            raise ValueError("Skeptic live-probe confidence must be between zero and one")
        self._repository = repository
        self._enabled = live_probes and not shadow_mode
        self._allow_shadow = self._enabled
        self._min_confidence = min_confidence

    async def select(
        self,
        session_id: UUID,
        user_id: UUID,
        current_candidate_turn_index: int,
        *,
        session_active: bool,
        probe_count: int,
        relevant_claim_ids: list[UUID],
    ) -> PendingInterviewerFlag | None:
        if not self._enabled or not session_active or probe_count >= 2:
            return None
        candidates = await self._repository.list_eligible(
            session_id,
            user_id,
            current_candidate_turn_index,
            self._min_confidence,
            self._allow_shadow,
        )
        # Repeat database eligibility checks in application code as defense in depth.
        candidates = [
            flag
            for flag in candidates
            if flag.detected_at_turn < current_candidate_turn_index
            and flag.confidence >= self._min_confidence
            and not flag.consumed
            and flag.safe_to_surface
            and (not flag.shadow_mode or self._allow_shadow)
            and not flag.disputed
            and flag.resolved_at is None
        ]
        if not candidates:
            return None
        relevant = set(relevant_claim_ids)
        winner = min(candidates, key=lambda flag: self._priority(flag, relevant))
        contradiction_types = {
            ObservationType.CONTRADICTION,
            ObservationType.OWNERSHIP_DRIFT,
        }
        return PendingInterviewerFlag(
            flag_id=winner.id,
            flag_type=winner.flag_type.value,
            claim_summary=winner.claim_summary,
            reason_summary=winner.reason,
            suggested_probe=winner.suggested_probe,
            recommended_turn_type=(
                InterviewerTurnType.CONTRADICTION_PROBE
                if winner.flag_type in contradiction_types
                else InterviewerTurnType.DEPTH_PROBE
            ),
            confidence_band=self._confidence_band(winner.confidence),
        )

    async def consume(
        self,
        flag_id: UUID,
        session_id: UUID,
        user_id: UUID,
        current_candidate_turn_index: int,
        interviewer_turn_id: UUID,
    ) -> bool:
        if not self._enabled:
            return False
        return await self._repository.consume(
            flag_id,
            session_id,
            user_id,
            current_candidate_turn_index,
            interviewer_turn_id,
            self._min_confidence,
            self._allow_shadow,
        )

    @staticmethod
    def _priority(
        flag: EligibleFlagCandidate, relevant_claim_ids: set[UUID]
    ) -> tuple[int, float, int, int, datetime, str]:
        severity = {SkepticSeverity.HIGH: 3, SkepticSeverity.MEDIUM: 2, SkepticSeverity.LOW: 1}
        verification = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        return (
            -severity[flag.severity],
            -flag.confidence,
            -(1 if flag.claim_id in relevant_claim_ids else 0),
            -verification.get((flag.claim_verification_priority or "").upper(), 0),
            flag.created_at,
            str(flag.id),
        )

    @staticmethod
    def _confidence_band(confidence: float) -> str:
        return "HIGH" if confidence >= 0.9 else "MEDIUM"

