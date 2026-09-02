from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID
from urllib.parse import quote

import httpx

from .config import Settings
from .schemas import DocumentRead


DOCUMENT_COLUMNS = (
    "id,user_id,document_type,storage_path,original_filename,mime_type,"
    "raw_text,status,error_message,created_at,processed_at"
)


class DocumentUnavailable(Exception):
    pass


class DocumentRepository(Protocol):
    async def create(self, values: dict[str, Any]) -> DocumentRead: ...
    async def list_for_user(self, user_id: UUID) -> list[DocumentRead]: ...
    async def get_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentRead | None: ...
    async def linked_to_protected_session(self, document_id: UUID) -> bool: ...
    async def update_owned(
        self, document_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> DocumentRead: ...
    async def delete(self, document_id: UUID, user_id: UUID) -> bool: ...


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
            key: value.value
            if hasattr(value, "value")
            else str(value)
            if isinstance(value, UUID)
            else value
            for key, value in values.items()
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
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

    async def list_for_user(self, user_id: UUID) -> list[DocumentRead]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/documents",
                    headers=self._headers,
                    params={
                        "user_id": f"eq.{user_id}",
                        "select": DOCUMENT_COLUMNS,
                        "order": "created_at.desc",
                    },
                )
                response.raise_for_status()
                return [DocumentRead.model_validate(row) for row in response.json()]
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def get_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentRead | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
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
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/session_document_links",
                    headers=self._headers,
                    params={
                        "document_id": f"eq.{document_id}",
                        "select": "session:sessions!inner(status)",
                        "sessions.status": "in.(in_progress,processing,complete)",
                        "limit": "1",
                    },
                )
                response.raise_for_status()
                return bool(response.json())
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc

    async def update_owned(
        self, document_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> DocumentRead:
        serialised = {
            key: value.value if hasattr(value, "value") else value
            for key, value in values.items()
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
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
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.delete(
                    f"{self._url}/rest/v1/documents",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"id": f"eq.{document_id}", "user_id": f"eq.{user_id}"},
                )
                response.raise_for_status()
                return bool(response.json())
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise DocumentUnavailable from exc


class SupabaseResumeStorage:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise DocumentUnavailable("Supabase resume storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._service_key = settings.supabase_service_role_key

    async def upload(self, path: str, content: bytes, mime_type: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
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
            async with httpx.AsyncClient(timeout=30) as client:
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
            async with httpx.AsyncClient(timeout=15) as client:
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
        "raw_text": raw_text,
        "status": "PROCESSED",
        "processed_at": datetime.now(UTC).isoformat(),
    }

