from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, InvalidAccessToken, get_token_verifier
from app.dependencies import get_onboarding_repository, get_profile_repository
from app.main import app
from app.schemas import OnboardingRead, ProfileRead


USER_ID = UUID("30000000-0000-4000-8000-000000000003")
AUTH = {"Authorization": "Bearer onboarding-token"}


class OnboardingVerifier:
    async def verify(self, token: str) -> AuthenticatedUser:
        if token != "onboarding-token":
            raise InvalidAccessToken
        return AuthenticatedUser(
            id=USER_ID, email="candidate@example.com", full_name="Candidate"
        )


class ProfileStub:
    async def reconcile(self, identity: AuthenticatedUser) -> ProfileRead:
        return ProfileRead(
            id=identity.id, full_name=identity.full_name, email=identity.email
        )


class MemoryOnboardingRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, OnboardingRead] = {USER_ID: OnboardingRead()}

    async def get(self, user_id: UUID) -> OnboardingRead:
        return self.rows[user_id]

    async def update(self, user_id: UUID, values: dict[str, Any]) -> OnboardingRead:
        updated = self.rows[user_id].model_copy(update=values)
        self.rows[user_id] = updated
        return updated


@pytest.fixture
def onboarding_client() -> tuple[TestClient, MemoryOnboardingRepository]:
    repository = MemoryOnboardingRepository()
    app.dependency_overrides[get_token_verifier] = lambda: OnboardingVerifier()
    app.dependency_overrides[get_profile_repository] = lambda: ProfileStub()
    app.dependency_overrides[get_onboarding_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, repository
    app.dependency_overrides.pop(get_profile_repository, None)
    app.dependency_overrides.pop(get_onboarding_repository, None)


def test_onboarding_requires_authentication(
    onboarding_client: tuple[TestClient, MemoryOnboardingRepository],
) -> None:
    client, _ = onboarding_client
    assert client.get("/api/v1/onboarding").status_code == 401
    assert (
        client.put(
            "/api/v1/onboarding", json={"career_intent": "INTERNSHIP"}
        ).status_code
        == 401
    )


def test_onboarding_progress_persists_between_steps(
    onboarding_client: tuple[TestClient, MemoryOnboardingRepository],
) -> None:
    client, _ = onboarding_client
    steps = [
        {"career_stage": "STUDENT", "career_intent": "INTERNSHIP"},
        {"target_role": "  Product   Designer  "},
        {"interview_timeline": "THIS_MONTH"},
        {"preferred_language": "ENGLISH"},
    ]
    for step in steps:
        response = client.put("/api/v1/onboarding", headers=AUTH, json=step)
        assert response.status_code == 200

    persisted = client.get("/api/v1/onboarding", headers=AUTH)
    assert persisted.status_code == 200
    assert persisted.json() == {
        "career_stage": "STUDENT",
        "career_intent": "INTERNSHIP",
        "target_role": "Product Designer",
        "interview_timeline": "THIS_MONTH",
        "preferred_language": "ENGLISH",
        "college_id": None,
        "onboarding_completed": False,
    }

    completed = client.put(
        "/api/v1/onboarding",
        headers=AUTH,
        json={"onboarding_completed": True},
    )
    assert completed.status_code == 200
    assert completed.json()["onboarding_completed"] is True


def test_completion_requires_all_onboarding_fields(
    onboarding_client: tuple[TestClient, MemoryOnboardingRepository],
) -> None:
    client, _ = onboarding_client
    response = client.put(
        "/api/v1/onboarding",
        headers=AUTH,
        json={"onboarding_completed": True},
    )
    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "Complete all required onboarding fields before continuing"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("career_stage", "GRADUATE"),
        ("career_intent", "GET_A_JOB"),
        ("interview_timeline", "TOMORROW"),
        ("preferred_language", "FRENCH"),
    ],
)
def test_invalid_enum_values_are_rejected(
    onboarding_client: tuple[TestClient, MemoryOnboardingRepository],
    field: str,
    value: str,
) -> None:
    client, _ = onboarding_client
    response = client.put("/api/v1/onboarding", headers=AUTH, json={field: value})
    assert response.status_code == 422


def test_onboarding_does_not_accept_user_id(
    onboarding_client: tuple[TestClient, MemoryOnboardingRepository],
) -> None:
    client, _ = onboarding_client
    response = client.put(
        "/api/v1/onboarding",
        headers=AUTH,
        json={"career_intent": "EXPLORING", "user_id": str(UUID(int=4))},
    )
    assert response.status_code == 422

