from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.assessment_pipeline_models import AssessmentPipelineState, AssessmentPipelineStatus
from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.dashboard_models import DashboardDiagnostic
from app.dashboard_repository import MemoryDashboardRepository
from app.dashboard_service import DashboardService
from app.dependencies import get_dashboard_service
from app.main import app
from app.schemas import Phase, SessionStatus


USER_ID = UUID("a1000000-0000-4000-8000-000000000001")
SESSION_ID = UUID("a2000000-0000-4000-8000-000000000001")
OLDER_SESSION_ID = UUID("a2000000-0000-4000-8000-000000000002")
AUTH = {"Authorization": "Bearer dashboard-token"}


class DashboardVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token != "dashboard-token":
            raise InvalidAccessToken
        return AuthenticatedUser(id=USER_ID, email="candidate@example.com")


def diagnostic(
    session_id: UUID,
    *,
    assessment_status: AssessmentPipelineStatus | None = None,
    available: bool = False,
) -> DashboardDiagnostic:
    now = datetime.now(UTC)
    return DashboardDiagnostic(
        id=session_id,
        target_role="Product Manager",
        interview_status=SessionStatus.COMPLETED,
        phase=Phase.COMPLETE,
        created_at=now,
        updated_at=now,
        completed_at=now,
        assessment=(
            AssessmentPipelineState(
                session_id=session_id,
                status=assessment_status,
                retry_count=0,
                queued_at=now,
            )
            if assessment_status
            else None
        ),
        diagnostic_available=available,
    )


def test_workspace_returns_empty_state_without_sessions() -> None:
    result = asyncio.run(
        DashboardService(MemoryDashboardRepository()).workspace(USER_ID)
    )
    assert result.current is None
    assert result.previous == []


def test_workspace_prioritises_latest_and_preserves_previous_diagnostics() -> None:
    current = diagnostic(SESSION_ID, assessment_status=AssessmentPipelineStatus.PROCESSING)
    previous = diagnostic(
        OLDER_SESSION_ID,
        assessment_status=AssessmentPipelineStatus.COMPLETED,
        available=True,
    )
    result = asyncio.run(
        DashboardService(MemoryDashboardRepository([current, previous])).workspace(USER_ID)
    )
    assert result.current == current
    assert result.previous == [previous]


def test_dashboard_diagnostic_company_is_optional() -> None:
    item = diagnostic(SESSION_ID)
    assert item.company is None


def test_dashboard_endpoint_is_authenticated_and_server_backed() -> None:
    current = diagnostic(SESSION_ID, assessment_status=AssessmentPipelineStatus.PENDING)
    service = DashboardService(MemoryDashboardRepository([current]))
    previous_verifier = app.dependency_overrides.get(get_token_verifier)
    previous_dashboard = app.dependency_overrides.get(get_dashboard_service)
    app.dependency_overrides[get_token_verifier] = lambda: DashboardVerifier()
    app.dependency_overrides[get_dashboard_service] = lambda: service
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/dashboard").status_code == 401
            response = client.get("/api/v1/dashboard", headers=AUTH)
            assert response.status_code == 200
            assert response.json()["current"]["id"] == str(SESSION_ID)
            assert response.json()["current"]["assessment"]["status"] == "PENDING"
    finally:
        if previous_verifier is None:
            app.dependency_overrides.pop(get_token_verifier, None)
        else:
            app.dependency_overrides[get_token_verifier] = previous_verifier
        if previous_dashboard is None:
            app.dependency_overrides.pop(get_dashboard_service, None)
        else:
            app.dependency_overrides[get_dashboard_service] = previous_dashboard
