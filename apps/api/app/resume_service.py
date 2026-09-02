from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from .agents.definitions import AgentExecutionContext
from .agents.resume import (
    RESUME_AGENT_NAME,
    RESUME_ANALYSIS_VERSION,
    RESUME_PROMPT_VERSION,
)
from .agents.runner import AgentRunner
from .document_parsing import DocumentParsingError, ResumeDocumentParser
from .document_repository import DocumentRepository, DocumentStorage
from .resume_models import (
    CandidateProfileContext,
    ClaimCorrectionCreate,
    ResumeAgentOutput,
    ResumeAgentInput,
    ResumeAnalysisResponse,
)
from .resume_repository import ResumeAnalysisRepository
from .schemas import DocumentStatus, DocumentType, OnboardingRead


class ResumeNotFound(Exception):
    pass


class UnsupportedResumeDocument(Exception):
    pass


class ResumeAnalysisService:
    def __init__(
        self,
        documents: DocumentRepository,
        storage: DocumentStorage,
        parser: ResumeDocumentParser,
        analyses: ResumeAnalysisRepository,
        runner: AgentRunner,
        *,
        model: str,
    ) -> None:
        self._documents = documents
        self._storage = storage
        self._parser = parser
        self._analyses = analyses
        self._runner = runner
        self._model = model

    async def analyze(
        self, document_id: UUID, user_id: UUID, profile: OnboardingRead
    ) -> ResumeAnalysisResponse:
        document = await self._owned_resume(document_id, user_id)
        analysis, started = await self._analyses.begin(
            document_id,
            user_id,
            model=self._model,
            prompt_version=RESUME_PROMPT_VERSION,
            analysis_version=RESUME_ANALYSIS_VERSION,
        )
        if not started:
            return ResumeAnalysisResponse(**analysis.model_dump(), claims=[])

        try:
            resume_text = document.raw_text or await self._parse_document(
                document, user_id
            )
        except DocumentParsingError:
            failed = await self._analyses.fail(
                analysis.id,
                user_id,
                execution_id=None,
                error_type="document_parsing_failure",
            )
            return ResumeAnalysisResponse(**failed.model_dump(), claims=[])

        candidate_profile = CandidateProfileContext(
            career_stage=profile.career_stage.value if profile.career_stage else None,
            target_role=profile.target_role,
            preferred_language=(
                profile.preferred_language.value if profile.preferred_language else None
            ),
        )
        result = await self._runner.run(
            RESUME_AGENT_NAME,
            ResumeAgentInput(
                document_id=document.id,
                user_id=user_id,
                resume_text=resume_text,
                candidate_profile=candidate_profile,
            ),
            context=AgentExecutionContext(user_id=user_id),
        )
        if not result.success or result.output is None:
            failed = await self._analyses.fail(
                analysis.id,
                user_id,
                execution_id=result.execution_id,
                error_type=result.error_type.value
                if result.error_type
                else "internal_failure",
            )
            return ResumeAnalysisResponse(**failed.model_dump(), claims=[])

        output = ResumeAgentOutput.model_validate(result.output)
        return await self._analyses.complete(
            analysis.id, user_id, result.execution_id, output
        )

    async def get(self, document_id: UUID, user_id: UUID) -> ResumeAnalysisResponse:
        await self._owned_resume(document_id, user_id)
        analysis = await self._analyses.get_latest(document_id, user_id)
        if analysis is None:
            raise ResumeNotFound
        return analysis

    async def correct_claim(
        self,
        document_id: UUID,
        user_id: UUID,
        claim_id: UUID,
        correction: ClaimCorrectionCreate,
    ) -> ResumeAnalysisResponse:
        await self._owned_resume(document_id, user_id)
        return await self._analyses.add_correction(
            document_id, user_id, claim_id, correction
        )

    async def _owned_resume(self, document_id: UUID, user_id: UUID):
        document = await self._documents.get_for_user(document_id, user_id)
        if document is None:
            raise ResumeNotFound
        if document.document_type != DocumentType.RESUME:
            raise UnsupportedResumeDocument
        return document

    async def _parse_document(self, document, user_id: UUID) -> str:
        if not document.storage_path or not document.mime_type:
            raise DocumentParsingError("resume source is unavailable")
        await self._documents.update_owned(
            document.id,
            user_id,
            {"status": DocumentStatus.PROCESSING, "error_message": None},
        )
        try:
            content = await self._storage.download(document.storage_path)
            text = self._parser.extract(content, document.mime_type)
        except Exception as exc:
            await self._documents.update_owned(
                document.id,
                user_id,
                {
                    "status": DocumentStatus.FAILED,
                    "error_message": "Resume text could not be extracted",
                },
            )
            if isinstance(exc, DocumentParsingError):
                raise
            raise DocumentParsingError("resume source could not be read") from exc
        await self._documents.update_owned(
            document.id,
            user_id,
            {
                "status": DocumentStatus.PROCESSED,
                "raw_text": text,
                "processed_at": datetime.now(UTC).isoformat(),
                "error_message": None,
            },
        )
        return text

