import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.repository import SESSION_READ_COLUMNS, SupabaseSessionRepository
from app.schemas import SessionCreate


def session_row(user_id, idempotency_key, session_id=None):
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(session_id or uuid4()),
        "user_id": str(user_id),
        "target_role": "Engineer",
        "role_profile_id": None,
        "resume_url": None,
        "jd_text": "",
        "status": "CREATED",
        "phase": "INTRO",
        "question_plan": None,
        "completion_pct": 0,
        "synthetic": False,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
        "phase_started_at": now,
        "phase_time_budget_seconds": 180,
        "total_time_budget_seconds": 1200,
        "elapsed_seconds": 0,
        "current_primary_question_id": None,
        "current_probe_count": 0,
        "total_questions": 0,
        "recovery_count": 0,
        "practice_mode": "FULL_INTERVIEW",
        "practice_focus": None,
        "practice_theme": None,
    }


class Response:
    def __init__(self, status, rows=None):
        self.status_code = status
        self._rows = rows or []

    def json(self):
        return self._rows

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("conflict", request=httpx.Request("POST", "https://test"), response=httpx.Response(self.status_code))


@pytest.mark.asyncio
async def test_concurrent_idempotent_create_returns_conflict_winner_without_duplicate_event(monkeypatch):
    user_id, key, winner_id = uuid4(), uuid4(), uuid4()
    winner = session_row(user_id, key, winner_id)
    gets = 0
    posts = 0
    events = []

    class Client:
        async def get(self, url, **kwargs):
            nonlocal gets
            gets += 1
            # Both callers miss before either insert completes; subsequent lookup sees winner.
            return Response(200, [] if gets <= 2 else [winner])

        async def post(self, url, **kwargs):
            nonlocal posts
            if url.endswith("/sessions"):
                posts += 1
                if posts == 1:
                    return Response(201, [winner])
                return Response(409)
            events.append(kwargs["json"])
            return Response(201, [{"id": str(uuid4()), **kwargs["json"], "created_at": datetime.now(UTC).isoformat()}])

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class Pool:
        async def __aenter__(self):
            return Client()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("app.repository.pooled", lambda _: Pool())
    repository = SupabaseSessionRepository(type("Settings", (), {
        "next_public_supabase_url": "https://test", "supabase_service_role_key": "x"
    })())
    payload = SessionCreate(target_role="Engineer", idempotency_key=key)

    results = await asyncio.gather(
        repository.create(user_id, payload), repository.create(user_id, payload),
        return_exceptions=True,
    )

    assert all(not isinstance(result, Exception) for result in results), results
    assert {result.id for result in results} == {winner_id}
    assert len(events) == 1
    assert events[0]["event_type"] == "SESSION_CREATED"
