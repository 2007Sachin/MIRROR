"""GET /api/v1/home: signed in, owner-scoped, and honest when something is down."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dashboard_repository import DashboardUnavailable
from app.dependencies import get_home_service
from app.home_service import HomeResponse, HomeState
from app.main import app
from app.role_service import RoleProfileNotFoundForUser
from tests.test_role_agent import RoleVerifier

A = {"Authorization": "Bearer role-a"}


class FakeHome:
    def __init__(self, outcome):
        self.outcome, self.seen = outcome, []

    async def home(self, user_id, requested_role=None):
        self.seen.append((user_id, requested_role))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def client_with(outcome):
    fake = FakeHome(outcome)
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_home_service] = lambda: fake
    return TestClient(app), fake


@pytest.fixture(autouse=True)
def cleanup():
    yield
    for dependency in (get_token_verifier, get_home_service):
        app.dependency_overrides.pop(dependency, None)


def test_home_requires_a_signed_in_person() -> None:
    client, _ = client_with(HomeResponse(state=HomeState.NO_ROLE, roles=[]))
    assert client.get("/api/v1/home").status_code == 401


def test_home_returns_the_servers_decision_for_the_signed_in_user_only() -> None:
    client, fake = client_with(HomeResponse(state=HomeState.NO_ROLE, roles=[]))
    response = client.get("/api/v1/home", headers=A)
    assert response.status_code == 200 and response.json()["state"] == "NO_ROLE"
    assert len(fake.seen) == 1 and fake.seen[0][1] is None  # the user id comes from the token, not the request


def test_a_role_id_is_passed_on_for_the_service_to_verify() -> None:
    role = uuid4()
    client, fake = client_with(HomeResponse(state=HomeState.NO_ROLE, roles=[]))
    client.get(f"/api/v1/home?role_profile_id={role}", headers=A)
    assert fake.seen[0][1] == role


def test_a_role_that_is_not_yours_is_not_found() -> None:
    client, _ = client_with(RoleProfileNotFoundForUser())
    response = client.get(f"/api/v1/home?role_profile_id={uuid4()}", headers=A)
    assert response.status_code == 404


def test_a_junk_role_id_is_rejected_before_any_read() -> None:
    client, fake = client_with(HomeResponse(state=HomeState.NO_ROLE, roles=[]))
    assert client.get("/api/v1/home?role_profile_id=not-an-id", headers=A).status_code == 422
    assert fake.seen == []


def test_an_outage_is_an_error_not_an_empty_home() -> None:
    client, _ = client_with(DashboardUnavailable("down"))
    response = client.get("/api/v1/home", headers=A)
    assert response.status_code == 503 and "state" not in response.json()


def test_an_upcoming_interview_is_part_of_the_response() -> None:
    from datetime import UTC, datetime

    from app.home_service import UpcomingInterview

    upcoming = UpcomingInterview(event_id=uuid4(), role_profile_id=uuid4(), target_role="Data Analyst",
                                 scheduled_for=datetime.now(UTC), round_kind="HR", company_label=None)
    client, _ = client_with(HomeResponse(state=HomeState.NO_ROLE, roles=[], upcoming_interview=upcoming))
    body = client.get("/api/v1/home", headers=A).json()
    assert body["upcoming_interview"]["round_kind"] == "HR" and body["upcoming_interview"]["event_id"] == str(upcoming.event_id)
    assert client_with(HomeResponse(state=HomeState.NO_ROLE, roles=[]))[0].get("/api/v1/home", headers=A).json()["upcoming_interview"] is None
