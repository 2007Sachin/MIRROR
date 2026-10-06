"""Loop 2 interview-target routes (owner-scoped; wired in main.py with the redesign routers).

GET  /api/v1/targets                                   {availability, targets}
POST /api/v1/targets                                   201 {target, blueprint}   (409 same active scope)
GET  /api/v1/targets/{id}                              target
POST /api/v1/targets/{id}/archive                      target (scope never changes; no PUT/PATCH)
GET  /api/v1/targets/{id}/blueprint[?version=n]        pinned blueprint content (old pins still served)
POST /api/v1/targets/{id}/blueprint/refresh            201 new pin | 200 already current
GET  /api/v1/targets/{id}/rounds/{round_key}           round detail (claims, unknowns, priorities, pack)
POST /api/v1/targets/{id}/rounds/{round_key}/practice  201 session + write-once link (no prompt text)
GET  /api/v1/targets/{id}/progress                     role progress over this target's linked sessions
GET  /api/v1/sessions/{session_id}/target              {availability, link|null}

Schema state: reads return ``availability`` with empty data unless AVAILABLE; writes answer
503 ``TARGETS_NOT_AVAILABLE`` before any side effect. Anything that is not the caller's is 404.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from .auth import AuthenticatedUser, get_current_user
from .config import get_settings
from .dependencies import (
    get_interview_state_machine,
    get_role_analysis_service,
    get_role_progress_service,
    get_story_repository,
)
from .interview_engine import SessionNotFound
from .role_repository import RoleAnalysisUnavailable
from .role_service import RoleProfileNotFoundForUser
from .story_repository import StoriesUnavailable
from .target_capability import TargetAvailability, TargetCapability
from .target_repository import (
    MemoryTargetRepository,
    SupabaseTargetRepository,
    TargetConflict,
    TargetRepository,
    TargetsUnavailable,
)
from .target_service import (
    BlueprintNotFound,
    BlueprintView,
    CatalogProvider,
    CatalogUnavailable,
    LinkConflict,
    PracticeStart,
    PracticeStarted,
    RepoCatalogProvider,
    RoundDetail,
    RoundNotFound,
    ShortPack,
    TargetArchived,
    TargetCreate,
    TargetNotFound,
    TargetService,
    target_view,
)

logger = logging.getLogger("mirror.targets")
router = APIRouter(tags=["targets"])

NOT_FOUND = "We couldn't find that target."
NOT_FOUND_ROUND = "We couldn't find that round."
NOT_FOUND_SESSION = "We couldn't find that session."
UNAVAILABLE = "Targets aren't available right now. Please try again in a moment."
NOT_AVAILABLE = {"code": "TARGETS_NOT_AVAILABLE", "message": "Targets aren't available yet."}
STORAGE_ERRORS = (TargetsUnavailable, RoleAnalysisUnavailable, StoriesUnavailable, CatalogUnavailable)


# ------------------------------------------------------------------ dependencies


@lru_cache
def get_target_repository() -> TargetRepository:
    settings = get_settings()
    if not settings.supabase_enabled:
        return MemoryTargetRepository()
    return SupabaseTargetRepository(settings)


@lru_cache
def get_target_capability() -> TargetCapability:
    settings = get_settings()
    return TargetCapability(
        settings.loop2_targets_enabled,
        get_target_repository().probe,
        ttl_seconds=settings.loop2_target_probe_ttl_seconds,
    )


@lru_cache
def get_catalog_provider() -> CatalogProvider:
    return RepoCatalogProvider()


def get_target_service(
    repo: TargetRepository = Depends(get_target_repository),
    catalogs: CatalogProvider = Depends(get_catalog_provider),
    roles: Any = Depends(get_role_analysis_service),
    stories: Any = Depends(get_story_repository),
    engine: Any = Depends(get_interview_state_machine),
) -> TargetService:
    return TargetService(repo, catalogs, roles, stories, engine)


async def availability(capability: TargetCapability = Depends(get_target_capability)) -> TargetAvailability:
    try:
        return await capability.state()
    except TargetsUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE) from exc


async def require_available(
    _: AuthenticatedUser = Depends(get_current_user),
    state: TargetAvailability = Depends(availability),
) -> None:
    """Writes stop here, after auth but before storage, catalog or session calls."""
    if state != TargetAvailability.AVAILABLE:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=NOT_AVAILABLE)


def _unavailable(exc: Exception) -> HTTPException:
    logger.warning("target storage unavailable", exc_info=exc)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=UNAVAILABLE)


# ------------------------------------------------------------------ targets


@router.get("/api/v1/targets")
async def list_targets(
    user: AuthenticatedUser = Depends(get_current_user),
    state: TargetAvailability = Depends(availability),
    service: TargetService = Depends(get_target_service),
) -> dict[str, Any]:
    if state != TargetAvailability.AVAILABLE:
        return {"availability": state.value, "targets": []}
    try:
        targets = await service.list(user.id)
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc
    return {"availability": state.value, "targets": [target_view(t).model_dump(mode="json") for t in targets]}


@router.post("/api/v1/targets", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_available)])
async def create_target(
    payload: TargetCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TargetService = Depends(get_target_service),
) -> dict[str, Any]:
    try:
        target, blueprint = await service.create(user.id, payload)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that role.") from exc
    except TargetConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "TARGET_EXISTS", "target_id": str(exc.existing_id) if exc.existing_id else None},
        ) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc
    return {
        "target": target_view(target).model_dump(mode="json"),
        "blueprint": {"version": blueprint.version, "catalog_version": blueprint.catalog_version, "match_state": blueprint.match_state},
    }


@router.get("/api/v1/targets/{target_id}")
async def read_target(
    target_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    state: TargetAvailability = Depends(availability),
    service: TargetService = Depends(get_target_service),
) -> dict[str, Any]:
    if state != TargetAvailability.AVAILABLE:
        return {"availability": state.value, "target": None}
    try:
        target = await service.get(target_id, user.id)
    except TargetNotFound as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc
    return {"availability": state.value, "target": target_view(target).model_dump(mode="json")}


@router.post("/api/v1/targets/{target_id}/archive", dependencies=[Depends(require_available)])
async def archive_target(
    target_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TargetService = Depends(get_target_service),
) -> dict[str, Any]:
    try:
        return target_view(await service.archive(target_id, user.id)).model_dump(mode="json")
    except TargetNotFound as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc


# ------------------------------------------------------------------ blueprint


@router.get("/api/v1/targets/{target_id}/blueprint", response_model=BlueprintView)
async def read_blueprint(
    target_id: UUID,
    version: int | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    state: TargetAvailability = Depends(availability),
    service: TargetService = Depends(get_target_service),
) -> BlueprintView:
    if state != TargetAvailability.AVAILABLE:
        return BlueprintView(availability=state)
    try:
        return await service.blueprint(target_id, user.id, version)
    except (TargetNotFound, BlueprintNotFound) as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc


@router.post(
    "/api/v1/targets/{target_id}/blueprint/refresh",
    response_model=BlueprintView,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_available)],
)
async def refresh_blueprint(
    target_id: UUID,
    response: Response,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TargetService = Depends(get_target_service),
) -> BlueprintView:
    try:
        view, created = await service.refresh(target_id, user.id)
    except TargetNotFound as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc
    except TargetArchived as exc:
        raise HTTPException(status_code=409, detail={"code": "TARGET_ARCHIVED"}) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return view


# ------------------------------------------------------------------ rounds


@router.get("/api/v1/targets/{target_id}/rounds/{round_key}", response_model=RoundDetail)
async def read_round(
    target_id: UUID,
    round_key: str,
    user: AuthenticatedUser = Depends(get_current_user),
    state: TargetAvailability = Depends(availability),
    service: TargetService = Depends(get_target_service),
) -> RoundDetail:
    if state != TargetAvailability.AVAILABLE:
        return RoundDetail(availability=state)
    try:
        return await service.round_detail(target_id, round_key, user.id)
    except (TargetNotFound, BlueprintNotFound) as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc
    except RoundNotFound as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND_ROUND) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc


@router.post(
    "/api/v1/targets/{target_id}/rounds/{round_key}/practice",
    response_model=PracticeStarted,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_available)],
)
async def start_round_practice(
    target_id: UUID,
    round_key: str,
    payload: PracticeStart,
    user: AuthenticatedUser = Depends(get_current_user),
    service: TargetService = Depends(get_target_service),
) -> PracticeStarted:
    try:
        return await service.start_round_practice(target_id, round_key, user.id, payload)
    except (TargetNotFound, RoleProfileNotFoundForUser, LookupError) as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc
    except RoundNotFound as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND_ROUND) from exc
    except TargetArchived as exc:
        raise HTTPException(status_code=409, detail={"code": "TARGET_ARCHIVED"}) from exc
    except LinkConflict as exc:
        raise HTTPException(status_code=409, detail={"code": "SESSION_ALREADY_LINKED"}) from exc
    except ShortPack as exc:
        raise HTTPException(
            status_code=422, detail={"code": "SHORT_PACK", "available": exc.available},
        ) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc


# ------------------------------------------------------------------ sessions and progress


@router.get("/api/v1/sessions/{session_id}/target")
async def read_session_target(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    state: TargetAvailability = Depends(availability),
    service: TargetService = Depends(get_target_service),
    engine: Any = Depends(get_interview_state_machine),
) -> dict[str, Any]:
    if state != TargetAvailability.AVAILABLE:
        return {"availability": state.value, "link": None}
    try:
        await engine.get_state(session_id, user.id)
        link = await service.session_link(session_id, user.id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND_SESSION) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc
    return {"availability": state.value, "link": link.model_dump(mode="json") if link else None}


@router.get("/api/v1/targets/{target_id}/progress")
async def read_target_progress(
    target_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    state: TargetAvailability = Depends(availability),
    service: TargetService = Depends(get_target_service),
    progress: Any = Depends(get_role_progress_service),
) -> dict[str, Any]:
    if state != TargetAvailability.AVAILABLE:
        return {"availability": state.value, "progress": None}
    try:
        target, session_ids = await service.linked_session_ids(target_id, user.id)
        result = await progress.target_detail(target.role_profile_id, user.id, session_ids)
    except (TargetNotFound, RoleProfileNotFoundForUser) as exc:
        raise HTTPException(status_code=404, detail=NOT_FOUND) from exc
    except STORAGE_ERRORS as exc:
        raise _unavailable(exc) from exc
    body = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    return {"availability": state.value, "target_id": str(target.id), "progress": body}
