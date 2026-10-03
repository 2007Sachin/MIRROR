"""The active role: one role at a time, stored in `profiles.current_role_profile_id`.

`GET /api/v1/active-role` -> {"role": {role_profile_id, target_role} | null, "roles": [...]}
with one entry per role name (its newest profile). The active role is the stored id, else
the onboarding role, else the newest role; a stored id counts while it is any profile of
one of this person's roles, and is reported as that role's newest profile.

`PUT /api/v1/active-role` {"role_profile_id"} stores the role's newest profile id. A role
that is not this person's is 404. Switching never creates or changes a practice session.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from .auth import AuthenticatedUser, get_current_user
from .dependencies import get_onboarding_repository, get_role_analysis_service
from .home_service import preferred_role
from .onboarding_repository import OnboardingUnavailable
from .role_repository import RoleAnalysisUnavailable
from .role_service import RoleAnalysisService

logger = logging.getLogger("mirror.active_role")
router = APIRouter()

_UNAVAILABLE = "Your roles aren't available right now. Please try again in a moment."


class RolePreferenceStore(Protocol):
    async def role_preference(self, user_id: UUID) -> tuple[UUID | None, UUID | None]: ...
    async def set_current_role(self, user_id: UUID, role_profile_id: UUID) -> None: ...


def get_role_preference_store() -> RolePreferenceStore:
    return get_onboarding_repository()


class ActiveRoleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActiveRole(ActiveRoleModel):
    role_profile_id: UUID
    target_role: str


class ActiveRoleResponse(ActiveRoleModel):
    role: ActiveRole | None = None
    roles: list[ActiveRole]


class ActiveRoleUpdate(ActiveRoleModel):
    role_profile_id: UUID


async def stored_role_preference(user_id: UUID) -> Sequence[UUID | None]:
    """For Home: the stored preference, or none when it cannot be read (Home then chooses as before)."""
    try:
        return await get_role_preference_store().role_preference(user_id)
    except (OnboardingUnavailable, HTTPException):
        logger.warning("active role preference unavailable", extra={"user_id": str(user_id)}, exc_info=True)
        return ()


async def _active_role(user_id: UUID, roles: RoleAnalysisService, store: RolePreferenceStore) -> ActiveRoleResponse:
    families = await roles.families(user_id)
    listed = [ActiveRole(role_profile_id=profile.id, target_role=profile.target_role) for profile, _ in families]
    chosen = preferred_role(families, await store.role_preference(user_id)) or (families[0] if families else None)
    role = ActiveRole(role_profile_id=chosen[0].id, target_role=chosen[0].target_role) if chosen else None
    return ActiveRoleResponse(role=role, roles=listed)


@router.get("/api/v1/active-role", response_model=ActiveRoleResponse)
async def read_active_role(
    user: AuthenticatedUser = Depends(get_current_user),
    roles: RoleAnalysisService = Depends(get_role_analysis_service),
    store: RolePreferenceStore = Depends(get_role_preference_store),
) -> ActiveRoleResponse:
    try:
        return await _active_role(user.id, roles, store)
    except (RoleAnalysisUnavailable, OnboardingUnavailable) as exc:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from exc


@router.put("/api/v1/active-role", response_model=ActiveRoleResponse)
async def update_active_role(
    payload: ActiveRoleUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    roles: RoleAnalysisService = Depends(get_role_analysis_service),
    store: RolePreferenceStore = Depends(get_role_preference_store),
) -> ActiveRoleResponse:
    try:
        families = await roles.families(user.id)
        chosen = preferred_role(families, [payload.role_profile_id])
        if chosen is None:
            raise HTTPException(status_code=404, detail="We couldn't find that role.")
        await store.set_current_role(user.id, chosen[0].id)
        return await _active_role(user.id, roles, store)
    except (RoleAnalysisUnavailable, OnboardingUnavailable) as exc:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from exc
