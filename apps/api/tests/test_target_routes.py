"""Loop 2 target routes: create/list/archive, pinned blueprint, round detail, round practice.

Fake auth (two users), memory target storage, a memory session engine and the real research
catalog (plus a synthetic India-scoped catalog for the researched path). No network.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.dependencies import (
    get_interview_state_machine,
    get_role_analysis_service,
    get_role_progress_service,
    get_story_repository,
)
from app.interview_engine import InterviewStateMachine
from app.repository import MemorySessionRepository
from app.research_catalog import CatalogDocument, RepoResearchCatalog, content_sha256, load_catalog
from app.role_service import RoleProfileNotFoundForUser
from app.routes_targets import (
    get_catalog_provider,
    get_target_capability,
    get_target_repository,
    router,
)
from app.target_capability import TargetAvailability
from app.target_repository import MemoryTargetRepository, TargetsUnavailable
from app.target_service import StaticCatalogProvider
from tests.test_role_agent import USER_A, USER_B, RoleVerifier

A = {"Authorization": "Bearer role-a"}
B = {"Authorization": "Bearer role-b"}
ROLE_A, ROLE_B = uuid4(), uuid4()


class FakeRoles:
    def __init__(self):
        self.owned = {ROLE_A: USER_A, ROLE_B: USER_B}

    async def get(self, profile_id, user_id):
        if self.owned.get(profile_id) != user_id:
            raise RoleProfileNotFoundForUser
        # The role's own seniority/JD says SDE II; a target must never pick that up.
        return SimpleNamespace(
            id=profile_id, user_id=user_id, target_role="Software Development Engineer", seniority="SENIOR",
            jd_text="Amazon SDE II, Bengaluru", competencies=[],
        )


class FakeStories:
    def __init__(self, titles=()):
        self.titles = titles

    async def list_for_user(self, user_id, *, archived=False):
        if user_id != USER_A:
            return []
        return [
            SimpleNamespace(title=title, archived_at=None, role_profile_id=None, created_at=datetime(2026, 1, i + 1, tzinfo=UTC))
            for i, title in enumerate(self.titles)
        ]


class FakeProgress:
    def __init__(self):
        self.calls = []

    async def target_detail(self, role_profile_id, user_id, session_ids):
        self.calls.append((role_profile_id, user_id, frozenset(session_ids)))
        return {"role_profile_id": str(role_profile_id), "practices": sorted(str(s) for s in session_ids)}


class FixedCapability:
    def __init__(self, state=TargetAvailability.AVAILABLE, error=False):
        self._state, self._error = state, error

    async def state(self):
        if self._error:
            raise TargetsUnavailable("down")
        return self._state


class SpyRepository(MemoryTargetRepository):
    """Records every write so refusal-before-side-effect can be checked."""

    def __init__(self):
        super().__init__()
        self.writes: list[str] = []
        self.question_history_cutoffs = []

    async def questions_for_target(self, *args, **kwargs):
        self.question_history_cutoffs.append(kwargs.get("since"))
        return await super().questions_for_target(*args, **kwargs)

    async def create_target(self, *args, **kwargs):
        self.writes.append("create_target")
        return await super().create_target(*args, **kwargs)

    async def archive_target(self, *args, **kwargs):
        self.writes.append("archive_target")
        return await super().archive_target(*args, **kwargs)

    async def create_blueprint(self, *args, **kwargs):
        self.writes.append("create_blueprint")
        return await super().create_blueprint(*args, **kwargs)

    async def record_questions(self, *args, **kwargs):
        self.writes.append("record_questions")
        return await super().record_questions(*args, **kwargs)

    async def create_link(self, *args, **kwargs):
        self.writes.append("create_link")
        return await super().create_link(*args, **kwargs)


def revised_global_catalog(version: int = 2) -> RepoResearchCatalog:
    """A catalog-content revision for pin tests; all official claims remain global."""
    raw = json.loads(load_catalog().document.model_dump_json(by_alias=True))
    raw["version"] = version
    raw["supersedes_version"] = version - 1 if version > 1 else None
    raw["claims"][0]["statement"] += " (catalog revision used only by tests)."
    document = CatalogDocument.model_validate(raw)
    return RepoResearchCatalog(document, content_sha256(json.dumps(raw, sort_keys=True).encode()))


@pytest.fixture
def world():
    repo = SpyRepository()
    sessions = MemorySessionRepository()
    engine = InterviewStateMachine(sessions, total_time_budget_seconds=1200, phase_time_budget_seconds=180)
    state = SimpleNamespace(
        repo=repo, sessions=sessions, engine=engine, capability=FixedCapability(),
        catalogs=StaticCatalogProvider({1: load_catalog()}), stories=FakeStories(), progress=FakeProgress(),
    )
    return state


def client(world) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_target_repository] = lambda: world.repo
    app.dependency_overrides[get_target_capability] = lambda: world.capability
    app.dependency_overrides[get_catalog_provider] = lambda: world.catalogs
    app.dependency_overrides[get_role_analysis_service] = lambda: FakeRoles()
    app.dependency_overrides[get_story_repository] = lambda: world.stories
    app.dependency_overrides[get_interview_state_machine] = lambda: world.engine
    app.dependency_overrides[get_role_progress_service] = lambda: world.progress
    return TestClient(app)


def create(c, headers=A, **over):
    body = {"role_profile_id": str(ROLE_A), "company": "Amazon", "geography": "in", "geography_label": "India"}
    body.update(over)
    return c.post("/api/v1/targets", headers=headers, json=body)


# ------------------------------------------------------------------ targets


def test_create_defaults_level_to_not_sure_and_never_reads_role_seniority(world) -> None:
    response = create(client(world))
    assert response.status_code == 201, response.text
    target = response.json()["target"]
    assert target["level_key"] == "not_sure"
    assert target["company_key"] == "amazon"
    assert target["role_family_key"] == "software_development_engineering"
    assert target["geography_key"] == "in"
    assert response.json()["blueprint"]["version"] == 1


def test_level_must_be_an_explicit_known_choice(world) -> None:
    c = client(world)
    assert create(c, level="SENIOR").status_code == 422
    assert create(c, level="sde 2").status_code == 422
    assert create(c, level="sde_ii").json()["target"]["level_key"] == "sde_ii"


def test_global_is_not_a_place_a_person_can_target(world) -> None:
    assert create(client(world), geography="global").status_code == 422


def test_unknown_company_is_kept_as_label_without_a_key(world) -> None:
    target = create(client(world), company="Some Startup").json()["target"]
    assert target["company_key"] is None and target["company_label"] == "Some Startup"


def test_duplicate_active_target_is_409_and_archive_allows_recreate(world) -> None:
    c = client(world)
    first = create(c).json()["target"]
    duplicate = create(c)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["target_id"] == first["id"]
    archived = c.post(f"/api/v1/targets/{first['id']}/archive", headers=A)
    assert archived.status_code == 200 and archived.json()["status"] == "ARCHIVED"
    assert archived.json()["level_key"] == first["level_key"]
    assert create(c).status_code == 201


def test_scope_cannot_be_edited(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    for method in ("put", "patch"):
        response = getattr(c, method)(f"/api/v1/targets/{target['id']}", headers=A, json={"level": "sde_ii"})
        assert response.status_code == 405


def test_list_returns_only_own_targets(world) -> None:
    c = client(world)
    create(c)
    create(c, headers=B, role_profile_id=str(ROLE_B))
    body = c.get("/api/v1/targets", headers=A).json()
    assert body["availability"] == "AVAILABLE"
    assert len(body["targets"]) == 1
    assert body["targets"][0]["role_profile_id"] == str(ROLE_A)


def test_create_with_someone_elses_role_is_404_and_writes_nothing(world) -> None:
    response = create(client(world), role_profile_id=str(ROLE_B))
    assert response.status_code == 404
    assert world.repo.writes == []


CROSS_USER_ROUTES = [
    ("get", "/api/v1/targets/{id}"),
    ("post", "/api/v1/targets/{id}/archive"),
    ("get", "/api/v1/targets/{id}/blueprint"),
    ("post", "/api/v1/targets/{id}/blueprint/refresh"),
    ("get", "/api/v1/targets/{id}/rounds/behavioural"),
    ("get", "/api/v1/targets/{id}/progress"),
]


@pytest.mark.parametrize(("method", "path"), CROSS_USER_ROUTES)
def test_someone_elses_target_is_404(world, method, path) -> None:
    c = client(world)
    target = create(c).json()["target"]
    response = getattr(c, method)(path.format(id=target["id"]), headers=B)
    assert response.status_code == 404
    assert target["id"] not in response.text


def test_someone_elses_target_cannot_start_practice(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    before = list(world.repo.writes)
    response = c.post(
        f"/api/v1/targets/{target['id']}/rounds/behavioural/practice", headers=B,
        json={"mode": "FOCUSED_PRACTICE", "idempotency_key": str(uuid4())},
    )
    assert response.status_code == 404
    assert world.repo.writes == before
    assert world.sessions.sessions == {}


# ------------------------------------------------------------------ owner rule: India never shows global guidance


GLOBAL_CLAIM_MARKERS = ("amazon.sde.sde_ii.", "amazon.all.", "amazon.sde.all.interview_topics", "amazon.jobs/content")


@pytest.mark.parametrize("level", ["not_sure", "sde_i", "sde_ii", "sde_iii", "university"])
def test_india_target_is_not_yet_researched_with_no_global_guidance(world, level) -> None:
    c = client(world)
    target = create(c, level=level).json()["target"]
    blueprint = c.get(f"/api/v1/targets/{target['id']}/blueprint", headers=A).json()
    assert blueprint["match_state"] == "NOT_RESEARCHED"
    assert blueprint["research_label_key"] == "research.not_yet_researched"
    assert blueprint["claims"] == [] and blueprint["conflicts"] == []
    assert "amazon.sde.india_specific_process" in [u["key"] for u in blueprint["unknowns"]]
    assert all(r["basis"] == "MIRROR_SUGGESTED" for r in blueprint["rounds"])
    for round_key in ("coding_reasoning", "system_design", "behavioural"):
        detail = c.get(f"/api/v1/targets/{target['id']}/rounds/{round_key}", headers=A)
        assert detail.status_code == 200
        body = detail.json()
        assert body["claims"] == [] and body["conflicts"] == []
        assert {p["rationale_code"] for p in body["pack"]["prompts"]} <= {"MIRROR_SUGGESTED", "YOUR_STORY"}
        assert not any(code.startswith("IN_") for p in body["priorities"] for code in p["reason_codes"])
        text = detail.text + json.dumps(blueprint)
        assert not any(marker in text for marker in GLOBAL_CLAIM_MARKERS)


def test_target_without_location_is_not_researched(world) -> None:
    c = client(world)
    target = create(c, geography=None, geography_label=None).json()["target"]
    blueprint = c.get(f"/api/v1/targets/{target['id']}/blueprint", headers=A).json()
    assert blueprint["match_state"] == "NOT_RESEARCHED" and blueprint["claims"] == []


# ------------------------------------------------------------------ researched path (synthetic India catalog)


def test_global_amazon_guidance_is_not_rendered_for_an_india_target(world) -> None:
    c = client(world)
    target = create(c, level="sde_ii").json()["target"]
    blueprint = c.get(f"/api/v1/targets/{target['id']}/blueprint", headers=A).json()
    assert blueprint["match_state"] == "NOT_RESEARCHED"
    assert blueprint["claims"] == [] and blueprint["conflicts"] == []
    assert {unknown["key"] for unknown in blueprint["unknowns"]} == {"amazon.sde.india_specific_process"}
    assert all(round_["basis"] == "MIRROR_SUGGESTED" for round_ in blueprint["rounds"])
    detail = c.get(f"/api/v1/targets/{target['id']}/rounds/coding_reasoning", headers=A).json()
    assert detail["claims"] == [] and detail["conflicts"] == []
    assert detail["round"]["basis"] == "MIRROR_SUGGESTED"


def test_round_detail_has_explicit_unknowns_priorities_and_a_full_pack(world) -> None:
    world.stories = FakeStories(("Moving billing to a new queue",))
    c = client(world)
    target = create(c).json()["target"]
    body = c.get(f"/api/v1/targets/{target['id']}/rounds/behavioural", headers=A).json()
    assert body["unknowns"]
    assert 1 <= len(body["priorities"]) <= 3
    assert [p["rank"] for p in body["priorities"]] == list(range(1, len(body["priorities"]) + 1))
    assert "points" not in json.dumps(body["priorities"])
    assert body["pack"]["state"] == "FULL"
    assert len(body["pack"]["prompts"]) >= 4
    assert body["pack"]["label_key"] == "prompts.written_by_mirror"
    assert all(p["provenance_class"] == "MIRROR_GENERATED" for p in body["pack"]["prompts"])
    assert all("text" not in p for p in body["pack"]["prompts"])
    assert all(p["competency_key"] for p in body["pack"]["prompts"])
    assert "Moving billing to a new queue" not in json.dumps(body)


def test_unknown_round_is_404(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    assert c.get(f"/api/v1/targets/{target['id']}/rounds/bar_raiser", headers=A).status_code == 404


# ------------------------------------------------------------------ blueprint pin and refresh


def test_refresh_appends_a_new_pin_and_old_content_is_still_served(world) -> None:
    v1 = load_catalog()
    world.catalogs = StaticCatalogProvider({1: v1})
    c = client(world)
    target = create(c, level="sde_ii").json()["target"]
    first = c.get(f"/api/v1/targets/{target['id']}/blueprint", headers=A).json()
    assert first["blueprint"]["catalog_version"] == 1
    assert first["blueprint"]["catalog_sha256"] == v1.content_sha256
    assert first["blueprint"]["refresh_available"] is False
    same = c.post(f"/api/v1/targets/{target['id']}/blueprint/refresh", headers=A)
    assert same.status_code == 200 and same.json()["blueprint"]["version"] == 1

    world.catalogs = StaticCatalogProvider({1: v1, 2: revised_global_catalog(2)})
    c = client(world)
    assert c.get(f"/api/v1/targets/{target['id']}/blueprint", headers=A).json()["blueprint"]["refresh_available"] is True
    refreshed = c.post(f"/api/v1/targets/{target['id']}/blueprint/refresh", headers=A)
    assert refreshed.status_code == 201
    assert refreshed.json()["blueprint"]["version"] == 2
    assert refreshed.json()["blueprint"]["catalog_version"] == 2
    assert refreshed.json()["match_state"] == "NOT_RESEARCHED"
    old = c.get(f"/api/v1/targets/{target['id']}/blueprint?version=1", headers=A).json()
    assert old["blueprint"]["catalog_version"] == 1 and old["match_state"] == "NOT_RESEARCHED"
    assert old["content_state"] == "SERVED"
    assert [b.version for b in world.repo.blueprint_rows] == [1, 2]
    assert c.get(f"/api/v1/targets/{target['id']}/blueprint?version=9", headers=A).status_code == 404


def test_pin_hash_mismatch_serves_nothing(world) -> None:
    c = client(world)
    target = create(c, level="sde_ii").json()["target"]
    world.catalogs = StaticCatalogProvider({1: revised_global_catalog(1)})  # same version, different global content
    body = client(world).get(f"/api/v1/targets/{target['id']}/blueprint", headers=A).json()
    assert body["content_state"] == "PIN_MISMATCH"
    assert body["claims"] == [] and body["conflicts"] == [] and body["unknowns"] == []


def test_archived_target_reads_but_cannot_refresh_or_practise(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    c.post(f"/api/v1/targets/{target['id']}/archive", headers=A)
    assert c.get(f"/api/v1/targets/{target['id']}/blueprint", headers=A).status_code == 200
    assert c.post(f"/api/v1/targets/{target['id']}/blueprint/refresh", headers=A).status_code == 409
    response = c.post(
        f"/api/v1/targets/{target['id']}/rounds/behavioural/practice", headers=A,
        json={"mode": "QUICK_DRILL", "idempotency_key": str(uuid4())},
    )
    assert response.status_code == 409
    assert world.sessions.sessions == {}


# ------------------------------------------------------------------ round practice


def start(c, target_id, round_key="behavioural", mode="FOCUSED_PRACTICE", key=None, headers=A):
    return c.post(
        f"/api/v1/targets/{target_id}/rounds/{round_key}/practice", headers=headers,
        json={"mode": mode, "idempotency_key": str(key or uuid4())},
    )


def test_round_practice_creates_a_role_session_stored_prompts_and_a_link(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    response = start(c, target["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    session = world.sessions.sessions[UUID(body["session"]["id"])]
    assert session.role_profile_id == ROLE_A
    assert (session.practice_mode, session.practice_focus) == ("FOCUSED_PRACTICE", "role")
    assert body["link"]["candidate_target_id"] == target["id"]
    assert body["link"]["round_key"] == "behavioural"
    assert len(body["prompts"]) == 4
    assert all(set(p) == {"position", "rationale_code"} for p in body["prompts"])  # no text before the interview
    stored = world.repo.questions
    assert len(stored) == 4 and {q.prompt_set_id for q in stored} == {UUID(body["link"]["prompt_set_id"])}
    linked = c.get(f"/api/v1/sessions/{session.id}/target", headers=A).json()
    assert linked["link"]["round_key"] == "behavioural"


def test_quick_drill_uses_three_prompts(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    assert len(start(c, target["id"], mode="QUICK_DRILL").json()["prompts"]) == 3


def test_prompt_insert_conflict_re_reads_winner_set_and_links_once(world) -> None:
    from app.target_repository import TargetConflict

    c = client(world)
    target = create(c).json()["target"]
    original = world.repo.record_questions
    raised = False

    async def conflict_after_commit(user_id, rows):
        nonlocal raised
        stored = await original(user_id, rows)
        if not raised:
            raised = True
            raise TargetConflict()
        return stored

    world.repo.record_questions = conflict_after_commit
    response = start(c, target["id"], round_key="system_design")
    assert response.status_code == 201, response.text
    assert len(world.repo.links) == 1
    assert len(world.repo.questions) == 4


def test_replay_with_same_key_returns_same_session_and_single_link(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    key = uuid4()
    first = start(c, target["id"], key=key).json()
    second = start(c, target["id"], key=key)
    assert second.status_code == 201
    assert second.json()["session"]["id"] == first["session"]["id"]
    assert len(world.repo.links) == 1 and len(world.repo.questions) == 4


def test_same_key_for_another_round_cannot_rewrite_the_link(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    key = uuid4()
    first = start(c, target["id"], key=key).json()
    response = start(c, target["id"], round_key="system_design", key=key)
    assert response.status_code == 409
    assert world.repo.links[UUID(first["session"]["id"])].round_key == "behavioural"


def test_reused_key_for_mismatched_existing_session_returns_409_without_prompts(world) -> None:
    import asyncio
    from app.schemas import SessionCreate

    c = client(world)
    target = create(c).json()["target"]
    key = uuid4()
    existing = asyncio.run(world.engine.create_session_state(USER_A, SessionCreate(
        target_role="Software Development Engineer", role_profile_id=ROLE_A,
        practice_mode="QUICK_DRILL", practice_focus="story", practice_theme=None, idempotency_key=key,
    )))
    response = start(c, target["id"], key=key)
    assert response.status_code == 409
    assert existing.id not in world.repo.links
    assert world.repo.questions == []


def test_archiving_after_practice_never_changes_the_link(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    session_id = start(c, target["id"]).json()["session"]["id"]
    c.post(f"/api/v1/targets/{target['id']}/archive", headers=A)
    create(c, level="sde_ii")
    link = c.get(f"/api/v1/sessions/{session_id}/target", headers=A).json()["link"]
    assert link["candidate_target_id"] == target["id"] and link["round_key"] == "behavioural"


@pytest.mark.parametrize("round_key", ["coding_reasoning", "system_design", "behavioural"])
def test_three_consecutive_focused_starts_remain_available(world, round_key) -> None:
    c = client(world)
    target = create(c).json()["target"]
    responses = [start(c, target["id"], round_key=round_key) for _ in range(3)]
    assert [r.status_code for r in responses] == [201, 201, 201]


def test_repeat_history_query_is_cut_to_the_guard_window(world) -> None:
    from datetime import timedelta

    c = client(world)
    target = create(c).json()["target"]
    response = c.get(f"/api/v1/targets/{target['id']}/rounds/system_design", headers=A)
    assert response.status_code == 200
    assert world.repo.question_history_cutoffs
    cutoff = world.repo.question_history_cutoffs[-1]
    assert cutoff is not None
    assert cutoff.tzinfo is not None
    age = datetime.now(UTC) - cutoff
    assert timedelta(days=29) <= age <= timedelta(days=31)


def test_orphan_prompt_set_does_not_consume_repeat_window(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    first = start(c, target["id"], round_key="system_design")
    assert first.status_code == 201
    linked = {link.prompt_set_id for link in world.repo.links.values()}
    source = list(world.repo.questions)
    orphan = [q.model_copy(update={"prompt_set_id": uuid4(), "novelty_sha256": "0" * 64}) for q in source]
    assert not ({q.prompt_set_id for q in orphan} & linked)
    world.repo.questions.extend(orphan)
    second = start(c, target["id"], round_key="system_design")
    assert second.status_code == 201, second.text
    assert len(world.repo.links) == 2


def test_short_pack_refuses_before_any_session(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    assert start(c, target["id"], round_key="system_design").status_code == 201
    assert start(c, target["id"], round_key="system_design").status_code == 201
    assert start(c, target["id"], round_key="system_design").status_code == 201
    before = len(world.sessions.sessions)
    response = start(c, target["id"], round_key="system_design")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SHORT_PACK"
    assert len(world.sessions.sessions) == before
    detail = c.get(f"/api/v1/targets/{target['id']}/rounds/system_design", headers=A).json()
    assert detail["pack"]["state"] == "SHORT_PACK"
    assert detail["practice"]["count"] == 3


def test_prompts_return_once_they_are_outside_the_repeat_window(world) -> None:
    from datetime import timedelta

    c = client(world)
    target = create(c).json()["target"]
    first = start(c, target["id"], round_key="system_design")
    assert first.status_code == 201
    old = datetime.now(UTC) - timedelta(days=31)
    world.repo.questions = [q.model_copy(update={"created_at": old}) for q in world.repo.questions]
    second = start(c, target["id"], round_key="system_design")
    assert second.status_code == 201, second.text
    sets = {}
    for q in world.repo.questions:
        sets.setdefault(q.prompt_set_id, []).append(q.novelty_sha256)
    assert len(sets) == 2
    assert all(len(hashes) == len(set(hashes)) for hashes in sets.values())  # never repeated within a set
    assert set.intersection(*(set(h) for h in sets.values()))  # earlier prompts came back after 30 days


def test_session_target_of_someone_elses_session_is_404(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    session_id = start(c, target["id"]).json()["session"]["id"]
    assert c.get(f"/api/v1/sessions/{session_id}/target", headers=B).status_code == 404


def test_session_without_target_has_null_link(world) -> None:
    from app.schemas import SessionCreate
    import asyncio

    session = asyncio.run(world.engine.create_session_state(USER_A, SessionCreate(target_role="Data Analyst")))
    body = client(world).get(f"/api/v1/sessions/{session.id}/target", headers=A).json()
    assert body == {"availability": "AVAILABLE", "link": None}


# ------------------------------------------------------------------ schema state


@pytest.mark.parametrize("state", [TargetAvailability.UNAVAILABLE, TargetAvailability.DISABLED])
def test_reads_return_empty_state_when_targets_are_not_available(world, state) -> None:
    world.capability = FixedCapability(state)
    c = client(world)
    body = c.get("/api/v1/targets", headers=A).json()
    assert body == {"availability": state.value, "targets": []}
    some_id = uuid4()
    assert c.get(f"/api/v1/targets/{some_id}/blueprint", headers=A).json()["availability"] == state.value
    assert c.get(f"/api/v1/targets/{some_id}/rounds/behavioural", headers=A).json()["round"] is None
    assert c.get(f"/api/v1/sessions/{some_id}/target", headers=A).json() == {"availability": state.value, "link": None}


@pytest.mark.parametrize("state", [TargetAvailability.UNAVAILABLE, TargetAvailability.DISABLED])
def test_writes_are_refused_before_any_side_effect(world, state) -> None:
    c = client(world)
    target = create(c).json()["target"]
    world.repo.writes.clear()
    world.capability = FixedCapability(state)
    c = client(world)
    responses = [
        create(c, level="sde_ii"),
        c.post(f"/api/v1/targets/{target['id']}/archive", headers=A),
        c.post(f"/api/v1/targets/{target['id']}/blueprint/refresh", headers=A),
        start(c, target["id"]),
    ]
    for response in responses:
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "TARGETS_NOT_AVAILABLE"
    assert world.repo.writes == []
    assert world.sessions.sessions == {}


def test_unauthenticated_writes_return_401_without_availability_probe(world) -> None:
    class CountingCapability:
        def __init__(self, state):
            self.state_value = state
            self.calls = 0

        async def state(self):
            self.calls += 1
            return self.state_value

    c = client(world)
    target = create(c).json()["target"]
    for state in (TargetAvailability.DISABLED, TargetAvailability.AVAILABLE):
        capability = CountingCapability(state)
        world.capability = capability
        c = client(world)
        responses = [
            c.post("/api/v1/targets", json={"role_profile_id": str(ROLE_A), "company": "Amazon"}),
            c.post(f"/api/v1/targets/{target['id']}/archive"),
            c.post(f"/api/v1/targets/{target['id']}/blueprint/refresh"),
            c.post(f"/api/v1/targets/{target['id']}/rounds/behavioural/practice", json={"mode": "FOCUSED_PRACTICE", "idempotency_key": str(uuid4())}),
        ]
        assert [response.status_code for response in responses] == [401] * 4
        assert capability.calls == 0


def test_transient_probe_error_is_503_not_empty(world) -> None:
    world.capability = FixedCapability(error=True)
    assert client(world).get("/api/v1/targets", headers=A).status_code == 503


def test_unauthenticated_is_401(world) -> None:
    assert client(world).get("/api/v1/targets").status_code == 401


# ------------------------------------------------------------------ wiring


def test_main_app_serves_targets_and_flag_is_off_by_default() -> None:
    from app.main import app

    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    try:
        c = TestClient(app)
        assert c.get("/api/v1/targets", headers=A).json() == {"availability": "DISABLED", "targets": []}
        response = c.post("/api/v1/targets", headers=A, json={"role_profile_id": str(ROLE_A), "company": "Amazon", "geography": "in"})
        assert response.status_code == 503 and response.json()["detail"]["code"] == "TARGETS_NOT_AVAILABLE"
    finally:
        app.dependency_overrides.pop(get_token_verifier, None)


# ------------------------------------------------------------------ progress and planner hand-off


def test_target_progress_is_built_from_linked_sessions_only(world) -> None:
    c = client(world)
    target = create(c).json()["target"]
    session_id = start(c, target["id"]).json()["session"]["id"]
    body = c.get(f"/api/v1/targets/{target['id']}/progress", headers=A).json()
    assert body["availability"] == "AVAILABLE"
    assert world.progress.calls == [(ROLE_A, USER_A, frozenset({UUID(session_id)}))]


def test_planner_loader_returns_stored_prompts_only_for_the_owner_when_available(world) -> None:
    import asyncio

    from app.target_service import linked_prompt_texts

    c = client(world)
    target = create(c).json()["target"]
    session_id = UUID(start(c, target["id"]).json()["session"]["id"])
    stored = [q.question_text for q in sorted(world.repo.questions, key=lambda q: q.position)]
    assert asyncio.run(linked_prompt_texts(world.repo, world.capability, session_id, USER_A)) == stored
    assert asyncio.run(linked_prompt_texts(world.repo, world.capability, session_id, USER_B)) == []
    for state in (TargetAvailability.UNAVAILABLE, TargetAvailability.DISABLED):
        assert asyncio.run(linked_prompt_texts(world.repo, FixedCapability(state), session_id, USER_A)) == []
    from app.planner_repository import InterviewPlanningUnavailable

    try:
        asyncio.run(linked_prompt_texts(world.repo, FixedCapability(error=True), session_id, USER_A))
    except InterviewPlanningUnavailable:
        pass
    else:
        raise AssertionError("a failed capability probe must fail planning visibly")


def test_available_planner_link_read_error_fails_visibly(world) -> None:
    import asyncio

    from app.planner_repository import InterviewPlanningUnavailable
    from app.target_service import linked_prompt_texts

    c = client(world)
    target = create(c).json()["target"]
    session_id = UUID(start(c, target["id"]).json()["session"]["id"])
    original = world.repo.link_for_session

    async def fail_link_read(session, user):
        raise RuntimeError("temporary repository failure")

    world.repo.link_for_session = fail_link_read
    try:
        try:
            asyncio.run(linked_prompt_texts(world.repo, world.capability, session_id, USER_A))
        except InterviewPlanningUnavailable:
            pass
        else:
            raise AssertionError("available linked-prompt read errors must fail planning visibly")
    finally:
        world.repo.link_for_session = original
