from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from .document_repository import DocumentRepository, DocumentStorage, DocumentUnavailable
from .schemas import DocumentRead, DocumentType, EvidenceCategory, EvidenceDetail, EvidenceUsage


class EvidenceNotFound(Exception):
    pass


class EvidenceArchived(Exception):
    pass


class EvidenceActiveUse(Exception):
    def __init__(self, usage: EvidenceUsage) -> None:
        self.usage = usage
        super().__init__("evidence is linked to an active diagnostic")


class DocumentLibraryService:
    """Owns safe evidence metadata, archive, restore, and replacement lifecycle."""

    def __init__(
        self,
        repository: DocumentRepository,
        storage: DocumentStorage,
    ) -> None:
        self._repository = repository
        self._storage = storage

    async def list(
        self,
        user_id: UUID,
        *,
        include_archived: bool = False,
    ) -> list[EvidenceDetail]:
        documents = await self._repository.list_for_user(
            user_id,
            include_archived=include_archived,
        )
        usage = await asyncio.gather(
            *(self._repository.usage(document.id, user_id) for document in documents)
        )
        return [
            EvidenceDetail(document=document, usage=document_usage)
            for document, document_usage in zip(documents, usage, strict=True)
        ]

    async def detail(self, document_id: UUID, user_id: UUID) -> EvidenceDetail:
        document = await self._owned(document_id, user_id)
        return EvidenceDetail(
            document=document,
            usage=await self._repository.usage(document_id, user_id),
        )

    async def update_metadata(
        self,
        document_id: UUID,
        user_id: UUID,
        values: dict[str, Any],
        *,
        acknowledge_active_use: bool,
    ) -> EvidenceDetail:
        document = await self._active(document_id, user_id)
        usage = await self._repository.usage(document.id, user_id)
        self._require_active_acknowledgement(usage, acknowledge_active_use)
        if usage.diagnostics:
            replacement = await self._repository.replace_owned(
                document.id,
                user_id,
                {
                    "id": uuid4(),
                    "document_type": document.document_type,
                    "storage_path": document.storage_path,
                    "original_filename": document.original_filename,
                    "mime_type": document.mime_type,
                    "raw_text": document.raw_text,
                    "status": document.status,
                    "processed_at": document.processed_at,
                    "title": values.get("title", document.title)
                    or document.original_filename
                    or "Professional evidence",
                    "evidence_category": values.get(
                        "evidence_category",
                        document.evidence_category,
                    ) or _legacy_category(document.document_type),
                    "context_note": values.get("context_note", document.context_note),
                },
            )
            return EvidenceDetail(
                document=replacement,
                usage=EvidenceUsage(
                    active_diagnostic_count=0,
                    completed_diagnostic_count=0,
                ),
            )
        updated = await self._repository.update_owned(document.id, user_id, values)
        return EvidenceDetail(document=updated, usage=usage)

    async def archive(
        self,
        document_id: UUID,
        user_id: UUID,
        *,
        acknowledge_active_use: bool,
    ) -> EvidenceDetail:
        document = await self._active(document_id, user_id)
        usage = await self._repository.usage(document.id, user_id)
        self._require_active_acknowledgement(usage, acknowledge_active_use)
        archived = await self._repository.update_owned(
            document.id,
            user_id,
            {"archived_at": datetime.now(UTC)},
        )
        return EvidenceDetail(document=archived, usage=usage)

    async def restore(self, document_id: UUID, user_id: UUID) -> EvidenceDetail:
        document = await self._owned(document_id, user_id)
        if document.archived_at is None:
            return EvidenceDetail(
                document=document,
                usage=await self._repository.usage(document.id, user_id),
            )
        restored = await self._repository.update_owned(
            document.id,
            user_id,
            {"archived_at": None},
        )
        return EvidenceDetail(
            document=restored,
            usage=await self._repository.usage(document.id, user_id),
        )

    async def replace(
        self,
        document_id: UUID,
        user_id: UUID,
        values: dict[str, Any],
        content: bytes,
        *,
        acknowledge_active_use: bool,
    ) -> EvidenceDetail:
        document = await self._active(document_id, user_id)
        usage = await self._repository.usage(document.id, user_id)
        self._require_active_acknowledgement(usage, acknowledge_active_use)
        storage_path = str(values["storage_path"])
        await self._storage.upload(storage_path, content, str(values["mime_type"]))
        try:
            replacement = await self._repository.replace_owned(
                document.id,
                user_id,
                values,
            )
        except DocumentUnavailable:
            try:
                await self._storage.delete(storage_path)
            except DocumentUnavailable:
                pass
            raise
        return EvidenceDetail(document=replacement, usage=EvidenceUsage(
            active_diagnostic_count=0,
            completed_diagnostic_count=0,
        ))

    async def _owned(self, document_id: UUID, user_id: UUID) -> DocumentRead:
        document = await self._repository.get_for_user(document_id, user_id)
        if document is None:
            raise EvidenceNotFound
        return document

    async def _active(self, document_id: UUID, user_id: UUID) -> DocumentRead:
        document = await self._owned(document_id, user_id)
        if document.archived_at is not None:
            raise EvidenceArchived
        return document

    @staticmethod
    def _require_active_acknowledgement(
        usage: EvidenceUsage,
        acknowledged: bool,
    ) -> None:
        if usage.active_diagnostic_count and not acknowledged:
            raise EvidenceActiveUse(usage)


def _legacy_category(document_type: DocumentType) -> EvidenceCategory:
    if document_type == DocumentType.RESUME:
        return EvidenceCategory.RESUME
    if document_type == DocumentType.JOB_DESCRIPTION:
        return EvidenceCategory.ROLE_BRIEF
    return EvidenceCategory.PROJECT
