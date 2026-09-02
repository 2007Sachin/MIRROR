from __future__ import annotations

from typing import Any
from uuid import UUID

from .config import Settings
from .flag_activation import EligibleFlagCandidate
from .skeptic_repository import SkepticPersistenceUnavailable, SupabaseSkepticRepository


class SupabaseFlagActivationRepository(SupabaseSkepticRepository):
    """Service-role adapter for database-enforced flag eligibility and consumption."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    async def list_eligible(
        self,
        session_id: UUID,
        user_id: UUID,
        current_candidate_turn_index: int,
        min_confidence: float,
        allow_shadow: bool,
    ) -> list[EligibleFlagCandidate]:
        rows = await self._post(
            "rpc/get_eligible_skeptic_flags",
            {
                "p_session_id": str(session_id),
                "p_user_id": str(user_id),
                "p_current_candidate_turn_index": current_candidate_turn_index,
                "p_min_confidence": min_confidence,
                "p_allow_shadow": allow_shadow,
            },
        )
        return [self._candidate(row) for row in rows]

    async def consume(
        self,
        flag_id: UUID,
        session_id: UUID,
        user_id: UUID,
        current_candidate_turn_index: int,
        interviewer_turn_id: UUID,
        min_confidence: float,
        allow_shadow: bool,
    ) -> bool:
        rows = await self._post(
            "rpc/consume_skeptic_flag",
            {
                "p_flag_id": str(flag_id),
                "p_session_id": str(session_id),
                "p_user_id": str(user_id),
                "p_current_candidate_turn_index": current_candidate_turn_index,
                "p_interviewer_turn_id": str(interviewer_turn_id),
                "p_min_confidence": min_confidence,
                "p_allow_shadow": allow_shadow,
            },
        )
        if not rows:
            return False
        value: Any = rows[0]
        if isinstance(value, dict):
            value = value.get("consume_skeptic_flag", False)
        return bool(value)

    @staticmethod
    def _candidate(row: dict[str, Any]) -> EligibleFlagCandidate:
        try:
            return EligibleFlagCandidate.model_validate(
                {
                    **row,
                    "flag_type": str(row["flag_type"]).upper(),
                    "severity": str(row["severity"]).upper(),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SkepticPersistenceUnavailable("Eligible flag data is invalid") from exc

