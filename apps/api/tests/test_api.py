from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, get_token_verifier
from app.main import app
from app.dependencies import get_interview_planning_service
from app.planner_models import PlanningStatus


class TestVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        return AuthenticatedUser(
            id="00000000-0000-4000-8000-000000000001",
            email="candidate@example.com",
        )


client = TestClient(app)
app.dependency_overrides[get_token_verifier] = lambda: TestVerifier()
AUTH = {"Authorization": "Bearer test-access-token"}


def test_create_and_read_session() -> None:
    created = client.post(
        "/api/sessions",
        json={"target_role": "Data Analyst", "jd_text": ""},
        headers=AUTH,
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    fetched = client.get(f"/api/sessions/{session_id}", headers=AUTH)
    assert fetched.status_code == 200
    assert fetched.json()["target_role"] == "Data Analyst"


def test_prepare_moves_created_session_to_ready() -> None:
    class CompletedPlanning:
        async def plan(self, session_id, user_id):
            return type("Plan", (), {"status": PlanningStatus.COMPLETED})()

    app.dependency_overrides[get_interview_planning_service] = (
        lambda: CompletedPlanning()
    )
    created = client.post(
        "/api/sessions", json={"target_role": "Data Analyst"}, headers=AUTH
    ).json()
    response = client.post(f"/api/sessions/{created['id']}/prepare", headers=AUTH)
    app.dependency_overrides.pop(get_interview_planning_service, None)
    assert response.status_code == 200
    assert response.json()["session"]["status"] == "READY"

