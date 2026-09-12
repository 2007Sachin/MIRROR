from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.dependencies import (
    get_document_repository,
    get_document_storage,
    get_interview_state_machine,
)
from app.document_repository import DocumentUnavailable
from app.interview_engine import InterviewStateMachine
from app.main import app, settings
from app.repository import MemorySessionRepository
from app.schemas import (
    DocumentRead,
    EvidenceDiagnosticReference,
    EvidenceUsage,
)


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
        self.completed_links: set[UUID] = set()
        self.session_links: set[tuple[UUID, UUID]] = set()
        self.fail_replace = False

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

    async def list_for_user(
        self, user_id: UUID, *, include_archived: bool = False
    ) -> list[DocumentRead]:
        return [
            document
            for document in self.documents.values()
            if document.user_id == user_id
            and (include_archived or document.archived_at is None)
        ]

    async def get_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentRead | None:
        document = self.documents.get(document_id)
        return document if document and document.user_id == user_id else None

    async def linked_to_protected_session(self, document_id: UUID) -> bool:
        return document_id in self.protected_links

    async def usage(self, document_id: UUID, user_id: UUID) -> EvidenceUsage:
        if await self.get_for_user(document_id, user_id) is None:
            return EvidenceUsage(active_diagnostic_count=0, completed_diagnostic_count=0)
        if document_id not in self.protected_links and document_id not in self.completed_links:
            return EvidenceUsage(active_diagnostic_count=0, completed_diagnostic_count=0)
        active = document_id in self.protected_links
        status = "ACTIVE" if active else "COMPLETED"
        return EvidenceUsage(
            active_diagnostic_count=1 if active else 0,
            completed_diagnostic_count=0 if active else 1,
            diagnostics=[
                EvidenceDiagnosticReference(
                    session_id=UUID("60000000-0000-4000-8000-000000000006"),
                    target_role="Product Manager",
                    status=status,
                    linked_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC) if not active else None,
                )
            ],
        )

    async def update_owned(
        self, document_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> DocumentRead:
        document = await self.get_for_user(document_id, user_id)
        if document is None:
            raise RuntimeError("owned document not found")
        updated = document.model_copy(update=values)
        self.documents[document_id] = updated
        return updated

    async def delete(self, document_id: UUID, user_id: UUID) -> bool:
        if await self.get_for_user(document_id, user_id) is None:
            return False
        del self.documents[document_id]
        return True

    async def replace_owned(
        self,
        document_id: UUID,
        user_id: UUID,
        values: dict[str, Any],
    ) -> DocumentRead:
        if self.fail_replace:
            raise DocumentUnavailable("replacement failed")
        document = await self.get_for_user(document_id, user_id)
        if document is None or document.archived_at is not None:
            raise RuntimeError("active owned document not found")
        self.documents[document_id] = document.model_copy(
            update={"archived_at": datetime.now(UTC)}
        )
        replacement = await self.create(
            {
                **values,
                "user_id": user_id,
                "version_number": document.version_number + 1,
                "supersedes_document_id": document.id,
            }
        )
        return replacement

    async def link_to_session(self, session_id: UUID, document_id: UUID) -> None:
        self.session_links.add((session_id, document_id))


class MemoryDocumentStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def upload(self, path: str, content: bytes, mime_type: str) -> None:
        self.objects[path] = (content, mime_type)

    async def delete(self, path: str) -> None:
        self.objects.pop(path, None)

    async def download(self, path: str) -> bytes:
        return self.objects[path][0]


@pytest.fixture
def document_client() -> tuple[
    TestClient, MemoryDocumentRepository, MemoryDocumentStorage
]:
    repository = MemoryDocumentRepository()
    storage = MemoryDocumentStorage()
    session_engine = InterviewStateMachine(
        MemorySessionRepository(),
        total_time_budget_seconds=1200,
        phase_time_budget_seconds=180,
    )
    app.dependency_overrides[get_token_verifier] = lambda: DocumentVerifier()
    app.dependency_overrides[get_document_repository] = lambda: repository
    app.dependency_overrides[get_document_storage] = lambda: storage
    app.dependency_overrides[get_interview_state_machine] = lambda: session_engine
    with TestClient(app) as client:
        yield client, repository, storage
    app.dependency_overrides.pop(get_document_repository, None)
    app.dependency_overrides.pop(get_document_storage, None)
    app.dependency_overrides.pop(get_interview_state_machine, None)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def docx_content() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return output.getvalue()


def text_docx_content(text: str) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
            f"{text}"
            "</w:t></w:r></w:p></w:body></w:document>",
        )
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


def test_role_brief_upload_extracts_and_persists_real_document_text(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, repository, storage = document_client
    response = client.post(
        "/api/v1/documents/job-description/upload",
        headers=auth("document-a"),
        files={
            "role_brief": (
                "product-manager.docx",
                text_docx_content("Lead product discovery and pricing decisions"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201
    assert response.json()["document_type"] == "JOB_DESCRIPTION"
    assert response.json()["status"] == "PROCESSED"
    assert "Lead product discovery" in response.json()["raw_text"]
    assert len(repository.documents) == 1
    assert len(storage.objects) == 1


def test_session_document_linking_is_owner_scoped_and_idempotent(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, repository, _ = document_client
    document = client.post(
        "/api/v1/documents/job-description",
        headers=auth("document-a"),
        json={"raw_text": "Product strategy and customer research"},
    ).json()
    session = client.post(
        "/api/v1/sessions",
        headers=auth("document-a"),
        json={"target_role": "Product Manager", "jd_text": ""},
    ).json()

    payload = {"document_ids": [document["id"]]}
    first = client.post(
        f"/api/v1/sessions/{session['id']}/documents",
        headers=auth("document-a"),
        json=payload,
    )
    second = client.post(
        f"/api/v1/sessions/{session['id']}/documents",
        headers=auth("document-a"),
        json=payload,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert repository.session_links == {(UUID(session["id"]), UUID(document["id"]))}

    forbidden = client.post(
        f"/api/v1/sessions/{session['id']}/documents",
        headers=auth("document-b"),
        json=payload,
    )
    assert forbidden.status_code == 404


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


def create_project_evidence(client: TestClient, *, token: str = "document-a") -> dict[str, Any]:
    response = client.post(
        "/api/v1/evidence",
        headers=auth(token),
        data={
            "title": "Pricing case study",
            "evidence_category": "CASE_STUDY",
            "context_note": "Owned pricing research and launch measurement.",
        },
        files={
            "evidence_file": (
                "pricing.docx",
                text_docx_content("Pricing research, launch plan and measured outcomes"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201
    return response.json()


def test_evidence_add_detail_search_contract_and_owner_scope(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, _, _ = document_client
    created = create_project_evidence(client)
    document = created["document"]
    assert document["title"] == "Pricing case study"
    assert document["evidence_category"] == "CASE_STUDY"
    assert document["context_note"].startswith("Owned pricing")
    assert document["status"] == "PROCESSED"
    assert "Pricing research" in document["raw_text"]
    assert created["usage"]["active_diagnostic_count"] == 0

    listed = client.get("/api/v1/evidence", headers=auth("document-a"))
    assert listed.status_code == 200
    assert [item["document"]["id"] for item in listed.json()] == [document["id"]]
    assert client.get(
        f"/api/v1/documents/{document['id']}/detail",
        headers=auth("document-b"),
    ).status_code == 404


def test_metadata_edit_and_category_change_require_active_use_acknowledgement(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, repository, _ = document_client
    created = create_project_evidence(client)["document"]
    document_id = UUID(created["id"])
    repository.protected_links.add(document_id)

    blocked = client.patch(
        f"/api/v1/documents/{document_id}",
        headers=auth("document-a"),
        json={"title": "Pricing ownership evidence"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "EVIDENCE_ACTIVE_USE"

    updated = client.patch(
        f"/api/v1/documents/{document_id}",
        headers=auth("document-a"),
        json={
            "title": "Pricing ownership evidence",
            "evidence_category": "PROJECT",
            "context_note": "I owned the final prioritisation decision.",
            "acknowledge_active_use": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["document"]["title"] == "Pricing ownership evidence"
    assert updated.json()["document"]["evidence_category"] == "PROJECT"
    assert updated.json()["document"]["version_number"] == 2
    assert updated.json()["document"]["supersedes_document_id"] == str(document_id)
    assert updated.json()["usage"]["active_diagnostic_count"] == 0
    assert repository.documents[document_id].archived_at is not None

    assert client.patch(
        f"/api/v1/documents/{document_id}",
        headers=auth("document-b"),
        json={"title": "Not mine"},
    ).status_code == 404


def test_archive_is_recoverable_and_preserves_completed_diagnostic_and_storage(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, repository, storage = document_client
    created = create_project_evidence(client)["document"]
    document_id = UUID(created["id"])
    storage_path = created["storage_path"]
    repository.completed_links.add(document_id)

    removed = client.post(
        f"/api/v1/documents/{document_id}/archive",
        headers=auth("document-a"),
        json={},
    )
    assert removed.status_code == 200
    assert removed.json()["document"]["archived_at"] is not None
    assert storage_path in storage.objects
    assert client.get("/api/v1/evidence", headers=auth("document-a")).json() == []
    archived = client.get(
        "/api/v1/evidence?include_archived=true",
        headers=auth("document-a"),
    ).json()
    assert archived[0]["usage"]["completed_diagnostic_count"] == 1

    restored = client.post(
        f"/api/v1/documents/{document_id}/restore",
        headers=auth("document-a"),
    )
    assert restored.status_code == 200
    assert restored.json()["document"]["archived_at"] is None


def test_replace_creates_new_version_and_keeps_historical_file(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, repository, storage = document_client
    original = create_project_evidence(client)["document"]
    original_id = UUID(original["id"])
    repository.completed_links.add(original_id)

    response = client.post(
        f"/api/v1/documents/{original_id}/replace",
        headers=auth("document-a"),
        data={"title": "Pricing case study v2", "evidence_category": "CASE_STUDY"},
        files={
            "evidence_file": (
                "pricing-v2.docx",
                text_docx_content("Updated pricing study with quantified outcomes"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    replacement = response.json()["document"]
    assert replacement["version_number"] == 2
    assert replacement["supersedes_document_id"] == str(original_id)
    assert repository.documents[original_id].archived_at is not None
    assert len(storage.objects) == 2
    assert original["storage_path"] in storage.objects
    current = client.get("/api/v1/evidence", headers=auth("document-a")).json()
    assert [item["document"]["id"] for item in current] == [replacement["id"]]


def test_active_diagnostic_blocks_replace_until_explicitly_acknowledged(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, repository, storage = document_client
    original = create_project_evidence(client)["document"]
    original_id = UUID(original["id"])
    repository.protected_links.add(original_id)
    replacement_file = (
        "pricing-v2.docx",
        text_docx_content("Updated pricing evidence"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    blocked = client.post(
        f"/api/v1/documents/{original_id}/replace",
        headers=auth("document-a"),
        data={"title": "Pricing v2", "evidence_category": "PROJECT"},
        files={"evidence_file": replacement_file},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "EVIDENCE_ACTIVE_USE"
    assert len(storage.objects) == 1
    assert repository.documents[original_id].archived_at is None

    replaced = client.post(
        f"/api/v1/documents/{original_id}/replace",
        headers=auth("document-a"),
        data={
            "title": "Pricing v2",
            "evidence_category": "PROJECT",
            "acknowledge_active_use": "true",
        },
        files={"evidence_file": replacement_file},
    )
    assert replaced.status_code == 200
    assert replaced.json()["document"]["supersedes_document_id"] == str(original_id)
    assert len(storage.objects) == 2


def test_failed_replace_removes_new_object_and_leaves_original_unchanged(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, repository, storage = document_client
    original = create_project_evidence(client)["document"]
    original_id = UUID(original["id"])
    repository.fail_replace = True

    response = client.post(
        f"/api/v1/documents/{original_id}/replace",
        headers=auth("document-a"),
        data={"title": "Replacement", "evidence_category": "PROJECT"},
        files={
            "evidence_file": (
                "replacement.docx",
                text_docx_content("Replacement project evidence"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 503
    assert len(storage.objects) == 1
    assert repository.documents[original_id].archived_at is None


def test_download_original_is_owner_scoped(
    document_client: tuple[TestClient, MemoryDocumentRepository, MemoryDocumentStorage],
) -> None:
    client, _, _ = document_client
    created = create_project_evidence(client)["document"]
    document_id = created["id"]
    assert client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth("document-b"),
    ).status_code == 404
    downloaded = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth("document-a"),
    )
    assert downloaded.status_code == 200
    assert b"Pricing research, launch plan and measured outcomes" in downloaded.content

