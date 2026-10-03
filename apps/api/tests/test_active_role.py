"""The active role: stored per person, owner-verified, with a fixed fallback order, and never a session."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import get_role_analysis_service
from app.home_service import HomeService
from app.routes_active_role import get_role_preference_store, router
from tests.test_home_service import FakeDashboard, FakeReadiness, FakeRoles, FakeStories, NOW
from tests.test_role_agent import USER_A, USER_B, RoleVerifier
from tests.test_role_progress import FakeReports, profile, session

A = {"Authorization": "Bearer role-a"}
B = {"Authorization": "Bearer role-b"}


class MemoryPreferences:
    def __init__(self, current=None, onboarding=None):
        self.current, self.onboarding, self.writes = current, onboarding, []

    async def role_preference(self, user_id):
        return (self.current, self.onboarding) if user_id == USER_A else (None, None)

    async def set_current_role(self, user_id, role_profile_id):
        self.writes.append((user_id, role_profile_id))
        self.current = role_profile_id


@pytest.fixture
def roles():
    analyst_old = profile(USER_A, "Data Analyst")
    analyst = profile(USER_A, "Data Analyst")  # newest profile of the same role
    manager = profile(USER_A, "Product Manager")
    theirs = profile(USER_B, "Designer")
    families = {
        USER_A: [(analyst, frozenset({analyst.id, analyst_old.id})), (manager, frozenset({manager.id}))],
        USER_B: [(theirs, frozenset({theirs.id}))],
    }
    return FakeRoles(families), analyst_old, analyst, manager, theirs


def client_for(fake_roles, preferences):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_role_analysis_service] = lambda: fake_roles
    app.dependency_overrides[get_role_preference_store] = lambda: preferences
    return TestClient(app)


def test_get_lists_each_role_once_and_the_stored_role(roles) -> None:
    fake, _, analyst, manager, _ = roles
    body = client_for(fake, MemoryPreferences(current=manager.id)).get("/api/v1/active-role", headers=A).json()
    assert body["role"] == {"role_profile_id": str(manager.id), "target_role": "Product Manager"}
    assert [item["role_profile_id"] for item in body["roles"]] == [str(analyst.id), str(manager.id)]


def test_fallback_order_is_stored_then_onboarding_then_newest(roles) -> None:
    fake, analyst_old, analyst, manager, theirs = roles
    get = lambda prefs: client_for(fake, prefs).get("/api/v1/active-role", headers=A).json()["role"]["role_profile_id"]  # noqa: E731
    # An older profile of a role counts, reported as the role's newest profile.
    assert get(MemoryPreferences(current=analyst_old.id, onboarding=manager.id)) == str(analyst.id)
    # A stored id that is not one of this person's roles falls through to onboarding.
    assert get(MemoryPreferences(current=theirs.id, onboarding=manager.id)) == str(manager.id)
    assert get(MemoryPreferences(current=None, onboarding=manager.id)) == str(manager.id)
    assert get(MemoryPreferences()) == str(analyst.id)


def test_no_roles_means_no_active_role(roles) -> None:
    fake = FakeRoles({})
    body = client_for(fake, MemoryPreferences()).get("/api/v1/active-role", headers=A).json()
    assert body == {"role": None, "roles": []}


def test_put_stores_the_roles_newest_profile(roles) -> None:
    fake, analyst_old, analyst, _, _ = roles
    preferences = MemoryPreferences()
    response = client_for(fake, preferences).put("/api/v1/active-role", headers=A, json={"role_profile_id": str(analyst_old.id)})
    assert response.status_code == 200
    assert response.json()["role"]["role_profile_id"] == str(analyst.id)
    assert preferences.writes == [(USER_A, analyst.id)]


def test_a_foreign_or_unknown_role_is_not_found_and_nothing_is_stored(roles) -> None:
    fake, _, _, _, theirs = roles
    preferences = MemoryPreferences()
    client = client_for(fake, preferences)
    assert client.put("/api/v1/active-role", headers=A, json={"role_profile_id": str(theirs.id)}).status_code == 404
    assert client.put("/api/v1/active-role", headers=A, json={"role_profile_id": "00000000-0000-4000-8000-000000000000"}).status_code == 404
    assert client.put("/api/v1/active-role", headers=A, json={"role_profile_id": "not-a-uuid"}).status_code == 422
    assert client.put("/api/v1/active-role", json={"role_profile_id": str(theirs.id)}).status_code == 401
    assert preferences.writes == []


def test_switching_never_creates_a_session(roles) -> None:
    fake, _, _, manager, _ = roles
    paths = {route.path for route in router.routes}
    assert paths == {"/api/v1/active-role"}  # the only thing these routes touch
    put = next(route for route in router.routes if "PUT" in route.methods)
    names = {dependency.call.__name__ for dependency in put.dependant.dependencies}
    assert not any("session" in name or "state_machine" in name for name in names)
    response = client_for(fake, MemoryPreferences()).put("/api/v1/active-role", headers=A, json={"role_profile_id": str(manager.id)})
    assert response.status_code == 200 and "session_id" not in response.text


@pytest.mark.asyncio
async def test_home_defaults_to_the_active_role_and_an_explicit_role_still_wins(roles) -> None:
    from app.role_progress import RoleProgressService

    fake, _, analyst, manager, _ = roles
    sessions = [session(analyst.id, days_ago=1)]  # the newest practice is for the analyst role
    dashboard = FakeDashboard({USER_A: sessions})
    progress = RoleProgressService(fake, dashboard, FakeReports({}), None, None)
    preferences = MemoryPreferences(current=manager.id)
    service = HomeService(fake, dashboard, progress, FakeReadiness(), FakeStories([]), active_role=preferences.role_preference)

    assert (await service.home(USER_A, now=NOW)).selected.role_profile_id == manager.id
    assert (await service.home(USER_A, analyst.id, now=NOW)).selected.role_profile_id == analyst.id
    # Without a stored role, Home chooses as before: the newest practice's role.
    plain = HomeService(fake, dashboard, progress, FakeReadiness(), FakeStories([]))
    assert (await plain.home(USER_A, now=NOW)).selected.role_profile_id == analyst.id
