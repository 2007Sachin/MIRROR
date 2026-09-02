from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import httpx

from .claim_resolution_models import ClaimResolutionRecord, ResolutionTriggerType
from .claims_models import ClaimRead, ClaimStatus
from .claims_repository import SupabaseClaimsGraphRepository, _claim
from .config import Settings


class ConcurrentClaimResolution(Exception):
    pass


class ClaimResolutionPersistenceError(Exception):
    pass


class ClaimResolutionRepository(Protocol):
    async def get_claim(self, claim_id: UUID, user_id: UUID) -> ClaimRead | None: ...
    async def commit(
        self, claim_id: UUID, user_id: UUID, expected_status: ClaimStatus,
        new_status: ClaimStatus, reason: str, evidence_ids: list[UUID],
        trigger_type: ResolutionTriggerType, confidence: float,
    ) -> tuple[ClaimRead, ClaimResolutionRecord]: ...
    async def list_claims(self, user_id: UUID) -> list[ClaimRead]: ...


class SupabaseClaimResolutionRepository(SupabaseClaimsGraphRepository):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)

    async def commit(
        self, claim_id: UUID, user_id: UUID, expected_status: ClaimStatus,
        new_status: ClaimStatus, reason: str, evidence_ids: list[UUID],
        trigger_type: ResolutionTriggerType, confidence: float,
    ) -> tuple[ClaimRead, ClaimResolutionRecord]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/rpc/resolve_claim_state",
                    headers=self._headers,
                    json={
                "p_claim_id": str(claim_id), "p_user_id": str(user_id),
                "p_expected_status": expected_status.value.lower(),
                "p_new_status": new_status.value.lower(), "p_reason": reason,
                "p_evidence_ids": [str(item) for item in evidence_ids],
                "p_trigger_type": trigger_type.value, "p_confidence": confidence,
                    },
                )
                if response.is_error:
                    message = response.text
                    if "claim_resolution_conflict" in message:
                        raise ConcurrentClaimResolution
                    raise ClaimResolutionPersistenceError("claim resolution was rejected")
                body = response.json()
                rows = body if isinstance(body, list) else [body]
        except ConcurrentClaimResolution:
            raise
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise ClaimResolutionPersistenceError from exc
        if not rows:
            raise ConcurrentClaimResolution
        payload: dict[str, Any] = rows[0]
        return _claim(payload["claim"]), ClaimResolutionRecord.model_validate({
            **payload["resolution"],
            "previous_status": str(payload["resolution"]["previous_status"]).upper(),
            "new_status": str(payload["resolution"]["new_status"]).upper(),
        })

    async def list_claims(self, user_id: UUID) -> list[ClaimRead]:
        return await super().list_claims(user_id)

