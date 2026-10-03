"""My plan routes. Wired by the coordinator with ``app.include_router(routes_plan.router)``.

`GET /api/v1/plan?role_profile_id=<optional>` -> Plan for that role, else for the active role.
`PUT /api/v1/plan/{role_profile_id}/areas/{area_key}/link` {evidence_item_id | story_id, confirmed}
confirms or dismisses one link and returns the rebuilt plan. A role, item or story that is not
the person's is 404.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from .auth import AuthenticatedUser, get_current_user
from .career_evidence import EvidenceUnavailable
from .config import get_settings
from .dashboard_repository import DashboardUnavailable
from .dependencies import get_readiness_service, get_role_analysis_service, get_story_repository
from .document_repository import DocumentUnavailable
from .onboarding_repository import OnboardingUnavailable
from .plan_service import (
    CoverageLinkRepository,
    CoverageLinksUnavailable,
    LinkChoice,
    MemoryCoverageLinkRepository,
    Plan,
    SupabaseCoverageLinkRepository,
    build_plan,
    no_role_plan,
)
from .readiness_service import ReadinessService, story_evidence
from .resume_repository import ResumeAnalysisUnavailable
from .role_repository import RoleAnalysisUnavailable
from .role_service import RoleAnalysisService, RoleProfileNotFoundForUser
from .routes_active_role import RolePreferenceStore, _active_role, get_role_preference_store
from .story_repository import StoriesUnavailable, StoryRepository

router = APIRouter(prefix="/api/v1/plan", tags=["plan"])

NOT_FOUND_ROLE = "We couldn't find that role."
NOT_FOUND_NEED = "We couldn't find that part of your plan."
NOT_FOUND_ITEM = "We couldn't find that example."
UNAVAILABLE = "Your plan isn't available right now. Please try again in a moment."
STORAGE_ERRORS = (
    RoleAnalysisUnavailable, DocumentUnavailable, StoriesUnavailable, DashboardUnavailable,
    EvidenceUnavailable, ResumeAnalysisUnavailable, OnboardingUnavailable, CoverageLinksUnavailable,
)


@lru_cache
def get_coverage_link_repository() -> CoverageLinkRepository:
    settings = get_settings()
    if not settings.supabase_enabled:
        return MemoryCoverageLinkRepository()
    try:
        return SupabaseCoverageLinkRepository(settings)
    except CoverageLinksUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE) from exc


async def _load(
    user_id: UUID,
    role_profile_id: UUID,
    readiness: ReadinessService,
    stories: StoryRepository,
    links: CoverageLinkRepository,
) -> Plan:
    """Raises RoleProfileNotFoundForUser for a role that is not the person's."""
    interview_map = await readiness.interview_map(role_profile_id, user_id)
    framed = {item.story_id: item.themes for item in await stories.framings_for_user(user_id, role_profile_id)}
    return build_plan(
        interview_map,
        await readiness.approved_evidence(user_id) or [],
        [story_evidence(story, framed.get(story.id, ())) for story in await stories.list_for_user(user_id)],
        await links.list_for_role(user_id, role_profile_id),
    )


@router.get("", response_model=Plan)
async def read_plan(
    role_profile_id: UUID | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    readiness: ReadinessService = Depends(get_readiness_service),
    roles: RoleAnalysisService = Depends(get_role_analysis_service),
    preferences: RolePreferenceStore = Depends(get_role_preference_store),
    stories: StoryRepository = Depends(get_story_repository),
    links: CoverageLinkRepository = Depends(get_coverage_link_repository),
) -> Plan:
    """Each need of the role once, with what you already have and the next step."""
    try:
        if role_profile_id is None:
            active = (await _active_role(user.id, roles, preferences)).role
            if active is None:
                return no_role_plan()
            role_profile_id = active.role_profile_id
        return await _load(user.id, role_profile_id, readiness, stories, links)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_ROLE) from exc
    except STORAGE_ERRORS as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE) from exc


@router.put("/{role_profile_id}/areas/{area_key}/link", response_model=Plan)
async def choose_link(
    role_profile_id: UUID,
    area_key: str,
    choice: LinkChoice,
    user: AuthenticatedUser = Depends(get_current_user),
    readiness: ReadinessService = Depends(get_readiness_service),
    stories: StoryRepository = Depends(get_story_repository),
    links: CoverageLinkRepository = Depends(get_coverage_link_repository),
) -> Plan:
    """Confirm (`confirmed: true`) or dismiss (`false`) one example or story for one need."""
    try:
        interview_map = await readiness.interview_map(role_profile_id, user.id)
        if all(theme.key != area_key for theme in interview_map.themes):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_NEED)
        if choice.evidence_item_id is not None:
            approved = await readiness.approved_evidence(user.id) or []
            if all(item.id != choice.evidence_item_id for item in approved):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_ITEM)
        elif await stories.get(choice.story_id, user.id) is None:  # type: ignore[arg-type]
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_ITEM)
        await links.save(user.id, role_profile_id, area_key, choice)
        return await _load(user.id, role_profile_id, readiness, stories, links)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_ROLE) from exc
    except STORAGE_ERRORS as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE) from exc


async def plan_glance(user_id: UUID, role_profile_id: UUID) -> list[dict[str, Any]]:
    """For Home: each plan need as {key, title, status}. Raises like the GET route's loaders do."""
    plan = await _load(user_id, role_profile_id, get_readiness_service(), get_story_repository(), get_coverage_link_repository())
    return [{"key": area.key, "title": area.title, "status": area.status.value} for area in plan.areas]
