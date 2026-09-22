"""Loads what the readiness features read, then hands it to the deterministic builders.

Everything is owner-scoped: each read goes through a service or repository that
takes the authenticated user id, never an id supplied by the client.
"""

from __future__ import annotations

from uuid import UUID

from .document_repository import DocumentRepository
from .interview_map import InterviewMap, StoryEvidence, build_interview_map
from .pressure_test import PressureResponse, PressureTest, Readiness, build_pressure_test
from .progress_summary import ProgressService
from .resume_models import ResumeAnalysisResponse
from .resume_service import ResumeAnalysisService, ResumeNotFound
from .role_models import RoleAnalysisResponse
from .role_service import RoleAnalysisService
from .schemas import DocumentRead, DocumentType, EvidenceCategory
from .story_models import STORY_PARTS, StoryRead
from .story_repository import PressureResponseRepository, StoryRepository


class ClaimNotFoundForUser(Exception):
    """The statement is not on this person's current resume."""


def story_evidence(story: StoryRead) -> StoryEvidence:
    text = " ".join(filter(None, (getattr(story, part) for part in STORY_PARTS)))
    return StoryEvidence(id=story.id, title=story.title, themes=tuple(story.themes), text=text)


def newest_resume(documents: list[DocumentRead]) -> DocumentRead | None:
    resumes = [
        document for document in documents
        if document.archived_at is None
        and document.document_type == DocumentType.RESUME
        and (document.evidence_category in (None, EvidenceCategory.RESUME))
    ]
    resumes.sort(key=lambda item: item.updated_at or item.created_at, reverse=True)
    return resumes[0] if resumes else None


class ReadinessService:
    def __init__(
        self,
        roles: RoleAnalysisService,
        documents: DocumentRepository,
        resumes: ResumeAnalysisService,
        stories: StoryRepository,
        progress: ProgressService | None,
        responses: PressureResponseRepository | None = None,
    ) -> None:
        self._responses = responses
        self._roles = roles
        self._documents = documents
        self._resumes = resumes
        self._stories = stories
        self._progress = progress

    async def role(self, role_profile_id: UUID, user_id: UUID) -> RoleAnalysisResponse:
        return await self._roles.get(role_profile_id, user_id)  # raises for another user's role

    async def resume(self, user_id: UUID) -> tuple[DocumentRead | None, ResumeAnalysisResponse | None]:
        document = newest_resume(await self._documents.list_for_user(user_id))
        if document is None:
            return None, None
        try:
            return document, await self._resumes.get(document.id, user_id)
        except ResumeNotFound:
            return document, None  # uploaded but never read

    async def interview_map(self, role_profile_id: UUID, user_id: UUID) -> InterviewMap:
        role = await self.role(role_profile_id, user_id)
        document, resume = await self.resume(user_id)
        stories = await self._stories.list_for_user(user_id)
        latest = await self._progress.latest(user_id, role.target_role) if self._progress else None
        return build_interview_map(
            role,
            resume,
            has_resume_document=document is not None,
            stories=[story_evidence(story) for story in stories],
            latest_review=latest,
        )

    async def pressure_test(self, role_profile_id: UUID, user_id: UUID) -> PressureTest:
        role = await self.role(role_profile_id, user_id)
        document, resume = await self.resume(user_id)
        responses = await self._responses.list_for_user(user_id) if self._responses else {}
        stories = await self._stories.list_for_user(user_id)
        return build_pressure_test(
            role,
            resume,
            has_resume_document=document is not None,
            responses={claim: Readiness(value) for claim, value in responses.items()},
            stories_by_claim={story.source_claim_id: story.id for story in stories if story.source_claim_id},
        )

    async def set_readiness(self, claim_id: UUID, user_id: UUID, readiness: Readiness) -> PressureResponse:
        """Only a statement on the person's own current resume can be marked."""
        _, resume = await self.resume(user_id)
        if resume is None or all(claim.id != claim_id for claim in resume.claims):
            raise ClaimNotFoundForUser
        if self._responses is None:
            raise ClaimNotFoundForUser
        updated = await self._responses.upsert(user_id, claim_id, readiness.value)
        return PressureResponse(claim_id=claim_id, readiness=readiness, updated_at=updated)
