from __future__ import annotations

from uuid import UUID

from .claims_models import (
    ClaimChangedBy,
    ClaimCreate,
    ClaimEntityCreate,
    ClaimEntityRead,
    ClaimEvidenceCreate,
    ClaimEvidenceRead,
    ClaimGraphRead,
    ClaimRead,
    ClaimRelationCreate,
    ClaimRelationRead,
    ClaimSource,
    ClaimStatus,
    ClaimVersionCreate,
    ClaimVersionRead,
)
from .claims_repository import ClaimsGraphRepository


class ClaimNotFound(Exception):
    pass


class InvalidClaimStatusTransition(Exception):
    pass


class ClaimResolutionAuthorityRequired(Exception):
    pass


class ClaimsGraphService:
    """Ownership-scoped application boundary for the claims graph."""

    def __init__(self, repository: ClaimsGraphRepository) -> None:
        self._repository = repository

    async def get_claim(self, claim_id: UUID, user_id: UUID) -> ClaimGraphRead:
        result = await self._repository.get_graph(claim_id, user_id)
        if result is None:
            raise ClaimNotFound
        return result

    async def get_claims_for_user(
        self,
        user_id: UUID,
        *,
        skill: str | None = None,
        project: str | None = None,
        status: ClaimStatus | None = None,
        source: ClaimSource | None = None,
    ) -> list[ClaimRead]:
        return await self._repository.list_claims(
            user_id, skill=skill, project=project, status=status, source=source
        )

    async def get_claims_for_session(
        self, session_id: UUID, user_id: UUID
    ) -> list[ClaimRead]:
        return await self._repository.list_claims(user_id, session_id=session_id)

    async def get_claims_by_skill(self, skill: str, user_id: UUID) -> list[ClaimRead]:
        return await self._repository.list_claims(user_id, skill=skill)

    async def get_claims_by_project(
        self, project: str, user_id: UUID
    ) -> list[ClaimRead]:
        return await self._repository.list_claims(user_id, project=project)

    async def find_related_claims(
        self, claim_id: UUID, user_id: UUID
    ) -> list[ClaimRead]:
        await self._require_claim(claim_id, user_id)
        return await self._repository.find_related(claim_id, user_id)

    async def create_claim(
        self,
        user_id: UUID,
        claim: ClaimCreate,
        *,
        changed_by: ClaimChangedBy = ClaimChangedBy.SYSTEM,
        reason: str = "Claim created by application service",
    ) -> ClaimRead:
        return await self._repository.create_claim(user_id, claim, changed_by, reason)

    async def get_or_create_entity(
        self, user_id: UUID, entity: ClaimEntityCreate
    ) -> ClaimEntityRead:
        return await self._repository.get_or_create_entity(user_id, entity)

    async def create_relation(
        self, user_id: UUID, relation: ClaimRelationCreate
    ) -> ClaimRelationRead:
        return await self._repository.create_relation(user_id, relation)

    async def create_version(
        self, claim_id: UUID, user_id: UUID, version: ClaimVersionCreate
    ) -> ClaimVersionRead:
        await self._require_claim(claim_id, user_id)
        return await self._repository.create_version(claim_id, user_id, version)

    async def update_status(
        self,
        claim_id: UUID,
        user_id: UUID,
        new_status: ClaimStatus,
        changed_by: ClaimChangedBy,
        reason: str,
    ) -> ClaimRead:
        raise ClaimResolutionAuthorityRequired(
            "ClaimResolutionService is the only claim-status commit authority"
        )

    async def link_evidence(
        self, claim_id: UUID, user_id: UUID, evidence: ClaimEvidenceCreate
    ) -> ClaimEvidenceRead:
        await self._require_claim(claim_id, user_id)
        return await self._repository.link_evidence(claim_id, user_id, evidence)

    async def _require_claim(self, claim_id: UUID, user_id: UUID) -> ClaimRead:
        claim = await self._repository.get_claim(claim_id, user_id)
        if claim is None:
            raise ClaimNotFound
        return claim

