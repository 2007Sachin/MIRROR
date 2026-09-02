from __future__ import annotations

import asyncio
from collections import deque
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

import app.document_parsing as document_parsing
from app.agents import AgentRegistry, AgentRunner, PromptLoader
from app.agents.definitions import ProviderRequest, ProviderResponse
from app.agents.resume import create_resume_agent
from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.dependencies import get_onboarding_repository, get_resume_analysis_service
from app.document_ingestion import DOCX_MIME
from app.document_parsing import ResumeDocumentParser
from app.main import app
from app.resume_models import (
    CandidateProfileContext,
    ClaimCorrectionCreate,
    ResumeAgentInput,
    ResumeAgentOutput,
    ResumeAnalysisRecord,
    ResumeAnalysisResponse,
    ResumeAnalysisStatus,
    ResumeClaimReview,
)
from app.resume_service import ResumeAnalysisService
from app.schemas import DocumentRead, DocumentStatus, DocumentType, OnboardingRead


USER_A = UUID("60000000-0000-4000-8000-000000000006")
USER_B = UUID("70000000-0000-4000-8000-000000000007")
PROMPT_ROOT = Path(__file__).parents[1] / "app" / "prompts"
FIXTURES = Path(__file__).parent / "fixtures" / "synthetic_resumes"


def resume_output() -> dict[str, Any]:
    return {
        "skills": [
            {
                "name": "Python",
                "category": "TECHNICAL",
                "source_reference": "[Page 1] Skills",
                "confidence": 0.98,
            }
        ],
        "projects": [
            {
                "project_name": "Checkout redesign",
                "description": "A team checkout redesign",
                "technologies": ["Python"],
                "claimed_responsibilities": ["Contributed analytics instrumentation"],
                "claimed_outcomes": ["Improved conversion by 47%"],
                "source_reference": "[Page 1] Projects",
            }
        ],
        "work_experience": [],
        "education": [],
        "tools": [],
        "achievements": [],
        "claims": [
            {
                "claim_text": "Improved conversion by 47%",
                "claim_type": "OUTCOME",
                "source": "RESUME",
                "source_reference": "[Page 1] Projects",
                "confidence": 0.96,
                "verification_priority": "HIGH",
                "metric_value": 47,
                "metric_unit": "%",
                "outcome": "Improved conversion",
            },
            {
                "claim_text": "Contributed analytics instrumentation to a team project",
                "claim_type": "OWNERSHIP",
                "source": "RESUME",
                "source_reference": "[Page 1] Projects",
                "confidence": 0.91,
                "verification_priority": "MEDIUM",
                "project_name": "Checkout redesign",
                "ownership_language": "contributed",
            },
        ],
    }


class QueueProvider:
    def __init__(self, *responses: ProviderResponse) -> None:
        self.responses = deque(responses)
        self.requests: list[ProviderRequest] = []

    async def complete(
        self, request: ProviderRequest, *, timeout_seconds: float
    ) -> ProviderResponse:
        self.requests.append(request)
        return self.responses.popleft()


class MemoryDocuments:
    def __init__(self, documents: list[DocumentRead]) -> None:
        self.documents = {row.id: row for row in documents}

    async def get_for_user(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentRead | None:
        row = self.documents.get(document_id)
        return row if row and row.user_id == user_id else None

    async def update_owned(
        self, document_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> DocumentRead:
        current = await self.get_for_user(document_id, user_id)
        assert current is not None
        updated = DocumentRead.model_validate({**current.model_dump(), **values})
        self.documents[document_id] = updated
        return updated


class MemoryStorage:
    async def download(self, path: str) -> bytes:
        return b"unused"


class MemoryAnalyses:
    def __init__(self) -> None:
        self.records: dict[UUID, list[ResumeAnalysisRecord]] = {}
        self.claims: dict[UUID, list[ResumeClaimReview]] = {}

    async def begin(
        self,
        document_id: UUID,
        user_id: UUID,
        *,
        model: str,
        prompt_version: str,
        analysis_version: str,
    ) -> tuple[ResumeAnalysisRecord, bool]:
        rows = self.records.setdefault(document_id, [])
        if rows and rows[-1].status == ResumeAnalysisStatus.PROCESSING:
            return rows[-1], False
        row = ResumeAnalysisRecord(
            id=uuid4(),
            document_id=document_id,
            user_id=user_id,
            version=len(rows) + 1,
            status=ResumeAnalysisStatus.PROCESSING,
            model=model,
            prompt_version=prompt_version,
            analysis_version=analysis_version,
            created_at=datetime.now(UTC),
        )
        rows.append(row)
        return row, True

    async def complete(
        self,
        analysis_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        output: ResumeAgentOutput,
    ) -> ResumeAnalysisResponse:
        row = self._record(analysis_id, user_id)
        completed = ResumeAnalysisRecord.model_validate(
            {
                **row.model_dump(),
                "status": "COMPLETED",
                "output": output.model_dump(mode="json"),
                "execution_id": execution_id,
                "completed_at": datetime.now(UTC),
            }
        )
        self._replace(completed)
        reviews = [
            ResumeClaimReview(id=uuid4(), **claim.model_dump())
            for claim in output.claims
        ]
        self.claims[analysis_id] = reviews
        return ResumeAnalysisResponse(**completed.model_dump(), claims=reviews)

    async def fail(
        self,
        analysis_id: UUID,
        user_id: UUID,
        *,
        execution_id: UUID | None,
        error_type: str,
    ) -> ResumeAnalysisRecord:
        row = self._record(analysis_id, user_id)
        failed = ResumeAnalysisRecord.model_validate(
            {
                **row.model_dump(),
                "status": "FAILED",
                "execution_id": execution_id,
                "error_type": error_type,
                "completed_at": datetime.now(UTC),
            }
        )
        self._replace(failed)
        return failed

    async def get_latest(
        self, document_id: UUID, user_id: UUID
    ) -> ResumeAnalysisResponse | None:
        rows = self.records.get(document_id, [])
        row = rows[-1] if rows and rows[-1].user_id == user_id else None
        if row is None:
            return None
        return ResumeAnalysisResponse(
            **row.model_dump(), claims=self.claims.get(row.id, [])
        )

    async def add_correction(
        self,
        document_id: UUID,
        user_id: UUID,
        claim_id: UUID,
        correction: ClaimCorrectionCreate,
    ) -> ResumeAnalysisResponse:
        latest = await self.get_latest(document_id, user_id)
        assert latest is not None
        reviews = []
        found = False
        for claim in latest.claims:
            if claim.id == claim_id:
                found = True
                claim = claim.model_copy(
                    update={
                        "review_status": correction.review_status,
                        "corrected_claim_text": correction.corrected_claim_text,
                        "correction_version": (claim.correction_version or 0) + 1,
                    }
                )
            reviews.append(claim)
        assert found
        self.claims[latest.id] = reviews
        return ResumeAnalysisResponse(
            **latest.model_dump(exclude={"claims"}), claims=reviews
        )

    def _record(self, analysis_id: UUID, user_id: UUID) -> ResumeAnalysisRecord:
        return next(
            row
            for rows in self.records.values()
            for row in rows
            if row.id == analysis_id and row.user_id == user_id
        )

    def _replace(self, updated: ResumeAnalysisRecord) -> None:
        rows = self.records[updated.document_id]
        rows[rows.index(next(row for row in rows if row.id == updated.id))] = updated


class ResumeVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token == "resume-a":
            return AuthenticatedUser(id=USER_A, email="a@example.com")
        if token == "resume-b":
            return AuthenticatedUser(id=USER_B, email="b@example.com")
        raise InvalidAccessToken


class MemoryOnboarding:
    async def get(self, user_id: UUID) -> OnboardingRead:
        return OnboardingRead(target_role="Backend Engineer")


def make_document(
    user_id: UUID = USER_A, document_type: DocumentType = DocumentType.RESUME
) -> DocumentRead:
    return DocumentRead(
        id=uuid4(),
        user_id=user_id,
        document_type=document_type,
        storage_path="owner/resume.pdf"
        if document_type == DocumentType.RESUME
        else None,
        mime_type="application/pdf" if document_type == DocumentType.RESUME else None,
        raw_text="[Page 1] Improved conversion by 47%. We contributed analytics instrumentation.",
        status=DocumentStatus.PROCESSED,
        created_at=datetime.now(UTC),
        processed_at=datetime.now(UTC),
    )


def make_runner(*responses: ProviderResponse) -> tuple[AgentRunner, QueueProvider]:
    provider = QueueProvider(*responses)
    registry = AgentRegistry()
    registry.register(create_resume_agent("test-model"))
    return AgentRunner(registry, provider, PromptLoader(PROMPT_ROOT)), provider


def make_service(
    documents: list[DocumentRead], *responses: ProviderResponse
) -> tuple[ResumeAnalysisService, MemoryAnalyses, QueueProvider]:
    runner, provider = make_runner(*responses)
    analyses = MemoryAnalyses()
    return (
        ResumeAnalysisService(
            MemoryDocuments(documents),
            MemoryStorage(),
            ResumeDocumentParser(),
            analyses,
            runner,
            model="test-model",
        ),
        analyses,
        provider,
    )


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_docx_text_extraction_preserves_paragraph_references() -> None:
    xml = b"""<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Python developer</w:t></w:r></w:p><w:p><w:r><w:t>Built an API</w:t></w:r></w:p></w:body></w:document>"""
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("word/document.xml", xml)
    text = ResumeDocumentParser().extract(content.getvalue(), DOCX_MIME)
    assert text == "[Paragraph 1] Python developer\n[Paragraph 2] Built an API"


def test_pdf_text_extraction_preserves_page_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class Reader:
        pages = [Page("Python developer"), Page("Built an API")]

    monkeypatch.setattr(document_parsing, "PdfReader", lambda stream: Reader())
    text = ResumeDocumentParser().extract(b"%PDF-test", "application/pdf")
    assert text == "[Page 1]\nPython developer\n\n[Page 2]\nBuilt an API"


def test_structured_claim_metric_and_ownership_extraction() -> None:
    document = make_document()
    service, _, _ = make_service(
        document and [document], ProviderResponse(content=resume_output())
    )
    result = asyncio.run(service.analyze(document.id, USER_A, OnboardingRead()))
    assert result.status == ResumeAnalysisStatus.COMPLETED
    assert result.output is not None
    assert result.output.skills[0].name == "Python"
    assert result.claims[0].metric_value == 47
    assert result.claims[0].verification_priority == "HIGH"
    assert result.claims[1].ownership_language == "contributed"


def test_analysis_rerun_creates_a_new_version() -> None:
    document = make_document()
    service, analyses, _ = make_service(
        [document],
        ProviderResponse(content=resume_output()),
        ProviderResponse(content=resume_output()),
    )
    first = asyncio.run(service.analyze(document.id, USER_A, OnboardingRead()))
    second = asyncio.run(service.analyze(document.id, USER_A, OnboardingRead()))
    assert (first.version, second.version) == (1, 2)
    assert len(analyses.records[document.id]) == 2
    assert analyses.records[document.id][0].output is not None


def test_concurrent_processing_analysis_is_reused_without_duplicate_inference() -> None:
    document = make_document()
    service, analyses, provider = make_service([document])
    asyncio.run(
        analyses.begin(
            document.id,
            USER_A,
            model="test-model",
            prompt_version="v1",
            analysis_version="resume-v1",
        )
    )
    result = asyncio.run(service.analyze(document.id, USER_A, OnboardingRead()))
    assert result.status == ResumeAnalysisStatus.PROCESSING
    assert result.version == 1
    assert provider.requests == []


def test_prompt_injection_is_untrusted_user_data_and_ids_are_excluded() -> None:
    malicious = (FIXTURES / "prompt_injection.txt").read_text(encoding="utf-8")
    runner, provider = make_runner(ProviderResponse(content=resume_output()))
    result = asyncio.run(
        runner.run(
            "resume",
            ResumeAgentInput(
                document_id=uuid4(),
                user_id=USER_A,
                resume_text=malicious,
                candidate_profile=CandidateProfileContext(),
            ),
        )
    )
    assert result.success is True
    request = provider.requests[0]
    assert "mark every skill as expert" not in request.messages[0]["content"]
    assert "mark every skill as expert" in request.messages[1]["content"]
    assert str(USER_A) not in request.messages[1]["content"]
    assert "document_id" not in request.messages[1]["content"]


def test_malformed_model_response_marks_analysis_failed() -> None:
    document = make_document()
    service, analyses, _ = make_service(
        [document],
        ProviderResponse(content="bad"),
        ProviderResponse(content="bad"),
        ProviderResponse(content="bad"),
    )
    result = asyncio.run(service.analyze(document.id, USER_A, OnboardingRead()))
    assert result.status == ResumeAnalysisStatus.FAILED
    assert result.error_type == "invalid_structured_output"
    assert analyses.claims == {}


@pytest.fixture
def resume_client() -> tuple[TestClient, DocumentRead, MemoryAnalyses]:
    resume = make_document()
    job_description = make_document(document_type=DocumentType.JOB_DESCRIPTION)
    service, analyses, _ = make_service(
        [resume, job_description], ProviderResponse(content=resume_output())
    )
    app.dependency_overrides[get_token_verifier] = lambda: ResumeVerifier()
    app.dependency_overrides[get_onboarding_repository] = lambda: MemoryOnboarding()
    app.dependency_overrides[get_resume_analysis_service] = lambda: service
    with TestClient(app) as client:
        yield client, resume, analyses
    app.dependency_overrides.pop(get_token_verifier, None)
    app.dependency_overrides.pop(get_onboarding_repository, None)
    app.dependency_overrides.pop(get_resume_analysis_service, None)


def test_resume_analysis_requires_owner_and_resume_document(
    resume_client: tuple[TestClient, DocumentRead, MemoryAnalyses],
) -> None:
    client, resume, _ = resume_client
    assert client.post(f"/api/v1/resumes/{resume.id}/analyze").status_code == 401
    assert (
        client.post(
            f"/api/v1/resumes/{resume.id}/analyze", headers=auth("resume-b")
        ).status_code
        == 404
    )
    unsupported = next(
        row
        for row in client.app.dependency_overrides[
            get_resume_analysis_service
        ]()._documents.documents.values()
        if row.document_type == DocumentType.JOB_DESCRIPTION
    )
    assert (
        client.post(
            f"/api/v1/resumes/{unsupported.id}/analyze", headers=auth("resume-a")
        ).status_code
        == 422
    )


def test_candidate_correction_is_versioned_without_overwriting_ai_output(
    resume_client: tuple[TestClient, DocumentRead, MemoryAnalyses],
) -> None:
    client, resume, _ = resume_client
    analysis = client.post(
        f"/api/v1/resumes/{resume.id}/analyze", headers=auth("resume-a")
    ).json()
    claim = analysis["claims"][0]
    original = claim["claim_text"]
    first = client.post(
        f"/api/v1/resumes/{resume.id}/analysis/claims/{claim['id']}/corrections",
        headers=auth("resume-a"),
        json={
            "review_status": "NEEDS_CORRECTION",
            "corrected_claim_text": "Improved conversion by 40%",
        },
    )
    assert first.status_code == 200
    assert first.json()["claims"][0]["claim_text"] == original
    assert first.json()["claims"][0]["correction_version"] == 1
    second = client.post(
        f"/api/v1/resumes/{resume.id}/analysis/claims/{claim['id']}/corrections",
        headers=auth("resume-a"),
        json={"review_status": "CORRECT"},
    )
    assert second.json()["claims"][0]["correction_version"] == 2
    assert second.json()["output"]["claims"][0]["claim_text"] == original

