from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.dependencies import get_profile_repository
from app.main import app
from app.schemas import ProfileRead


USER_A = AuthenticatedUser(
    id=UUID("10000000-0000-4000-8000-000000000001"),
    email="a@example.com",
    full_name="User A",
)
USER_B = AuthenticatedUser(
    id=UUID("20000000-0000-4000-8000-000000000002"),
    email="b@example.com",
    full_name="User B",
)


class FakeVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token == "token-a":
            return USER_A
        if token == "token-b":
            return USER_B
        raise InvalidAccessToken


class FakeProfileRepository:
    def __init__(self) -> None:
        self.profiles: dict[UUID, ProfileRead] = {}

    async def reconcile(self, identity: AuthenticatedUser) -> ProfileRead:
        profile = self.profiles.get(identity.id)
        if profile is None:
            profile = ProfileRead(
                id=identity.id,
                full_name=identity.full_name,
                email=identity.email,
            )
        elif profile.email != identity.email:
            profile = profile.model_copy(update={"email": identity.email})
        self.profiles[identity.id] = profile
        return profile

    async def update_full_name(self, user_id: UUID, full_name: str) -> ProfileRead:
        profile = self.profiles[user_id].model_copy(update={"full_name": full_name})
        self.profiles[user_id] = profile
        return profile


@pytest.fixture
def auth_client() -> tuple[TestClient, FakeProfileRepository]:
    profiles = FakeProfileRepository()
    app.dependency_overrides[get_token_verifier] = lambda: FakeVerifier()
    app.dependency_overrides[get_profile_repository] = lambda: profiles
    with TestClient(app) as client:
        yield client, profiles
    app.dependency_overrides.pop(get_profile_repository, None)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_no_token_returns_401(
    auth_client: tuple[TestClient, FakeProfileRepository],
) -> None:
    client, _ = auth_client
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_token_returns_401(
    auth_client: tuple[TestClient, FakeProfileRepository],
) -> None:
    client, _ = auth_client
    response = client.get("/api/v1/me", headers=auth("not-valid"))
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_authenticated_request_reconciles_profile(
    auth_client: tuple[TestClient, FakeProfileRepository],
) -> None:
    client, profiles = auth_client
    response = client.get("/api/v1/me", headers=auth("token-a"))
    assert response.status_code == 200
    assert response.json() == {
        "id": str(USER_A.id),
        "full_name": "User A",
        "email": "a@example.com",
    }
    assert set(profiles.profiles) == {USER_A.id}


def test_user_isolation(auth_client: tuple[TestClient, FakeProfileRepository]) -> None:
    client, profiles = auth_client
    profile_a = client.get("/api/v1/me", headers=auth("token-a")).json()
    profile_b = client.get("/api/v1/me", headers=auth("token-b")).json()

    assert profile_a["id"] == str(USER_A.id)
    assert profile_b["id"] == str(USER_B.id)
    assert profile_b["email"] != profile_a["email"]
    assert set(profiles.profiles) == {USER_A.id, USER_B.id}


def test_profile_update_is_scoped_to_authenticated_user(
    auth_client: tuple[TestClient, FakeProfileRepository],
) -> None:
    client, profiles = auth_client
    client.get("/api/v1/me", headers=auth("token-b"))
    response = client.patch(
        "/api/v1/me",
        headers=auth("token-a"),
        json={"full_name": "  Alice   Example  "},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Alice Example"
    assert response.json()["id"] == str(USER_A.id)
    assert profiles.profiles[USER_B.id].full_name == "User B"

    forbidden = client.patch(
        "/api/v1/me",
        headers=auth("token-a"),
        json={"full_name": "Alice", "id": str(USER_B.id)},
    )
    assert forbidden.status_code == 422

