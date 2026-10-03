from __future__ import annotations

from uuid import UUID

from .dashboard_models import DashboardResponse
from .dashboard_repository import DashboardRepository


class DashboardService:
    def __init__(self, repository: DashboardRepository) -> None:
        self._repository = repository

    async def sessions(self, user_id: UUID, limit: int = 100):
        """The person's sessions, newest first, deeper than the workspace shows."""
        return await self._repository.list_for_user(user_id, limit=limit)

    async def answered_counts(self, user_id: UUID, session_ids: list[UUID]) -> dict[UUID, int]:
        return await self._repository.answered_counts(user_id, session_ids)

    async def workspace(self, user_id: UUID) -> DashboardResponse:
        diagnostics = await self._repository.list_for_user(user_id)
        return DashboardResponse(
            current=diagnostics[0] if diagnostics else None,
            previous=diagnostics[1:],
        )
