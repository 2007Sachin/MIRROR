from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import httpx

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
from .config import Settings


CLAIM_COLUMNS = (
    "id,user_id,session_id,claim_text,claim_type,source,source_document_id,"
    "source_reference,status,confidence,verification_priority,synthetic,created_at,updated_at"
)


class ClaimsGraphUnavailable(Exception):
    pass


class ClaimsGraphRepository(Protocol):
    async def get_claim(self, claim_id: UUID, user_id: UUID) -> ClaimRead | None: ...

    async def get_graph(
        self, claim_id: UUID, user_id: UUID
    ) -> ClaimGraphRead | None: ...

    async def list_claims(
        self,
        user_id: UUID,
        *,
        skill: str | None = None,
        project: str | None = None,
        status: ClaimStatus | None = None,
        source: ClaimSource | None = None,
        session_id: UUID | None = None,
    ) -> list[ClaimRead]: ...

    async def create_claim(
        self, user_id: UUID, claim: ClaimCreate, changed_by: ClaimChangedBy, reason: str
    ) -> ClaimRead: ...

    async def get_or_create_entity(
        self, user_id: UUID, entity: ClaimEntityCreate
    ) -> ClaimEntityRead: ...

    async def create_relation(
        self, user_id: UUID, relation: ClaimRelationCreate
    ) -> ClaimRelationRead: ...

    async def create_version(
        self, claim_id: UUID, user_id: UUID, version: ClaimVersionCreate
    ) -> ClaimVersionRead: ...

    async def update_status(
        self,
        claim_id: UUID,
        user_id: UUID,
        status: ClaimStatus,
        changed_by: ClaimChangedBy,
        reason: str,
    ) -> ClaimRead: ...

    async def link_evidence(
        self, claim_id: UUID, user_id: UUID, evidence: ClaimEvidenceCreate
    ) -> ClaimEvidenceRead: ...

    async def find_related(self, claim_id: UUID, user_id: UUID) -> list[ClaimRead]: ...


def _claim(row: dict[str, Any]) -> ClaimRead:
    normalized = dict(row)
    for key in ("claim_type", "source", "status", "verification_priority"):
        normalized[key] = normalized[key].upper()
    return ClaimRead.model_validate(normalized)


class SupabaseClaimsGraphRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise ClaimsGraphUnavailable("Supabase claims storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def get_claim(self, claim_id: UUID, user_id: UUID) -> ClaimRead | None:
        rows = await self._get(
            "claims",
            {
                "id": f"eq.{claim_id}",
                "user_id": f"eq.{user_id}",
                "select": CLAIM_COLUMNS,
            },
        )
        return _claim(rows[0]) if rows else None

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
        claim_ids: set[str] | None = None
        for entity_type, name in (("SKILL", skill), ("PROJECT", project)):
            if name is None:
                continue
            entities = await self._get(
                "claim_entities",
                {
                    "user_id": f"eq.{user_id}",
                    "entity_type": f"eq.{entity_type}",
                    "canonical_key": f"eq.{name.strip().casefold()}",
                    "select": "id",
                },
            )
            entity_ids = [row["id"] for row in entities]
            if not entity_ids:
                return []
            relations = await self._get(
                "claim_relations",
                {
                    "user_id": f"eq.{user_id}",
                    "source_entity_type": "eq.CLAIM",
                    "target_entity_id": f"in.({','.join(entity_ids)})",
                    "select": "source_entity_id",
                },
            )
            matching = {row["source_entity_id"] for row in relations}
            claim_ids = matching if claim_ids is None else claim_ids & matching
        if claim_ids == set():
            return []
        params: dict[str, str] = {
            "user_id": f"eq.{user_id}",
            "select": CLAIM_COLUMNS,
            "order": "created_at.desc",
        }
        if claim_ids is not None:
            params["id"] = f"in.({','.join(claim_ids)})"
        if status:
            params["status"] = f"eq.{status.value.lower()}"
        if source:
            params["source"] = f"eq.{source.value.lower()}"
        if session_id:
            params["session_id"] = f"eq.{session_id}"
        return [_claim(row) for row in await self._get("claims", params)]

    async def get_graph(self, claim_id: UUID, user_id: UUID) -> ClaimGraphRead | None:
        claim = await self.get_claim(claim_id, user_id)
        if claim is None:
            return None
        relations = [
            ClaimRelationRead.model_validate(row)
            for row in await self._get(
                "claim_relations",
                {
                    "user_id": f"eq.{user_id}",
                    "or": f"(source_entity_id.eq.{claim_id},target_entity_id.eq.{claim_id})",
                    "select": "*",
                },
            )
        ]
        entity_ids = {
            str(relation.target_entity_id)
            for relation in relations
            if relation.target_entity_type.value == "ENTITY"
        } | {
            str(relation.source_entity_id)
            for relation in relations
            if relation.source_entity_type.value == "ENTITY"
        }
        entities = []
        if entity_ids:
            entities = [
                ClaimEntityRead.model_validate(row)
                for row in await self._get(
                    "claim_entities",
                    {
                        "user_id": f"eq.{user_id}",
                        "id": f"in.({','.join(entity_ids)})",
                        "select": "id,user_id,entity_type,canonical_name,metadata,created_at",
                    },
                )
            ]
        versions = [
            ClaimVersionRead.model_validate(row)
            for row in await self._get(
                "claim_versions",
                {
                    "claim_id": f"eq.{claim_id}",
                    "user_id": f"eq.{user_id}",
                    "select": "*",
                    "order": "version.asc",
                },
            )
        ]
        evidence = [
            ClaimEvidenceRead.model_validate(row)
            for row in await self._get(
                "claim_evidence",
                {
                    "claim_id": f"eq.{claim_id}",
                    "user_id": f"eq.{user_id}",
                    "select": "*",
                    "order": "created_at.asc",
                },
            )
        ]
        return ClaimGraphRead(
            claim=claim,
            entities=entities,
            relations=relations,
            versions=versions,
            evidence=evidence,
            related_claims=await self.find_related(claim_id, user_id),
        )

    async def create_claim(
        self, user_id: UUID, claim: ClaimCreate, changed_by: ClaimChangedBy, reason: str
    ) -> ClaimRead:
        rows = await self._post(
            "rpc/create_claim_with_version",
            {
                "p_user_id": str(user_id),
                "p_claim": claim.model_dump(mode="json"),
                "p_changed_by": changed_by.value,
                "p_reason": reason,
            },
        )
        return _claim(rows[0])

    async def get_or_create_entity(
        self, user_id: UUID, entity: ClaimEntityCreate
    ) -> ClaimEntityRead:
        rows = await self._post(
            "claim_entities",
            {"user_id": str(user_id), **entity.model_dump(mode="json")},
            prefer="resolution=merge-duplicates,return=representation",
            params={
                "on_conflict": "user_id,entity_type,canonical_key",
                "select": "id,user_id,entity_type,canonical_name,metadata,created_at",
            },
        )
        return ClaimEntityRead.model_validate(rows[0])

    async def create_relation(
        self, user_id: UUID, relation: ClaimRelationCreate
    ) -> ClaimRelationRead:
        rows = await self._post(
            "claim_relations",
            {"user_id": str(user_id), **relation.model_dump(mode="json")},
            prefer="return=representation",
        )
        return ClaimRelationRead.model_validate(rows[0])

    async def create_version(
        self, claim_id: UUID, user_id: UUID, version: ClaimVersionCreate
    ) -> ClaimVersionRead:
        rows = await self._post(
            "rpc/append_claim_version",
            {
                "p_claim_id": str(claim_id),
                "p_user_id": str(user_id),
                "p_previous_state": version.previous_state,
                "p_new_state": version.new_state,
                "p_changed_by": version.changed_by.value,
                "p_reason": version.reason,
            },
        )
        return ClaimVersionRead.model_validate(rows[0])

    async def update_status(
        self,
        claim_id: UUID,
        user_id: UUID,
        status: ClaimStatus,
        changed_by: ClaimChangedBy,
        reason: str,
    ) -> ClaimRead:
        rows = await self._post(
            "rpc/update_claim_status",
            {
                "p_claim_id": str(claim_id),
                "p_user_id": str(user_id),
                "p_new_status": status.value.lower(),
                "p_changed_by": changed_by.value,
                "p_reason": reason,
            },
        )
        return _claim(rows[0])

    async def link_evidence(
        self, claim_id: UUID, user_id: UUID, evidence: ClaimEvidenceCreate
    ) -> ClaimEvidenceRead:
        rows = await self._post(
            "claim_evidence",
            {
                "user_id": str(user_id),
                "claim_id": str(claim_id),
                **evidence.model_dump(mode="json"),
            },
            prefer="return=representation",
        )
        return ClaimEvidenceRead.model_validate(rows[0])

    async def find_related(self, claim_id: UUID, user_id: UUID) -> list[ClaimRead]:
        rows = await self._post(
            "rpc/find_related_claims",
            {"p_claim_id": str(claim_id), "p_user_id": str(user_id)},
        )
        return [_claim(row) for row in rows]

    async def _get(self, resource: str, params: dict[str, str]) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/{resource}",
                    headers=self._headers,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise ClaimsGraphUnavailable from exc

    async def _post(
        self,
        resource: str,
        payload: dict[str, Any],
        *,
        prefer: str | None = None,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        headers = (
            self._headers if prefer is None else {**self._headers, "Prefer": prefer}
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/{resource}",
                    headers=headers,
                    params=params,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError, ValueError, IndexError) as exc:
            raise ClaimsGraphUnavailable from exc

