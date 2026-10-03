"""One story, useful for zero, one or many roles, by exact role id. Framing never copies content."""

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


def _role(client, label="Product Manager", headers=A) -> str:
    response = client.post("/api/v1/roles/analyze", headers=headers, json={"target_role": label})
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


def _story(client, headers=A, **values):
    response = client.post("/api/v1/stories", headers=headers, json={"title": "Fixing delivery delays", **values})
    assert response.status_code == 201, response.text
    return response.json()


def _roles(client, story_id, headers=A):
    response = client.get(f"/api/v1/stories/{story_id}/roles", headers=headers)
    assert response.status_code == 200
    return response.json()


def _frame(client, story_id, role_id, headers=A, **values):
    return client.put(f"/api/v1/stories/{story_id}/roles/{role_id}", headers=headers, json=values)


# ------------------------------------------------------------------ zero, one, many


def test_a_story_can_be_useful_across_roles_with_no_role_at_all(client) -> None:
    story = _story(client, themes=["Process improvement"])
    assert story["role_profile_ids"] == [] and _roles(client, story["id"]) == []


def test_a_story_written_for_a_role_is_useful_for_that_role(client) -> None:
    role = _role(client)
    story = _story(client, role_profile_id=role)
    assert story["role_profile_ids"] == [role]
    [framing] = _roles(client, story["id"])
    assert framing["role_profile_id"] == role and framing["themes"] == [] and framing["emphasis"] is None


def test_the_same_story_can_be_positioned_for_several_roles(client) -> None:
    pm, analyst = _role(client, "Product Manager"), _role(client, "Business Analyst")
    story = _story(client, role_profile_id=pm, situation="Deliveries ran late")

    framed = _frame(client, story["id"], analyst, themes=["Requirements", " requirements "], emphasis="  The process mapping  ")
    assert framed.status_code == 200
    assert framed.json()["themes"] == ["Requirements"] and framed.json()["emphasis"] == "The process mapping"
    updated = _frame(client, story["id"], pm, themes=["Prioritisation"])
    assert updated.status_code == 200 and updated.json()["id"] == _roles(client, story["id"])[0]["id"]

    assert {item["role_profile_id"] for item in _roles(client, story["id"])} == {pm, analyst}
    assert len(client.get("/api/v1/stories", headers=A).json()) == 1  # still one story
    listed = client.get("/api/v1/stories", headers=A).json()[0]
    assert sorted(listed["role_profile_ids"]) == sorted([pm, analyst])
    assert client.get(f"/api/v1/stories/{story['id']}", headers=A).json()["situation"] == "Deliveries ran late"


def test_adding_the_same_role_twice_never_duplicates_it(client) -> None:
    role = _role(client)
    story = _story(client)
    first = _frame(client, story["id"], role, themes=["Roadmaps"]).json()
    second = _frame(client, story["id"], role, themes=["Roadmaps"]).json()
    assert first["id"] == second["id"] and len(_roles(client, story["id"])) == 1


def test_roles_with_the_same_name_stay_separate(client) -> None:
    first, second = _role(client, "Product Manager"), _role(client, "Product Manager")
    assert first != second
    story = _story(client)
    _frame(client, story["id"], first, themes=["Discovery"])
    assert [item["role_profile_id"] for item in _roles(client, story["id"])] == [first]
    assert client.delete(f"/api/v1/stories/{story['id']}/roles/{second}", headers=A).status_code == 404
    assert [item["role_profile_id"] for item in _roles(client, story["id"])] == [first]


def test_removing_a_role_keeps_the_story_its_history_and_other_roles(client) -> None:
    pm, analyst = _role(client, "Product Manager"), _role(client, "Business Analyst")
    story = _story(client, role_profile_id=pm, situation="v1")
    client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"situation": "v2"})
    _frame(client, story["id"], analyst)

    assert client.delete(f"/api/v1/stories/{story['id']}/roles/{pm}", headers=A).status_code == 204
    assert [item["role_profile_id"] for item in _roles(client, story["id"])] == [analyst]
    kept = client.get(f"/api/v1/stories/{story['id']}", headers=A).json()
    assert kept["archived_at"] is None and kept["situation"] == "v2" and kept["role_profile_ids"] == [analyst]
    assert kept["role_profile_id"] == pm  # where it was first written stays as provenance
    assert len(client.get(f"/api/v1/stories/{story['id']}/versions", headers=A).json()) == 2
    assert client.delete(f"/api/v1/stories/{story['id']}/roles/{pm}", headers=A).status_code == 404


def test_framing_input_is_validated(client) -> None:
    role = _role(client)
    story = _story(client)
    assert _frame(client, story["id"], role, themes=["t"] * 13).status_code == 422
    assert _frame(client, story["id"], role, emphasis="x" * 501).status_code == 422
    assert _frame(client, story["id"], role, situation="copied content").status_code == 422  # never a copy
    assert client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"role_profile_id": role}).status_code == 422


# ------------------------------------------------------------------ history and archive


def test_roles_and_story_versions_are_independent(client) -> None:
    pm, analyst = _role(client, "Product Manager"), _role(client, "Business Analyst")
    story = _story(client, role_profile_id=pm, situation="v1")
    _frame(client, story["id"], analyst, themes=["Requirements"])
    _frame(client, story["id"], analyst, themes=["Requirements", "Process"], emphasis="Mapping")
    client.delete(f"/api/v1/stories/{story['id']}/roles/{analyst}", headers=A)
    _frame(client, story["id"], analyst, themes=["Requirements"])
    assert client.get(f"/api/v1/stories/{story['id']}", headers=A).json()["current_version"] == 1
    assert len(client.get(f"/api/v1/stories/{story['id']}/versions", headers=A).json()) == 1

    before = _roles(client, story["id"])
    edited = client.patch(f"/api/v1/stories/{story['id']}", headers=A, json={"situation": "v2"}).json()
    assert edited["current_version"] == 2 and _roles(client, story["id"]) == before
    first = client.get(f"/api/v1/stories/{story['id']}/versions", headers=A).json()[-1]
    restored = client.post(f"/api/v1/stories/{story['id']}/versions/{first['id']}/restore", headers=A).json()
    assert restored["current_version"] == 3 and restored["situation"] == "v1"
    assert _roles(client, story["id"]) == before and sorted(restored["role_profile_ids"]) == sorted([pm, analyst])


def test_archiving_keeps_every_role_and_restoring_brings_them_back(client) -> None:
    pm, analyst = _role(client, "Product Manager"), _role(client, "Business Analyst")
    story = _story(client, role_profile_id=pm)
    _frame(client, story["id"], analyst, themes=["Requirements"])
    before = _roles(client, story["id"])

    archived = client.post(f"/api/v1/stories/{story['id']}/archive", headers=A).json()
    assert sorted(archived["role_profile_ids"]) == sorted([pm, analyst])
    assert _roles(client, story["id"]) == before
    assert _frame(client, story["id"], pm, themes=["x"]).status_code == 409
    assert client.delete(f"/api/v1/stories/{story['id']}/roles/{pm}", headers=A).status_code == 409
    archived_list = client.get("/api/v1/stories?archived=true", headers=A).json()
    assert sorted(archived_list[0]["role_profile_ids"]) == sorted([pm, analyst])

    restored = client.post(f"/api/v1/stories/{story['id']}/restore", headers=A).json()
    assert restored["id"] == story["id"] and _roles(client, story["id"]) == before


# ------------------------------------------------------------------ Dig Deeper


def test_dig_deeper_story_keeps_its_role_and_is_reused_for_another(client) -> None:
    pm, analyst = _role(client, "Product Manager"), _role(client, "Business Analyst")
    story = _story(client, role_profile_id=pm, origin="PRESSURE_TEST", source_text="Cut delivery delays by 30%", themes=["Operations"])
    assert [item["role_profile_id"] for item in _roles(client, story["id"])] == [pm]
    assert len(client.get(f"/api/v1/stories/{story['id']}/versions", headers=A).json()) == 1

    _frame(client, story["id"], analyst)
    stories = client.get("/api/v1/stories", headers=A).json()
    assert [item["id"] for item in stories] == [story["id"]]
    assert stories[0]["origin"] == "PRESSURE_TEST" and stories[0]["source_text"] == "Cut delivery delays by 30%"


# ------------------------------------------------------------------ ownership


def test_roles_on_a_story_belong_only_to_its_owner(client) -> None:
    mine, theirs = _role(client, headers=A), _role(client, headers=B)
    story = _story(client, role_profile_id=mine)
    their_story = _story(client, headers=B, title="Their story")

    # Reading, changing or removing someone else's roles.
    assert client.get(f"/api/v1/stories/{story['id']}/roles", headers=B).status_code == 404
    assert _frame(client, story["id"], mine, headers=B).status_code == 404
    assert _frame(client, story["id"], theirs, headers=B).status_code == 404
    assert client.delete(f"/api/v1/stories/{story['id']}/roles/{mine}", headers=B).status_code == 404
    # Mixing one person's story with another person's role, in either direction.
    assert _frame(client, story["id"], theirs, headers=A).status_code == 404
    assert _frame(client, their_story["id"], mine, headers=A).status_code == 404
    assert client.post("/api/v1/stories", headers=A, json={"title": "Borrowed role", "role_profile_id": theirs}).status_code == 404
    assert client.get(f"/api/v1/stories/{story['id']}/roles").status_code == 401

    assert [item["role_profile_id"] for item in _roles(client, story["id"])] == [mine]
    assert _roles(client, their_story["id"], headers=B) == []
