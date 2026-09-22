from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID
from urllib.parse import quote

import httpx

from .http_pool import pooled

from .config import Settings
from .schemas import (
    DocumentRead,
    DocumentType,
    EvidenceDiagnosticReference,
    EvidenceUsage,
)


DOCUMENT_COLUMNS = (
    "id,user_id,document_type,storage_path,original_filename,mime_type,"
    "raw_text,status,error_message,created_at,processed_at,title,"
    "evidence_category,context_note,updated_at,archived_at,version_number,"
    "supersedes_document_id"
)


class DocumentUnavailable(Exception):
    pass


class DocumentRepository(Protocol):
    async def create(self, values: dict[str, Any]) -> DocumentRead: ...
    async def list_for_user(
        self, user_id: UUID, *, include_archived: bool = False
    ) -> list[DocumentRead]: ...
    async def get_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentRead | None: ...
    async def linked_to_protected_session(self, document_id: UUID) -> bool: ...
    async def usage(self, document_id: UUID, user_id: UUID) -> EvidenceUsage: ...
    async def update_owned(
        self, document_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> DocumentRead: ...
    async def delete(self, document_id: UUID, user_id: UUID) -> bool: ...
    async def replace_owned(
        self,
        document_id: UUID,
        user_id: UUID,
        values: dict[str, Any],
    ) -> DocumentRead: ...
    async def link_to_session(self, session_id: UUID, document_id: UUID) -> None: ...


class DocumentStorage(Protocol):
    async def upload(self, path: str, content: bytes, mime_type: str) -> None: ...
    async def download(self, path: str) -> bytes: ...
    async def delete(self, path: str) -> None: ...


class SupabaseDocumentRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise DocumentUnavailable("Supabase document storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def create(self, values: dict[str, Any]) -> DocumentRead:
        serialised = {
            key: _value(value)
            for key, value in values.items()
        }
        try:
            async with pooled(10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/documents",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"select": DOCUMENT_COLUMNS},
                    json=serialised,
                )
                response.raise_for_status()
                return DocumentRead.model_validate(response.json()[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def list_for_user(
        self, user_id: UUID, *, include_archived: bool = False
    ) -> list[DocumentRead]:
        params = {
            "user_id": f"eq.{user_id}",
            "select": DOCUMENT_COLUMNS,
            "order": "updated_at.desc,created_at.desc",
        }
        if not include_archived:
            params["archived_at"] = "is.null"
        try:
            async with pooled(10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/documents",
                    headers=self._headers,
                    params=params,
                )
                response.raise_for_status()
                return [DocumentRead.model_validate(row) for row in response.json()]
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def get_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentRead | None:
        try:
            async with pooled(10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/documents",
                    headers=self._headers,
                    params={
                        "id": f"eq.{document_id}",
                        "user_id": f"eq.{user_id}",
                        "select": DOCUMENT_COLUMNS,
                    },
                )
                response.raise_for_status()
                rows = response.json()
                return DocumentRead.model_validate(rows[0]) if rows else None
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def linked_to_protected_session(self, document_id: UUID) -> bool:
        try:
            async with pooled(10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/session_document_links",
                    headers=self._headers,
                    params={
                        "document_id": f"eq.{document_id}",
                        "select": "session:sessions!inner(status)",
                        "sessions.status": "in.(CREATED,PREPARING,READY,ACTIVE,ASSESSING,COMPLETED)",
                        "limit": "1",
                    },
                )
                response.raise_for_status()
                return bool(response.json())
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def usage(self, document_id: UUID, user_id: UUID) -> EvidenceUsage:
        if await self.get_for_user(document_id, user_id) is None:
            return EvidenceUsage(
                active_diagnostic_count=0,
                completed_diagnostic_count=0,
            )
        try:
            async with pooled(10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/session_document_links",
                    headers=self._headers,
                    params={
                        "document_id": f"eq.{document_id}",
                        "select": (
                            "created_at,session:sessions!inner("
                            "id,user_id,target_role,status,completed_at)"
                        ),
                        "session.user_id": f"eq.{user_id}",
                        "order": "created_at.desc",
                    },
                )
                response.raise_for_status()
                diagnostics: list[EvidenceDiagnosticReference] = []
                for row in response.json():
                    session = row.get("session")
                    if not isinstance(session, dict):
                        continue
                    diagnostics.append(
                        EvidenceDiagnosticReference(
                            session_id=session["id"],
                            target_role=session["target_role"],
                            status=session["status"],
                            linked_at=row["created_at"],
                            completed_at=session.get("completed_at"),
                        )
                    )
                return EvidenceUsage(
                    active_diagnostic_count=sum(
                        item.status
                        in {"CREATED", "PREPARING", "READY", "ACTIVE", "ASSESSING"}
                        for item in diagnostics
                    ),
                    completed_diagnostic_count=sum(
                        item.status == "COMPLETED" for item in diagnostics
                    ),
                    diagnostics=diagnostics,
                )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def update_owned(
        self, document_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> DocumentRead:
        serialised = {
            key: _value(value)
            for key, value in values.items()
        }
        try:
            async with pooled(10) as client:
                response = await client.patch(
                    f"{self._url}/rest/v1/documents",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={
                        "id": f"eq.{document_id}",
                        "user_id": f"eq.{user_id}",
                        "select": DOCUMENT_COLUMNS,
                    },
                    json=serialised,
                )
                response.raise_for_status()
                rows = response.json()
                if not rows:
                    raise DocumentUnavailable("document update returned no row")
                return DocumentRead.model_validate(rows[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def delete(self, document_id: UUID, user_id: UUID) -> bool:
        try:
            async with pooled(10) as client:
                response = await client.delete(
                    f"{self._url}/rest/v1/documents",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"id": f"eq.{document_id}", "user_id": f"eq.{user_id}"},
                )
                response.raise_for_status()
                return bool(response.json())
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def replace_owned(
        self,
        document_id: UUID,
        user_id: UUID,
        values: dict[str, Any],
    ) -> DocumentRead:
        payload = {
            "p_original_document_id": str(document_id),
            "p_user_id": str(user_id),
            "p_new_document_id": str(values["id"]),
            "p_document_type": _value(values["document_type"]),
            "p_storage_path": values.get("storage_path"),
            "p_original_filename": values.get("original_filename"),
            "p_mime_type": values.get("mime_type"),
            "p_raw_text": values.get("raw_text"),
            "p_status": _value(values["status"]),
            "p_processed_at": values.get("processed_at"),
            "p_title": values["title"],
            "p_evidence_category": _value(values["evidence_category"]),
            "p_context_note": values.get("context_note"),
        }
        try:
            async with pooled(10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/rpc/replace_evidence_document",
                    headers=self._headers,
                    params={"select": DOCUMENT_COLUMNS},
                    json=payload,
                )
                response.raise_for_status()
                rows = response.json()
                if not rows:
                    raise DocumentUnavailable("replacement returned no row")
                return DocumentRead.model_validate(rows[0])
        except (httpx.HTTPError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def link_to_session(self, session_id: UUID, document_id: UUID) -> None:
        try:
            async with pooled(10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/session_document_links",
                    headers={
                        **self._headers,
                        "Prefer": "resolution=ignore-duplicates",
                    },
                    params={"on_conflict": "session_id,document_id"},
                    json={
                        "session_id": str(session_id),
                        "document_id": str(document_id),
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DocumentUnavailable from exc


class SupabaseResumeStorage:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise DocumentUnavailable("Supabase resume storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._service_key = settings.supabase_service_role_key

    async def upload(self, path: str, content: bytes, mime_type: str) -> None:
        try:
            async with pooled(30) as client:
                response = await client.post(
                    f"{self._url}/storage/v1/object/private-resumes/{path}",
                    headers={
                        "apikey": self._service_key,
                        "Authorization": f"Bearer {self._service_key}",
                        "Content-Type": mime_type,
                        "x-upsert": "false",
                    },
                    content=content,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DocumentUnavailable from exc

    async def download(self, path: str) -> bytes:
        try:
            async with pooled(30) as client:
                response = await client.get(
                    f"{self._url}/storage/v1/object/private-resumes/{quote(path, safe='/')}",
                    headers={
                        "apikey": self._service_key,
                        "Authorization": f"Bearer {self._service_key}",
                    },
                )
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as exc:
            raise DocumentUnavailable from exc

    async def delete(self, path: str) -> None:
        try:
            async with pooled(15) as client:
                response = await client.delete(
                    f"{self._url}/storage/v1/object/private-resumes/{path}",
                    headers={
                        "apikey": self._service_key,
                        "Authorization": f"Bearer {self._service_key}",
                    },
                )
                if response.status_code not in (200, 404):
                    response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DocumentUnavailable from exc


def job_description_values(user_id: UUID, raw_text: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "document_type": "JOB_DESCRIPTION",
        "title": "Role brief",
        "evidence_category": "ROLE_BRIEF",
        "raw_text": raw_text,
        "status": "PROCESSED",
        "processed_at": datetime.now(UTC).isoformat(),
    }


def document_type_for_category(category: str) -> DocumentType:
    if category == "RESUME":
        return DocumentType.RESUME
    if category == "ROLE_BRIEF":
        return DocumentType.JOB_DESCRIPTION
    return DocumentType.PROJECT


def _value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value

