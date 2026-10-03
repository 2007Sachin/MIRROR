"""Story history and archive: one story, many read-only versions, reversible archiving."""

import pytest
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import get_onboarding_repository, get_role_analysis_service, get_story_repository
from app.main import app
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


def _create(client, headers=A, **values):
    response = client.post("/api/v1/stories", headers=headers, json={"title": "Rebuilding the pricing model", **values})
    assert response.status_code == 201
    return response.json()


def _versions(client, story_id, headers=A):
    response = client.get(f"/api/v1/stories/{story_id}/versions", headers=headers)
    assert response.status_code == 200
    return response.json()


def _edit(client, story_id, headers=A, **values):
    return client.patch(f"/api/v1/stories/{story_id}", headers=headers, json=values)


# ------------------------------------------------------------------ versions


def test_a_new_story_starts_with_one_version(client) -> None:
    story = _create(client, situation="Prices were set by hand")
    assert story["current_version"] == 1
    [first] = _versions(client, story["id"])
    assert first["version"] == 1 and first["change_reason"] == "CREATED"
    assert first["situation"] == "Prices were set by hand" and first["story_id"] == story["id"]


def test_each_edit_adds_a_version_and_keeps_the_same_story(client) -> None:
    story = _create(client, situation="v1 situation")
    second = _edit(client, story["id"], situation="v2 situation").json()
    third = _edit(client, story["id"], actions="v3 actions").json()

    assert second["id"] == third["id"] == story["id"]
    assert (second["current_version"], third["current_version"]) == (2, 3)
    versions = _versions(client, story["id"])
    assert [item["version"] for item in versions] == [3, 2, 1]  # newest first
    assert [item["change_reason"] for item in versions] == ["MANUAL_EDIT", "MANUAL_EDIT", "CREATED"]
    assert len(client.get("/api/v1/stories", headers=A).json()) == 1


def test_saving_unchanged_content_does_not_add_a_version(client) -> None:
    story = _create(client, situation="Same", themes=["Pricing"])
    again = _edit(client, story["id"], title=story["title"], situation="  Same  ", themes=["Pricing"])
    assert again.status_code == 200 and again.json()["current_version"] == 1
    assert _edit(client, story["id"]).json()["current_version"] == 1  # empty save
    assert len(_versions(client, story["id"])) == 1


def test_earlier_versions_never_change_after_later_edits(client) -> None:
    story = _create(client, situation="Original situation", outcome="Original outcome")
    first = _versions(client, story["id"])[0]
    _edit(client, story["id"], situation="Rewritten")
    _edit(client, story["id"], outcome="Rewritten outcome", title="A new title")

    still = client.get(f"/api/v1/stories/{story['id']}/versions/{first['id']}", headers=A)
    assert still.status_code == 200
    assert still.json() == first


def test_restoring_an_earlier_version_creates_a_new_current_version(client) -> None:
    story = _create(client, situation="v1", outcome="first outcome")
    _edit(client, story["id"], situation="v2")
    _edit(client, story["id"], situation="v3", outcome="third outcome")
    before = {item["version"]: item for item in _versions(client, story["id"])}

    restored = client.post(f"/api/v1/stories/{story['id']}/versions/{before[1]['id']}/restore", headers=A)
    assert restored.status_code == 200
    current = restored.json()
    assert current["id"] == story["id"] and current["current_version"] == 4
    assert (current["situation"], current["outcome"]) == ("v1", "first outcome")

    after = {item["version"]: item for item in _versions(client, story["id"])}
    assert sorted(after) == [1, 2, 3, 4]
    assert after[4]["change_reason"] == "RESTORED" and after[4]["restored_from_version"] == 1
    assert all(after[number] == before[number] for number in (1, 2, 3))  # history untouched


def test_restoring_the_version_already_current_adds_nothing(client) -> None:
    story = _create(client, situation="only")
    [first] = _versions(client, story["id"])
    restored = client.post(f"/api/v1/stories/{story['id']}/versions/{first['id']}/restore", headers=A)
    assert restored.json()["current_version"] == 1 and len(_versions(client, story["id"])) == 1


def test_history_belongs_only_to_the_stories_owner(client) -> None:
    story = _create(client, situation="mine")
    [first] = _versions(client, story["id"])
    theirs = _create(client, headers=B, title="Their story")
    [their_first] = _versions(client, theirs["id"], headers=B)

    assert client.get(f"/api/v1/stories/{story['id']}/versions", headers=B).status_code == 404
    assert client.get(f"/api/v1/stories/{story['id']}/versions/{first['id']}", headers=B).status_code == 404
    assert client.post(f"/api/v1/stories/{story['id']}/versions/{first['id']}/restore", headers=B).status_code == 404
    # A version id from another story, even one's own, never crosses over.
    assert client.get(f"/api/v1/stories/{theirs['id']}/versions/{first['id']}", headers=B).status_code == 404
    assert client.post(f"/api/v1/stories/{story['id']}/versions/{their_first['id']}/restore", headers=A).status_code == 404
    assert client.get(f"/api/v1/stories/{story['id']}/versions").status_code == 401
    assert client.get(f"/api/v1/stories/{story['id']}", headers=A).json()["current_version"] == 1


def test_a_story_from_dig_deeper_has_its_first_version_straight_away(client) -> None:
    story = _create(client, origin="PRESSURE_TEST", source_text="Built pricing models", situation="From my answer")
    [first] = _versions(client, story["id"])
    assert first["change_reason"] == "CREATED" and first["situation"] == "From my answer"
    fetched = client.get(f"/api/v1/stories/{story['id']}", headers=A).json()
    assert fetched["origin"] == "PRESSURE_TEST" and fetched["source_text"] == "Built pricing models"


# ------------------------------------------------------------------ archive


def test_an_archived_story_leaves_the_active_list_and_can_be_restored(client) -> None:
    story = _create(client, situation="kept")
    _edit(client, story["id"], situation="kept, edited")

    archived = client.post(f"/api/v1/stories/{story['id']}/archive", headers=A)
    assert archived.status_code == 200 and archived.json()["archived_at"]
    assert client.get("/api/v1/stories", headers=A).json() == []
    assert [item["id"] for item in client.get("/api/v1/stories?archived=true", headers=A).json()] == [story["id"]]
    assert client.get(f"/api/v1/stories/{story['id']}", headers=A).status_code == 200  # old links still open
    assert len(_versions(client, story["id"])) == 2  # history survives, archiving is not a version

    restored = client.post(f"/api/v1/stories/{story['id']}/restore", headers=A).json()
    assert restored["id"] == story["id"] and restored["archived_at"] is None
    assert restored["origin"] == story["origin"] and restored["current_version"] == 2
    assert [item["id"] for item in client.get("/api/v1/stories", headers=A).json()] == [story["id"]]
    assert client.get("/api/v1/stories?archived=true", headers=A).json() == []
    assert len(_versions(client, story["id"])) == 2


def test_archiving_or_restoring_twice_changes_nothing(client) -> None:
    story = _create(client)
    first = client.post(f"/api/v1/stories/{story['id']}/archive", headers=A).json()
    again = client.post(f"/api/v1/stories/{story['id']}/archive", headers=A).json()
    assert first["archived_at"] == again["archived_at"]
    client.post(f"/api/v1/stories/{story['id']}/restore", headers=A)
    assert client.post(f"/api/v1/stories/{story['id']}/restore", headers=A).json()["archived_at"] is None


def test_an_archived_story_is_read_only_until_restored(client) -> None:
    story = _create(client, situation="v1")
    _edit(client, story["id"], situation="v2")
    first = _versions(client, story["id"])[-1]
    client.post(f"/api/v1/stories/{story['id']}/archive", headers=A)

    assert _edit(client, story["id"], situation="while archived").status_code == 409
    assert client.post(f"/api/v1/stories/{story['id']}/versions/{first['id']}/restore", headers=A).status_code == 409
    assert len(_versions(client, story["id"])) == 2


def test_another_person_cannot_archive_or_restore_a_story(client) -> None:
    story = _create(client)
    assert client.post(f"/api/v1/stories/{story['id']}/archive", headers=B).status_code == 404
    assert client.get(f"/api/v1/stories/{story['id']}", headers=A).json()["archived_at"] is None
    client.post(f"/api/v1/stories/{story['id']}/archive", headers=A)
    assert client.post(f"/api/v1/stories/{story['id']}/restore", headers=B).status_code == 404
    assert client.get("/api/v1/stories?archived=true", headers=B).json() == []
    assert client.get(f"/api/v1/stories/{story['id']}", headers=A).json()["archived_at"] is not None


def test_stories_can_no_longer_be_hard_deleted(client) -> None:
    story = _create(client)
    assert client.delete(f"/api/v1/stories/{story['id']}", headers=A).status_code == 405
    assert client.get(f"/api/v1/stories/{story['id']}", headers=A).status_code == 200
