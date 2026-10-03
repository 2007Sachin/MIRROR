"""Interview events + debrief routes: owner-scoped, validated, cascade on delete."""

import pytest
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import get_interview_event_service, get_onboarding_repository, get_role_analysis_service
from app.interview_event_repository import MemoryInterviewEventRepository
from app.interview_event_service import InterviewEventService
from app.main import app
from app.readiness_service import ReadinessService
from app.story_repository import MemoryStoryRepository
from tests.test_role_agent import MemoryOnboarding, RoleVerifier, make_service

A = {"Authorization": "Bearer role-a"}
B = {"Authorization": "Bearer role-b"}
WHEN = "2026-10-01T09:00:00+05:30"


class NoDocuments:
    async def list_for_user(self, user_id):
        return []


@pytest.fixture
def client():
    roles, _, _ = make_service()
    stories = MemoryStoryRepository()
    events = MemoryInterviewEventRepository()
    readiness = ReadinessService(roles, NoDocuments(), None, stories, None, None)
    service = InterviewEventService(events, readiness, stories)
    overrides = {
        get_token_verifier: lambda: RoleVerifier(),
        get_role_analysis_service: lambda: roles,
        get_onboarding_repository: lambda: MemoryOnboarding(),
        get_interview_event_service: lambda: service,
    }
    app.dependency_overrides.update(overrides)
    with TestClient(app) as test_client:
        test_client.events = events
        yield test_client
    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


def make_role(client) -> str:
    return client.post("/api/v1/roles/analyze", headers=A, json={"target_role": "Data Analyst"}).json()["id"]


def make_event(client, role, **extra) -> dict:
    response = client.post(f"/api/v1/roles/{role}/interviews", headers=A, json={"scheduled_for": WHEN, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_crud(client) -> None:
    role = make_role(client)
    later = make_event(client, role, scheduled_for="2027-01-01T09:00:00Z", company_label="  Acme  ")
    sooner = make_event(client, role, round_kind="TECHNICAL")
    assert later["company_label"] == "Acme" and later["has_debrief"] is False and later["timing"] in ("UPCOMING", "SOON", "PAST")
    listed = client.get(f"/api/v1/roles/{role}/interviews", headers=A).json()
    assert [e["id"] for e in listed] == [sooner["id"], later["id"]]

    patched = client.patch(f"/api/v1/interviews/{later['id']}", headers=A, json={"company_label": None, "round_kind": "HR"})
    assert patched.status_code == 200 and patched.json()["company_label"] is None and patched.json()["round_kind"] == "HR"

    assert client.delete(f"/api/v1/interviews/{later['id']}", headers=A).status_code == 204
    assert len(client.get(f"/api/v1/roles/{role}/interviews", headers=A).json()) == 1


def test_unauthenticated_is_401(client) -> None:
    role = make_role(client)
    assert client.get(f"/api/v1/roles/{role}/interviews").status_code == 401
    assert client.post(f"/api/v1/roles/{role}/interviews", json={"scheduled_for": WHEN}).status_code == 401


def test_foreign_role_and_event_are_404(client) -> None:
    role = make_role(client)
    event = make_event(client, role)
    assert client.get(f"/api/v1/roles/{role}/interviews", headers=B).status_code == 404
    assert client.post(f"/api/v1/roles/{role}/interviews", headers=B, json={"scheduled_for": WHEN}).status_code == 404
    for method, path in (("patch", ""), ("delete", ""), ("get", "/brief"), ("get", "/debrief"), ("put", "/debrief")):
        kwargs = {"json": {}} if method in ("patch", "put") else {}
        response = getattr(client, method)(f"/api/v1/interviews/{event['id']}{path}", headers=B, **kwargs)
        assert response.status_code == 404, (method, path)
    assert client.get(f"/api/v1/interviews/{role}/brief", headers=A).status_code == 404


def test_validation_is_422(client) -> None:
    role = make_role(client)
    assert client.post(f"/api/v1/roles/{role}/interviews", headers=A, json={"scheduled_for": "2026-10-01T09:00:00"}).status_code == 422
    assert client.post(f"/api/v1/roles/{role}/interviews", headers=A, json={"scheduled_for": WHEN, "company_label": "x" * 121}).status_code == 422
    event = make_event(client, role)
    too_many = {"questions_asked": [f"Question {i}" for i in range(16)]}
    assert client.put(f"/api/v1/interviews/{event['id']}/debrief", headers=A, json=too_many).status_code == 422


def test_brief_is_readable_and_honest(client) -> None:
    event = make_event(client, make_role(client))
    brief = client.get(f"/api/v1/interviews/{event['id']}/brief", headers=A)
    assert brief.status_code == 200, brief.text
    body = brief.json()
    assert body["event"]["id"] == event["id"] and body["role_title"] == "Data Analyst"
    assert body["limitations"] and 3 <= len(body["questions_to_ask"]) <= 5 and len(body["themes"]) <= 3


def test_debrief_lifecycle_and_cascade(client) -> None:
    event = make_event(client, make_role(client))
    path = f"/api/v1/interviews/{event['id']}/debrief"
    assert client.get(path, headers=A).status_code == 404
    written = client.put(path, headers=A, json={"questions_asked": ["Tell me about SQL", " tell me about sql "], "feeling": "MIXED"})
    assert written.status_code == 200, written.text
    view = client.get(path, headers=A).json()
    assert view["debrief"]["questions_asked"] == ["Tell me about SQL"]
    assert view["debrief"]["outcome"] == "WAITING"
    assert [f["question"] for f in view["follow_ups"]] == ["Tell me about SQL"]
    assert client.get(f"/api/v1/roles/{event['role_profile_id']}/interviews", headers=A).json()[0]["has_debrief"] is True

    assert client.delete(f"/api/v1/interviews/{event['id']}", headers=A).status_code == 204
    assert client.events.debriefs == {}
    assert client.get(path, headers=A).status_code == 404


def test_create_is_capped_per_role(client, monkeypatch) -> None:
    from app import interview_event_service

    monkeypatch.setattr(interview_event_service, "MAX_INTERVIEWS_PER_ROLE", 1)
    role = make_role(client)
    make_event(client, role)
    response = client.post(f"/api/v1/roles/{role}/interviews", headers=A, json={"scheduled_for": WHEN})
    assert response.status_code == 409
