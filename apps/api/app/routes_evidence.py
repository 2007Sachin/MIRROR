"""Career Evidence routes: review, edit, approve and merge the experience Mirror found.

Wired by the coordinator with ``app.include_router(routes_evidence.router)``.
"""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from .auth import AuthenticatedUser, get_current_user
from .career_evidence import (
    CareerEvidenceService,
    EvidenceApprove,
    EvidenceItem,
    EvidenceList,
    EvidenceMerge,
    EvidenceMergeInvalid,
    EvidenceNotFound,
    EvidenceRepository,
    EvidenceUnavailable,
    EvidenceUpdate,
    MemoryEvidenceRepository,
    SupabaseEvidenceRepository,
)
from .config import get_settings
from .document_repository import DocumentUnavailable
from .resume_repository import ResumeAnalysisUnavailable

router = APIRouter(prefix="/api/v1/career-evidence", tags=["evidence"])

NOT_FOUND = "We couldn't find that item."
UNAVAILABLE = "Your experience isn't available right now. Please try again in a moment."
STORAGE_ERRORS = (EvidenceUnavailable, DocumentUnavailable, ResumeAnalysisUnavailable)


@lru_cache
def get_evidence_repository() -> EvidenceRepository:
    settings = get_settings()
    if not settings.supabase_enabled:
        return MemoryEvidenceRepository()
    try:
        return SupabaseEvidenceRepository(settings)
    except EvidenceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE) from exc


def get_career_evidence_service() -> CareerEvidenceService:
    from .dependencies import get_document_repository, get_resume_analysis_service

    return CareerEvidenceService(get_evidence_repository(), get_document_repository(), get_resume_analysis_service())


def _unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE)


@router.get("", response_model=EvidenceList)
async def list_evidence(
    user: AuthenticatedUser = Depends(get_current_user),
    service: CareerEvidenceService = Depends(get_career_evidence_service),
) -> EvidenceList:
    """The experience found on your newest resume, for you to review."""
    try:
        return await service.list(user.id)
    except STORAGE_ERRORS as exc:
        raise _unavailable() from exc


@router.post("/approve", response_model=list[EvidenceItem])
async def approve_evidence(
    body: EvidenceApprove,
    user: AuthenticatedUser = Depends(get_current_user),
    service: CareerEvidenceService = Depends(get_career_evidence_service),
) -> list[EvidenceItem]:
    try:
        return await service.approve(user.id, body.ids)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable() from exc


@router.patch("/{item_id}", response_model=EvidenceItem)
async def update_evidence(
    item_id: UUID,
    body: EvidenceUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    service: CareerEvidenceService = Depends(get_career_evidence_service),
) -> EvidenceItem:
    try:
        return await service.update(user.id, item_id, body)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable() from exc


@router.post("/{item_id}/merge", response_model=EvidenceItem)
async def merge_evidence(
    item_id: UUID,
    body: EvidenceMerge,
    user: AuthenticatedUser = Depends(get_current_user),
    service: CareerEvidenceService = Depends(get_career_evidence_service),
) -> EvidenceItem:
    try:
        return await service.merge(user.id, item_id, body.into)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from exc
    except EvidenceMergeInvalid as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable() from exc
