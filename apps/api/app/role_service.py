from __future__ import annotations

from uuid import UUID, uuid4

from .agents.definitions import AgentExecutionContext
from .agents.role import ROLE_AGENT_NAME, ROLE_ANALYSIS_VERSION, ROLE_PROMPT_VERSION
from .agents.runner import AgentRunner
from .document_repository import DocumentRepository
from .role_canonical import load_canonical_role
from .role_models import (
    CompetencySourceType,
    RoleAgentInput,
    RoleAgentOutput,
    RoleAnalysisResponse,
    RoleAnalyzeRequest,
    RoleSourceType,
    StoredRoleCompetency,
)
from .role_repository import RoleAnalysisRepository
from .schemas import DocumentStatus, DocumentType, OnboardingRead


class RoleProfileNotFoundForUser(Exception):
    pass


class InvalidRoleSourceDocument(Exception):
    pass


class RoleProfileTargetMismatch(Exception):
    pass


class RoleAnalysisService:
    def __init__(
        self,
        documents: DocumentRepository,
        analyses: RoleAnalysisRepository,
        runner: AgentRunner,
        *,
        model: str,
    ) -> None:
        self._documents = documents
        self._analyses = analyses
        self._runner = runner
        self._model = model

    async def analyze(
        self, request: RoleAnalyzeRequest, user_id: UUID, onboarding: OnboardingRead
    ) -> RoleAnalysisResponse:
        jd_text, source_document_id = await self._resolve_job_description(
            request, user_id
        )
        source_type = (
            RoleSourceType.JOB_DESCRIPTION
            if jd_text
            else RoleSourceType.SYNTHETIC_CANONICAL
        )
        if request.role_profile_id:
            profile = await self._analyses.get_profile(request.role_profile_id, user_id)
            if profile is None:
                raise RoleProfileNotFoundForUser
            if profile.target_role.casefold() != request.target_role.casefold():
                raise RoleProfileTargetMismatch
        else:
            profile = await self._analyses.create_profile(
                user_id,
                request.target_role,
                source_type,
                source_document_id,
            )

        canonical = load_canonical_role(request.target_role) if not jd_text else None
        model = "synthetic-canonical-v1" if canonical else self._model
        prompt_version = "canonical-v1" if canonical else ROLE_PROMPT_VERSION
        analysis, started = await self._analyses.begin(
            profile.id,
            user_id,
            source_type=source_type,
            source_document_id=source_document_id,
            model=model,
            prompt_version=prompt_version,
            analysis_version=ROLE_ANALYSIS_VERSION,
        )
        if not started:
            current = await self._analyses.get(profile.id, user_id)
            if current is None:
                raise RoleProfileNotFoundForUser
            return current

        if canonical:
            return await self._analyses.complete(
                analysis.id, user_id, uuid4(), canonical
            )

        result = await self._runner.run(
            ROLE_AGENT_NAME,
            RoleAgentInput(
                target_role=request.target_role,
                job_description_text=jd_text,
                career_stage=(
                    onboarding.career_stage.value if onboarding.career_stage else None
                ),
            ),
            context=AgentExecutionContext(user_id=user_id),
        )
        if not result.success or result.output is None:
            return await self._analyses.fail(
                analysis.id,
                user_id,
                result.execution_id,
                result.error_type.value if result.error_type else "internal_failure",
            )

        output = RoleAgentOutput.model_validate(result.output)
        if not self._source_types_match(output, source_type):
            return await self._analyses.fail(
                analysis.id,
                user_id,
                result.execution_id,
                "source_validation_failure",
            )
        return await self._analyses.complete(
            analysis.id, user_id, result.execution_id, output
        )

    async def get(self, profile_id: UUID, user_id: UUID) -> RoleAnalysisResponse:
        result = await self._analyses.get(profile_id, user_id)
        if result is None:
            raise RoleProfileNotFoundForUser
        return result

    async def competencies(
        self, profile_id: UUID, user_id: UUID
    ) -> list[StoredRoleCompetency]:
        result = await self._analyses.competencies(profile_id, user_id)
        if result is None:
            raise RoleProfileNotFoundForUser
        return result

    async def _resolve_job_description(
        self, request: RoleAnalyzeRequest, user_id: UUID
    ) -> tuple[str | None, UUID | None]:
        if request.job_description_document_id is None:
            return request.job_description_text, None
        document = await self._documents.get_for_user(
            request.job_description_document_id, user_id
        )
        if document is None:
            raise InvalidRoleSourceDocument
        if (
            document.document_type != DocumentType.JOB_DESCRIPTION
            or document.status != DocumentStatus.PROCESSED
            or not document.raw_text
        ):
            raise InvalidRoleSourceDocument
        return document.raw_text, document.id

    @staticmethod
    def _source_types_match(output: RoleAgentOutput, expected: RoleSourceType) -> bool:
        if output.source_type != expected:
            return False
        allowed = (
            {
                CompetencySourceType.JOB_DESCRIPTION_EXPLICIT,
                CompetencySourceType.JOB_DESCRIPTION_INFERRED,
            }
            if expected == RoleSourceType.JOB_DESCRIPTION
            else {CompetencySourceType.SYNTHETIC_CANONICAL}
        )
        return all(item.source_type in allowed for item in output.competencies)

