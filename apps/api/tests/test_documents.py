from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.dependencies import get_document_repository, get_document_storage
from app.main import app, settings
from app.schemas import DocumentRead


USER_A = UUID("40000000-0000-4000-8000-000000000004")
USER_B = UUID("50000000-0000-4000-8000-000000000005")


class DocumentVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token == "document-a":
            return AuthenticatedUser(id=USER_A, email="a@example.com")
        if token == "document-b":
            return AuthenticatedUser(id=USER_B, email="b@example.com")
        raise InvalidAccessToken


class MemoryDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[UUID, DocumentRead] = {}
        self.protected_links: set[UUID] = set()

    async def create(self, values: dict[str, Any]) -> DocumentRead:
        document = DocumentRead.model_validate(
            {
                "id": values.get("id", uuid4()),
                "storage_path": None,
                "original_filename": None,
                "mime_type": None,
                "raw_text": None,
                "error_message": None,
                "processed_at": None,
                "created_at": datetime.now(UTC),
                **values,
            }
        )
        self.documents[document.id] = document
        return document

    async def list_for_user(self, user_id: UUID) -> list[DocumentRead]:
        return [
            document
            for document in self.documents.values()
            if document.user_id == user_id
        ]

    async def get_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentRead | None:
        document = self.documents.get(document_id)
        return document if document and document.user_id == user_id else None

    async def linked_to_protected_session(self, document_id: UUID) -> bool:
        return document_id in self.protected_links

    async def delete(self, document_id: UUID, user_id: UUID) -> bool:
        if await self.get_for_user(document_id, user_id) is None:
            return False
        del self.documents[document_id]
        return True


class MemoryDocumentStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def upload(self, path: str, content: bytes, mime_type: str) -> None:
        self.objects[path] = (content, mime_type)

    async def delete(self, path: str) -> None:
        self.objects.pop(path, None)


@pytest.fixture
def document_client() -> tuple[
    TestClient, MemoryDocumentRepository, MemoryDocumentStorage
]:
    repository = MemoryDocumentRepository()
    storage = MemoryDocumentStorage()
    app.dependency_overrides[get_token_verifier] = lambda: DocumentVerifier()
    app.dependency_overrides[get_document_repository] = lambda: repository
    app.dependency_overrides[get_document_storage] = lambda: storage
    with TestClient(app) as client:
        yield client, repository, storage
    app.dependency_overrides.pop(get_document_repository, None)
    app.dependency_overrides.pop(get_document_storage, None)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def docx_content() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return output.getvalue()


@pytest.mark.parametrize(
    ("filename", "content", "mime_type"),
    [
        ("resume.pdf", b"not a real PDF", "application/pdf"),
        ("resume.exe", b"MZ", "application/octet-stream"),
        (
            "resume.docx",
            b"PK-not-a-docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_resume_rejects_unsupported_or_spoofed_file_types(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
    filename: str,
    content: bytes,
    mime_type: str,
) -> None:
    client, repository, storage = document_client
    response = client.post(
        "/api/v1/documents/resume",
        headers=auth("document-a"),
        files={"resume": (filename, content, mime_type)},
    )
    assert response.status_code == 415
    assert not repository.documents
    assert not storage.objects


@pytest.mark.parametrize(
    ("content", "mime_type"),
    [
        (b"%PDF-1.7\nvalid enough for ingestion", "application/pdf"),
        (
            docx_content(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_supported_resume_signatures_are_uploaded(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
    content: bytes,
    mime_type: str,
) -> None:
    client, repository, storage = document_client
    response = client.post(
        "/api/v1/documents/resume",
        headers=auth("document-a"),
        files={"resume": ("misleading.txt", content, mime_type)},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "UPLOADED"
    assert response.json()["mime_type"] == mime_type
    assert len(repository.documents) == 1
    assert len(storage.objects) == 1


def test_resume_rejects_files_over_configured_size(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, repository, storage = document_client
    monkeypatch.setattr(settings, "resume_max_file_size_bytes", 8)
    response = client.post(
        "/api/v1/documents/resume",
        headers=auth("document-a"),
        files={"resume": ("resume.pdf", b"%PDF-1234", "application/pdf")},
    )
    assert response.status_code == 413
    assert not repository.documents
    assert not storage.objects


def test_job_description_creation_persists_raw_text(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, _, _ = document_client
    response = client.post(
        "/api/v1/documents/job-description",
        headers=auth("document-a"),
        json={"raw_text": "  Build reliable APIs and collaborate with product.  "},
    )
    assert response.status_code == 201
    assert response.json()["document_type"] == "JOB_DESCRIPTION"
    assert response.json()["status"] == "PROCESSED"
    assert (
        response.json()["raw_text"]
        == "Build reliable APIs and collaborate with product."
    )


def test_document_access_and_deletion_are_owner_scoped(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, _, _ = document_client
    created = client.post(
        "/api/v1/documents/job-description",
        headers=auth("document-a"),
        json={"raw_text": "Role for candidate A"},
    ).json()

    document_id = created["id"]
    assert (
        client.get(
            f"/api/v1/documents/{document_id}", headers=auth("document-b")
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/documents/{document_id}", headers=auth("document-b")
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/documents/{document_id}", headers=auth("document-a")
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/api/v1/documents/{document_id}", headers=auth("document-a")
        ).status_code
        == 204
    )


def test_unauthorized_document_access_returns_401(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, _, _ = document_client
    assert client.get("/api/v1/documents").status_code == 401
    assert client.get(f"/api/v1/documents/{uuid4()}").status_code == 401


def test_linked_document_cannot_be_deleted(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, repository, _ = document_client
    created = client.post(
        "/api/v1/documents/job-description",
        headers=auth("document-a"),
        json={"raw_text": "Protected job description"},
    ).json()
    document_id = UUID(created["id"])
    repository.protected_links.add(document_id)

    response = client.delete(
        f"/api/v1/documents/{document_id}", headers=auth("document-a")
    )
    assert response.status_code == 409
    assert document_id in repository.documents

