"""Error responses carry CORS headers, so the browser can read them and show a calm message."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.config import get_settings
from app.dependencies import get_home_service
from app.main import app
from tests.test_role_agent import RoleVerifier

A = {"Authorization": "Bearer role-a"}
ORIGIN = get_settings().app_url


class BrokenHome:
    def __init__(self, error):
        self.error = error

    async def home(self, user_id, requested_role=None):
        raise self.error


@pytest.fixture
def client():
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_token_verifier, None)
    app.dependency_overrides.pop(get_home_service, None)


def assert_cors(response, status):
    assert response.status_code == status
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_not_found_and_invalid_input_carry_cors(client) -> None:
    app.dependency_overrides[get_home_service] = lambda: BrokenHome(RuntimeError("never reached"))
    assert_cors(client.get("/api/v1/does-not-exist", headers={"Origin": ORIGIN}), 404)
    assert_cors(client.get("/api/v1/home?role_profile_id=nope", headers={**A, "Origin": ORIGIN}), 422)
    assert_cors(client.get("/api/v1/home", headers={"Origin": ORIGIN}), 401)


def test_unavailable_carries_cors(client) -> None:
    app.dependency_overrides[get_home_service] = lambda: BrokenHome(HTTPException(status_code=503, detail="down"))
    assert_cors(client.get("/api/v1/home", headers={**A, "Origin": ORIGIN}), 503)


def test_an_unexpected_error_is_a_calm_json_500_with_cors(client) -> None:
    app.dependency_overrides[get_home_service] = lambda: BrokenHome(RuntimeError("boom"))
    response = client.get("/api/v1/home", headers={**A, "Origin": ORIGIN})
    assert_cors(response, 500)
    assert response.json() == {"detail": "We couldn't finish that just now. Please try again in a moment."}
    assert "boom" not in response.text
