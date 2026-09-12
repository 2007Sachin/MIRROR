from __future__ import annotations

from uuid import UUID

from .dashboard_models import DashboardResponse
from .dashboard_repository import DashboardRepository


class DashboardService:
    def __init__(self, repository: DashboardRepository) -> None:
        self._repository = repository

    async def workspace(self, user_id: UUID) -> DashboardResponse:
        diagnostics = await self._repository.list_for_user(user_id)
        return DashboardResponse(
            current=diagnostics[0] if diagnostics else None,
            previous=diagnostics[1:],
        )
