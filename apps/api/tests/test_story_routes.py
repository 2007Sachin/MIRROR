"""My Stories routes: owner-scoped, validated, and honest about completeness."""

import pytest
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import get_onboarding_repository, get_role_analysis_service, get_story_repository
from app.main import app
from app.story_models import StoryCompleteness, StoryCreate, story_completeness
from app.story_repository import MemoryStoryRepository
from tests.test_role_agent import MemoryOnboarding, RoleVerifier, make_service

A = {"Authorization": "Bearer role-a"}
B = {"Authorization": "Bearer role-b"}


@pytest.fixture
def client():
    stories = MemoryStoryRepository()
    service, _, _ = make_service()
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_story_repository] = lambda: stories
    app.dependency_overrides[get_role_analysis_service] = lambda: service
    app.dependency_overrides[get_onboarding_repository] = lambda: MemoryOnboarding()
    with TestClient(app) as test_client:
        yield test_client
    for dependency in (get_token_verifier, get_story_repository, get_role_analysis_service, get_onboarding_repository):
        app.dependency_overrides.pop(dependency, None)


def test_a_story_can_be_created_read_updated_and_deleted_by_its_owner(client) -> None:
    created = client.post("/api/v1/stories", headers=A, json={"title": "Rebuilding the pricing model", "themes": ["Pricing", " pricing "]})
    assert created.status_code == 201
    story = created.json()
    assert story["themes"] == ["Pricing"]  # duplicates folded
    assert story["completeness"] == "STARTED"

    updated = client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={
        "situation": "Prices were set by hand", "actions": "I built a model", "outcome": "Margins held",
    })
    assert updated.json()["completeness"] == "DEVELOPING"
    assert client.get("/api/v1/stories", headers=A).json()[0]["id"] == story["id"]

    assert client.delete(f"/api/v1/stories/{story['id']}", headers=A).status_code == 204
    assert client.get(f"/api/v1/stories/{story['id']}", headers=A).status_code == 404


def test_another_person_can_never_see_change_or_delete_a_story(client) -> None:
    story = client.post("/api/v1/stories", headers=A, json={"title": "Mine"}).json()
    assert client.get(f"/api/v1/stories/{story['id']}", headers=B).status_code == 404
    assert client.patch(f"/api/v1/stories/{story['id']}", headers=B, json={"title": "Taken"}).status_code == 404
    assert client.delete(f"/api/v1/stories/{story['id']}", headers=B).status_code == 404
    assert client.get("/api/v1/stories", headers=B).json() == []
    assert client.get("/api/v1/stories").status_code == 401


def test_a_story_cannot_point_at_someone_elses_role(client) -> None:
    role = client.post("/api/v1/roles/analyze", headers=A, json={"target_role": "Software Engineer"}).json()
    assert client.post("/api/v1/stories", headers=B, json={"title": "Borrowed", "role_profile_id": role["id"]}).status_code == 404
    assert client.post("/api/v1/stories", headers=A, json={"title": "Mine", "role_profile_id": role["id"]}).status_code == 201


def test_invalid_stories_are_rejected(client) -> None:
    assert client.post("/api/v1/stories", headers=A, json={"title": "x"}).status_code == 422
    assert client.post("/api/v1/stories", headers=A, json={"title": "Fine", "themes": ["t"] * 13}).status_code == 422


def test_completeness_counts_written_parts_and_never_judges_them() -> None:
    assert story_completeness(StoryCreate(title="Title"))[0] == StoryCompleteness.STARTED
    core = StoryCreate(title="Title", situation="s", actions="a", outcome="o")
    assert story_completeness(core)[0] == StoryCompleteness.DEVELOPING
    full = core.model_copy(update={"ownership": "mine", "reasoning": "because"})
    state, missing = story_completeness(full)
    assert state == StoryCompleteness.READY and "measurable_result" in missing
    assert story_completeness(StoryCreate(title="Title", situation="   ", actions="a", outcome="o"))[0] == StoryCompleteness.STARTED
