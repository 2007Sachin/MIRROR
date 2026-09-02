from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.claims_models import (
    ClaimChangedBy,
    ClaimCreate,
    ClaimEntityCreate,
    ClaimEntityRead,
    ClaimEntityType,
    ClaimEvidenceCreate,
    ClaimEvidenceRead,
    ClaimEvidenceType,
    ClaimGraphRead,
    ClaimNodeType,
    ClaimRead,
    ClaimRelationCreate,
    ClaimRelationRead,
    ClaimRelationSource,
    ClaimRelationType,
    ClaimSource,
    ClaimStatus,
    ClaimType,
    ClaimVersionCreate,
    ClaimVersionRead,
    EvidenceDirection,
)
from app.claims_service import (
    ClaimNotFound,
    ClaimResolutionAuthorityRequired,
    ClaimsGraphService,
)
from app.dependencies import get_claims_graph_service
from app.main import app


USER_A = UUID("10000000-0000-4000-8000-000000000001")
USER_B = UUID("20000000-0000-4000-8000-000000000002")


class MemoryClaims:
    def __init__(self) -> None:
        self.claims: dict[UUID, ClaimRead] = {}
        self.entities: dict[UUID, ClaimEntityRead] = {}
        self.relations: dict[UUID, ClaimRelationRead] = {}
        self.versions: dict[UUID, list[ClaimVersionRead]] = {}
        self.evidence: dict[UUID, list[ClaimEvidenceRead]] = {}

    async def get_claim(self, claim_id: UUID, user_id: UUID) -> ClaimRead | None:
        claim = self.claims.get(claim_id)
        return claim if claim and claim.user_id == user_id else None

    async def list_claims(
        self,
        user_id: UUID,
        *,
        skill: str | None = None,
        project: str | None = None,
        status: ClaimStatus | None = None,
        source: ClaimSource | None = None,
        session_id: UUID | None = None,
    ) -> list[ClaimRead]:
        result = [claim for claim in self.claims.values() if claim.user_id == user_id]
        if status:
            result = [claim for claim in result if claim.status == status]
        if source:
            result = [claim for claim in result if claim.source == source]
        if session_id:
            result = [claim for claim in result if claim.session_id == session_id]
        for entity_type, value in (
            (ClaimEntityType.SKILL, skill),
            (ClaimEntityType.PROJECT, project),
        ):
            if value:
                ids = {
                    entity.id
                    for entity in self.entities.values()
                    if entity.user_id == user_id
                    and entity.entity_type == entity_type
                    and entity.canonical_name.casefold() == value.casefold()
                }
                claim_ids = {
                    relation.source_entity_id
                    for relation in self.relations.values()
                    if relation.user_id == user_id
                    and relation.source_entity_type == ClaimNodeType.CLAIM
                    and relation.target_entity_id in ids
                }
                result = [claim for claim in result if claim.id in claim_ids]
        return result

    async def create_claim(
        self,
        user_id: UUID,
        claim: ClaimCreate,
        changed_by: ClaimChangedBy,
        reason: str,
    ) -> ClaimRead:
        now = datetime.now(UTC)
        row = ClaimRead(
            id=uuid4(),
            user_id=user_id,
            status=ClaimStatus.UNVERIFIED,
            created_at=now,
            updated_at=now,
            **claim.model_dump(),
        )
        self.claims[row.id] = row
        await self.create_version(
            row.id,
            user_id,
            ClaimVersionCreate(
                new_state={"claim_text": row.claim_text, "status": row.status.value},
                changed_by=changed_by,
                reason=reason,
            ),
        )
        return row

    async def get_or_create_entity(
        self, user_id: UUID, entity: ClaimEntityCreate
    ) -> ClaimEntityRead:
        for existing in self.entities.values():
            if (
                existing.user_id == user_id
                and existing.entity_type == entity.entity_type
                and existing.canonical_name.casefold()
                == entity.canonical_name.casefold()
            ):
                return existing
        row = ClaimEntityRead(
            id=uuid4(),
            user_id=user_id,
            created_at=datetime.now(UTC),
            **entity.model_dump(),
        )
        self.entities[row.id] = row
        return row

    async def create_relation(
        self, user_id: UUID, relation: ClaimRelationCreate
    ) -> ClaimRelationRead:
        for node_type, node_id in (
            (relation.source_entity_type, relation.source_entity_id),
            (relation.target_entity_type, relation.target_entity_id),
        ):
            owner = (
                self.claims.get(node_id).user_id
                if node_type == ClaimNodeType.CLAIM and node_id in self.claims
                else self.entities.get(node_id).user_id
                if node_type == ClaimNodeType.ENTITY and node_id in self.entities
                else None
            )
            if owner != user_id:
                raise ClaimNotFound
        row = ClaimRelationRead(
            id=uuid4(),
            user_id=user_id,
            created_at=datetime.now(UTC),
            **relation.model_dump(),
        )
        self.relations[row.id] = row
        return row

    async def create_version(
        self, claim_id: UUID, user_id: UUID, version: ClaimVersionCreate
    ) -> ClaimVersionRead:
        if await self.get_claim(claim_id, user_id) is None:
            raise ClaimNotFound
        row = ClaimVersionRead(
            id=uuid4(),
            user_id=user_id,
            claim_id=claim_id,
            version=len(self.versions.get(claim_id, [])) + 1,
            created_at=datetime.now(UTC),
            **version.model_dump(),
        )
        self.versions.setdefault(claim_id, []).append(row)
        return row

    async def update_status(
        self,
        claim_id: UUID,
        user_id: UUID,
        status: ClaimStatus,
        changed_by: ClaimChangedBy,
        reason: str,
    ) -> ClaimRead:
        old = self.claims[claim_id]
        await self.create_version(
            claim_id,
            user_id,
            ClaimVersionCreate(
                previous_state={"status": old.status.value},
                new_state={"status": status.value},
                changed_by=changed_by,
                reason=reason,
            ),
        )
        updated = old.model_copy(
            update={"status": status, "updated_at": datetime.now(UTC)}
        )
        self.claims[claim_id] = updated
        return updated

    async def link_evidence(
        self, claim_id: UUID, user_id: UUID, evidence: ClaimEvidenceCreate
    ) -> ClaimEvidenceRead:
        if await self.get_claim(claim_id, user_id) is None:
            raise ClaimNotFound
        row = ClaimEvidenceRead(
            id=uuid4(),
            user_id=user_id,
            claim_id=claim_id,
            created_at=datetime.now(UTC),
            **evidence.model_dump(),
        )
        self.evidence.setdefault(claim_id, []).append(row)
        return row

    async def find_related(self, claim_id: UUID, user_id: UUID) -> list[ClaimRead]:
        anchors = {
            relation.target_entity_id
            for relation in self.relations.values()
            if relation.user_id == user_id and relation.source_entity_id == claim_id
        }
        ids = {
            relation.source_entity_id
            for relation in self.relations.values()
            if relation.user_id == user_id
            and relation.target_entity_id in anchors
            and relation.source_entity_id != claim_id
        }
        return [self.claims[item] for item in ids]

    async def get_graph(self, claim_id: UUID, user_id: UUID) -> ClaimGraphRead | None:
        claim = await self.get_claim(claim_id, user_id)
        if claim is None:
            return None
        relations = [
            row
            for row in self.relations.values()
            if row.user_id == user_id
            and claim_id in (row.source_entity_id, row.target_entity_id)
        ]
        entity_ids = {
            node_id
            for row in relations
            for node_type, node_id in (
                (row.source_entity_type, row.source_entity_id),
                (row.target_entity_type, row.target_entity_id),
            )
            if node_type == ClaimNodeType.ENTITY
        }
        return ClaimGraphRead(
            claim=claim,
            entities=[self.entities[item] for item in entity_ids],
            relations=relations,
            versions=self.versions.get(claim_id, []),
            evidence=self.evidence.get(claim_id, []),
            related_claims=await self.find_related(claim_id, user_id),
        )


def new_claim(text: str = "Built an SQL reporting pipeline") -> ClaimCreate:
    return ClaimCreate(
        claim_text=text,
        claim_type=ClaimType.SKILL,
        source=ClaimSource.RESUME,
        confidence=0.9,
    )


def make_graph() -> tuple[ClaimsGraphService, MemoryClaims]:
    repository = MemoryClaims()
    return ClaimsGraphService(repository), repository


def test_claim_creation_and_initial_version() -> None:
    service, repository = make_graph()
    claim = asyncio.run(service.create_claim(USER_A, new_claim()))
    assert claim.status == ClaimStatus.UNVERIFIED
    assert repository.versions[claim.id][0].changed_by == ClaimChangedBy.SYSTEM


def test_relation_creation_and_related_claims() -> None:
    service, _ = make_graph()
    first = asyncio.run(
        service.create_claim(USER_A, new_claim("Used SQL for reporting"))
    )
    second = asyncio.run(
        service.create_claim(USER_A, new_claim("Optimized SQL queries"))
    )
    skill = asyncio.run(
        service.get_or_create_entity(
            USER_A,
            ClaimEntityCreate(entity_type=ClaimEntityType.SKILL, canonical_name="SQL"),
        )
    )
    for claim in (first, second):
        asyncio.run(
            service.create_relation(
                USER_A,
                ClaimRelationCreate(
                    source_entity_type=ClaimNodeType.CLAIM,
                    source_entity_id=claim.id,
                    relation_type=ClaimRelationType.ABOUT_SKILL,
                    target_entity_type=ClaimNodeType.ENTITY,
                    target_entity_id=skill.id,
                    confidence=0.9,
                    source=ClaimRelationSource.RESUME_ANALYSIS,
                ),
            )
        )
    related = asyncio.run(service.find_related_claims(first.id, USER_A))
    assert [claim.id for claim in related] == [second.id]
    assert len(asyncio.run(service.get_claims_by_skill("sql", USER_A))) == 2


def test_generic_claim_service_cannot_commit_status() -> None:
    service, repository = make_graph()
    claim = asyncio.run(service.create_claim(USER_A, new_claim()))
    with pytest.raises(ClaimResolutionAuthorityRequired):
        asyncio.run(service.update_status(
            claim.id,
            USER_A,
            ClaimStatus.CORROBORATED,
            ClaimChangedBy.SYSTEM,
            "Supported by independently collected evidence",
        ))
    assert claim.status == ClaimStatus.UNVERIFIED
    assert [version.version for version in repository.versions[claim.id]] == [1]

    manual = asyncio.run(
        service.create_version(
            claim.id,
            USER_A,
            ClaimVersionCreate(
                previous_state={"status": ClaimStatus.UNVERIFIED.value},
                new_state={
                    "status": ClaimStatus.UNVERIFIED.value,
                    "note": "Candidate added context",
                },
                changed_by=ClaimChangedBy.USER,
                reason="Candidate supplied additional context",
            ),
        )
    )
    assert manual.version == 2
    assert repository.versions[claim.id][0].new_state["status"] == "UNVERIFIED"


def test_relation_rejects_cross_owner_nodes() -> None:
    service, _ = make_graph()
    claim = asyncio.run(service.create_claim(USER_A, new_claim()))
    other_skill = asyncio.run(
        service.get_or_create_entity(
            USER_B,
            ClaimEntityCreate(entity_type=ClaimEntityType.SKILL, canonical_name="SQL"),
        )
    )
    with pytest.raises(ClaimNotFound):
        asyncio.run(
            service.create_relation(
                USER_A,
                ClaimRelationCreate(
                    source_entity_type=ClaimNodeType.CLAIM,
                    source_entity_id=claim.id,
                    relation_type=ClaimRelationType.ABOUT_SKILL,
                    target_entity_type=ClaimNodeType.ENTITY,
                    target_entity_id=other_skill.id,
                    confidence=0.8,
                    source=ClaimRelationSource.APPLICATION,
                ),
            )
        )


def test_evidence_validation_and_linking() -> None:
    with pytest.raises(ValidationError):
        ClaimEvidenceCreate(
            evidence_type=ClaimEvidenceType.INTERVIEW_TURN,
            evidence_direction=EvidenceDirection.SUPPORTS,
            strength=0.8,
        )
    service, _ = make_graph()
    claim = asyncio.run(service.create_claim(USER_A, new_claim()))
    evidence = asyncio.run(
        service.link_evidence(
            claim.id,
            USER_A,
            ClaimEvidenceCreate(
                evidence_type=ClaimEvidenceType.SYSTEM_OBSERVATION,
                quote_text="Candidate supplied contextual clarification.",
                evidence_direction=EvidenceDirection.CONTEXT_ONLY,
                strength=0.5,
            ),
        )
    )
    assert evidence.claim_id == claim.id


def test_resume_analysis_migration_builds_graph_transactionally() -> None:
    migration = Path("supabase/migrations/202609010007_claims_graph.sql").read_text()
    assert "perform public.build_claim_graph_for_resume_analysis" in migration
    assert "'DOCUMENT_EXCERPT'" in migration
    assert "'CONTEXT_ONLY'" in migration
    assert "'AI'" in migration
    assert "claim_relations_validate_ownership" in migration
    assert "claim_evidence_validate_ownership" in migration


class ClaimsVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token == "user-a":
            return AuthenticatedUser(id=USER_A, email="a@example.com")
        if token == "user-b":
            return AuthenticatedUser(id=USER_B, email="b@example.com")
        raise InvalidAccessToken


@pytest.fixture
def claims_client() -> tuple[TestClient, ClaimsGraphService]:
    service, _ = make_graph()
    asyncio.run(service.create_claim(USER_A, new_claim()))
    app.dependency_overrides[get_token_verifier] = lambda: ClaimsVerifier()
    app.dependency_overrides[get_claims_graph_service] = lambda: service
    with TestClient(app) as client:
        yield client, service
    app.dependency_overrides.pop(get_token_verifier, None)
    app.dependency_overrides.pop(get_claims_graph_service, None)


def test_claim_api_is_owner_scoped(
    claims_client: tuple[TestClient, ClaimsGraphService],
) -> None:
    client, _ = claims_client
    own = client.get("/api/v1/claims", headers={"Authorization": "Bearer user-a"})
    assert own.status_code == 200 and len(own.json()) == 1
    claim_id = own.json()[0]["id"]
    assert (
        client.get(
            f"/api/v1/claims/{claim_id}", headers={"Authorization": "Bearer user-a"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/claims/{claim_id}", headers={"Authorization": "Bearer user-b"}
        ).status_code
        == 404
    )
    assert client.get("/api/v1/claims").status_code == 401

