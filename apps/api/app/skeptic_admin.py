from __future__ import annotations

from uuid import UUID

from .skeptic_models import SkepticAdminSessionResult
from .skeptic_repository import SkepticRepository


class AdminAccessRequired(Exception):
    pass


class SkepticSessionNotFound(Exception):
    pass


class SkepticAdminService:
    def __init__(self, repository: SkepticRepository) -> None:
        self._repository = repository

    async def inspect(
        self, session_id: UUID, requesting_user_id: UUID
    ) -> SkepticAdminSessionResult:
        if not await self._repository.is_admin(requesting_user_id):
            raise AdminAccessRequired
        result = await self._repository.inspect_session(session_id)
        if result is None:
            raise SkepticSessionNotFound
        return result

