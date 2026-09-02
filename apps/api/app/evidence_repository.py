from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from .config import Settings
from .evidence_models import (
    EvidenceContext,
    EvidenceItem,
    EvidenceSourceExcerpt,
    EvidenceSourceType,
)
from .skeptic_repository import SkepticPersistenceUnavailable, SupabaseSkepticRepository


class EvidencePersistenceUnavailable(Exception):
    pass


class EvidenceRepository(Protocol):
    async def load_context(self, claim_id: UUID, user_id: UUID) -> EvidenceContext | None: ...
    async def load_source_text(
        self, source_type: EvidenceSourceType, source_id: UUID, user_id: UUID
    ) -> str | None: ...
    async def save_validated(
        self,
        claim_id: UUID,
        user_id: UUID,
        item: EvidenceItem,
        execution_id: UUID,
        model: str,
        prompt_version: str,
    ) -> bool: ...
    async def list_execution_evidence_ids(
        self, claim_id: UUID, user_id: UUID, execution_id: UUID
    ) -> list[UUID]: ...


class SupabaseEvidenceRepository(SupabaseSkepticRepository):
    def __init__(self, settings: Settings) -> None:
        try:
            super().__init__(settings)
        except SkepticPersistenceUnavailable as exc:
            raise EvidencePersistenceUnavailable from exc

    async def load_context(self, claim_id: UUID, user_id: UUID) -> EvidenceContext | None:
        claims = await self._get(
            "claims", {"id": f"eq.{claim_id}", "user_id": f"eq.{user_id}", "select": "*", "limit": "1"}
        )
        if not claims:
            return None
        claim_row = dict(claims[0])
        claim_row.update(
            claim_type=str(claim_row["claim_type"]).upper(),
            source=str(claim_row["source"]).upper(),
            status=str(claim_row["status"]).upper(),
            verification_priority=str(claim_row["verification_priority"]).upper(),
        )
        excerpts: list[EvidenceSourceExcerpt] = []
        document_id = claim_row.get("source_document_id")
        if document_id:
            documents = await self._get(
                "documents", {"id": f"eq.{document_id}", "user_id": f"eq.{user_id}", "select": "id,document_type,raw_text", "limit": "1"}
            )
            if documents and documents[0].get("raw_text"):
                excerpts.append(
                    EvidenceSourceExcerpt(
                        source_type=(EvidenceSourceType.RESUME if str(documents[0]["document_type"]).upper() == "RESUME" else EvidenceSourceType.OTHER_DOCUMENT),
                        source_id=documents[0]["id"],
                        text=documents[0]["raw_text"],
                        source_reference=claim_row.get("source_reference"),
                    )
                )
        turn_params = {
            "select": "id,speaker,text,sessions!inner(user_id)",
            "sessions.user_id": f"eq.{user_id}",
            "order": "turn_index.asc",
            "limit": "50",
        }
        if claim_row.get("session_id"):
            turn_params["session_id"] = f"eq.{claim_row['session_id']}"
        turns = await self._get("turns", turn_params)
        transcript = [
            EvidenceSourceExcerpt(
                source_type=(EvidenceSourceType.CANDIDATE_TURN if str(row["speaker"]).lower() == "candidate" else EvidenceSourceType.INTERVIEWER_TURN),
                source_id=row["id"],
                text=row["text"],
            )
            for row in turns
        ]
        flags = await self._get(
            "flags", {"claim_id": f"eq.{claim_id}", "select": "id,flag_type,severity,confidence,reason,safe_to_surface", "limit": "30"}
        )
        evidence = await self._get(
            "claim_evidence", {"claim_id": f"eq.{claim_id}", "user_id": f"eq.{user_id}", "select": "id,user_id,claim_id,evidence_type,turn_id,document_id,quote_text,evidence_direction,strength,created_at", "order": "created_at.asc"}
        )
        return EvidenceContext.model_validate(
            {
                "claim": claim_row,
                "resume_source_excerpts": excerpts,
                "related_transcript_turns": transcript,
                "related_flags": flags,
                "related_probes": [item for item in transcript if item.source_type == EvidenceSourceType.INTERVIEWER_TURN],
                "existing_evidence": [
                    {**row, "evidence_type": str(row["evidence_type"]).upper(), "evidence_direction": str(row["evidence_direction"]).upper()}
                    for row in evidence
                ],
            }
        )

    async def load_source_text(
        self, source_type: EvidenceSourceType, source_id: UUID, user_id: UUID
    ) -> str | None:
        if source_type in {EvidenceSourceType.CANDIDATE_TURN, EvidenceSourceType.INTERVIEWER_TURN}:
            rows = await self._get(
                "turns", {"id": f"eq.{source_id}", "select": "text,sessions!inner(user_id)", "sessions.user_id": f"eq.{user_id}", "limit": "1"}
            )
        elif source_type in {EvidenceSourceType.RESUME, EvidenceSourceType.OTHER_DOCUMENT}:
            rows = await self._get(
                "documents", {"id": f"eq.{source_id}", "user_id": f"eq.{user_id}", "select": "raw_text", "limit": "1"}
            )
        else:
            # PROJECT becomes trusted only once it has a canonical persisted text
            # source. Reject rather than validating against synthesized metadata.
            return None
        if not rows:
            return None
        return rows[0].get("text") or rows[0].get("raw_text")

    async def save_validated(
        self, claim_id: UUID, user_id: UUID, item: EvidenceItem,
        execution_id: UUID, model: str, prompt_version: str,
    ) -> bool:
        rows = await self._post(
            "rpc/insert_validated_claim_evidence",
            {
                "p_claim_id": str(claim_id), "p_user_id": str(user_id),
                "p_source_type": item.source_type.value,
                "p_source_id": str(item.source_id),
                "p_turn_id": str(item.turn_id) if item.turn_id else None,
                "p_document_id": str(item.document_id) if item.document_id else None,
                "p_quote_text": item.quote, "p_direction": item.direction.value,
                "p_strength": item.strength.value, "p_reason_code": item.reason_code.value,
                "p_execution_id": str(execution_id), "p_model": model,
                "p_prompt_version": prompt_version,
            },
        )
        value: Any = rows[0] if rows else False
        if isinstance(value, dict):
            value = value.get("insert_validated_claim_evidence", False)
        return bool(value)

    async def list_execution_evidence_ids(
        self, claim_id: UUID, user_id: UUID, execution_id: UUID
    ) -> list[UUID]:
        rows = await self._get("claim_evidence", {
            "claim_id": f"eq.{claim_id}", "user_id": f"eq.{user_id}",
            "evidence_execution_id": f"eq.{execution_id}", "validated": "eq.true",
            "select": "id",
        })
        return [UUID(str(row["id"])) for row in rows]

