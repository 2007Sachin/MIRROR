"""My plan: role needs in priority order, statuses from approved experience only, the person's choice wins."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_token_verifier
from app.career_evidence import EvidenceItem
from app.dependencies import get_readiness_service, get_role_analysis_service, get_story_repository
from app.interview_map import (
    Coverage,
    CoverageReason,
    ExperienceState,
    InterviewMap,
    InterviewTheme,
    MapState,
    StoryEvidence,
    slug,
)
from app.plan_service import (
    CoverageLink,
    LinkChoice,
    MemoryCoverageLinkRepository,
    PlanState,
    PlanStatus,
    build_plan,
    sentence_case,
)
from app.role_models import CompetencyCategory
from app.role_service import RoleProfileNotFoundForUser
from app.routes_active_role import get_role_preference_store
from app.routes_plan import get_coverage_link_repository, router
from app.story_models import STORY_PARTS
from tests.test_active_role import MemoryPreferences
from tests.test_home_service import FakeRoles
from tests.test_role_agent import USER_A, USER_B, RoleVerifier
from tests.test_role_progress import profile

A = {"Authorization": "Bearer role-a"}
B = {"Authorization": "Bearer role-b"}
NOW = datetime(2026, 10, 1, tzinfo=UTC)
NEEDS = ["SQL", "Stakeholder Management", "Data Visualisation", "Forecasting", "Experimentation", "Python"]


def item(title, *, user=USER_A, status="APPROVED", kind="ACHIEVEMENT", tools=(), outcome=None, metric=None):
    return EvidenceItem(
        id=uuid4(), user_id=user, source_key=str(uuid4()), kind=kind, title=title, tools=list(tools),
        outcome=outcome, metric=metric, status=status, updated_at=NOW,
    )


def the_map(role_id, *, needs=NEEDS, state=MapState.READY, experience=ExperienceState.READY):
    themes = [
        InterviewTheme(
            key=slug(name), name=name, category=CompetencyCategory.TECHNICAL, from_job_description=index == 0,
            source_text="Strong SQL for weekly reporting" if index == 0 else None, coverage=Coverage.MISSING,
        )
        for index, name in enumerate(needs)
    ]
    return InterviewMap(
        role_profile_id=role_id, target_role="Data Analyst", state=state, experience_state=experience, themes=themes,
    )


def link(role_id, key, *, evidence=None, story=None, confirmed=True):
    return CoverageLink(
        id=uuid4(), user_id=USER_A, role_profile_id=role_id, requirement_key=key,
        evidence_item_id=evidence, story_id=story, reason=CoverageReason.CONFIRMED if confirmed else None,
        confirmed=confirmed, dismissed=not confirmed,
    )


ROLE = uuid4()


def area(plan, key):
    return next(area for area in plan.areas if area.key == key)


# ------------------------------------------------------------------ the builder


def test_areas_follow_role_priority_and_stop_at_five() -> None:
    plan = build_plan(the_map(ROLE), [], [], [])
    assert plan.state == PlanState.READY
    assert [area.theme for area in plan.areas] == NEEDS[:5]
    first = plan.areas[0]
    assert first.title == "SQL" and first.from_job_description and first.why == "Strong SQL for weekly reporting"
    assert plan.areas[1].title == "Stakeholder management" and plan.areas[1].why is None
    assert all(area.status == PlanStatus.BUILD for area in plan.areas)
    assert plan.recommended_area_key == "sql"


def test_status_comes_from_approved_items_only() -> None:
    pending = item("You wrote SQL queries for the weekly report", tools=["SQL"], status="PENDING")
    removed = item("You built SQL dashboards", tools=["SQL"], status="REMOVED")
    plan = build_plan(the_map(ROLE), [pending, removed], [], [])
    assert area(plan, "sql").status == PlanStatus.BUILD and area(plan, "sql").have == []

    approved = item("You wrote SQL queries for the weekly report", tools=["SQL"])
    sql = area(build_plan(the_map(ROLE), [approved], [], []), "sql")
    assert sql.status == PlanStatus.GOOD
    assert sql.have[0].evidence_item_id == approved.id and sql.have[0].reason == CoverageReason.TOOL
    assert "by how much" in sql.strengthen  # no measured result yet
    assert sql.primary_action == "PRACTICE"


def test_a_partial_word_overlap_only_suggests() -> None:
    near = item("You met stakeholders every week")
    managed = area(build_plan(the_map(ROLE), [near], [], []), "stakeholder-management")
    assert managed.status == PlanStatus.BUILD
    assert managed.have == [] and managed.suggested[0].evidence_item_id == near.id
    assert managed.suggested[0].reason is None and "Confirm it" in managed.strengthen


def test_a_tagged_story_is_strong_and_a_confirmed_link_wins() -> None:
    story = StoryEvidence(id=uuid4(), title="The churn forecast", themes=("Forecasting",), text="")
    plan = build_plan(the_map(ROLE), [], [story], [])
    assert area(plan, "forecasting").status == PlanStatus.STRONG
    assert area(plan, "forecasting").have[0].reason == CoverageReason.CONFIRMED

    # Nothing matches "Python" by words, but the person says this item shows it.
    unrelated = item("You automated the monthly close")
    confirmed = [link(ROLE, "python", evidence=unrelated.id), link(ROLE, "experimentation", story=story.id)]
    plan = build_plan(the_map(ROLE, needs=NEEDS[1:]), [unrelated], [story], confirmed)
    assert area(plan, "python").status == PlanStatus.GOOD
    assert area(plan, "python").have[0].reason == CoverageReason.CONFIRMED
    assert area(plan, "experimentation").status == PlanStatus.STRONG


def test_dismissed_links_never_show() -> None:
    sql_item = item("You wrote SQL queries for the weekly report", tools=["SQL"])
    near = item("You met stakeholders every week")
    dismissed = [link(ROLE, "sql", evidence=sql_item.id, confirmed=False), link(ROLE, "stakeholder-management", evidence=near.id, confirmed=False)]
    plan = build_plan(the_map(ROLE), [sql_item, near], [], dismissed)
    assert area(plan, "sql").status == PlanStatus.BUILD and area(plan, "sql").have == []
    assert area(plan, "stakeholder-management").suggested == []
    assert all(proof.evidence_item_id != sql_item.id for proof in (*area(plan, "sql").have, *area(plan, "sql").suggested))


def test_a_confirmed_link_to_an_item_no_longer_approved_does_not_count() -> None:
    gone = item("You built the pricing model", status="REMOVED")
    plan = build_plan(the_map(ROLE), [gone], [], [link(ROLE, "forecasting", evidence=gone.id)])
    assert area(plan, "forecasting").status == PlanStatus.BUILD


def test_needs_review_preparing_and_unavailable_have_no_areas() -> None:
    assert build_plan(the_map(ROLE, experience=ExperienceState.NEEDS_REVIEW), [], [], []).state == PlanState.NEEDS_REVIEW
    assert build_plan(the_map(ROLE, experience=ExperienceState.NEEDS_REVIEW), [], [], []).areas == []
    assert build_plan(the_map(ROLE, state=MapState.ROLE_PREPARING), [], [], []).state == PlanState.PREPARING
    assert build_plan(the_map(ROLE, state=MapState.ROLE_UNREADABLE), [], [], []).state == PlanState.UNAVAILABLE


def test_recommended_is_the_first_need_not_yet_strong() -> None:
    story = StoryEvidence(id=uuid4(), title="Weekly SQL report", themes=("SQL",), text="")
    plan = build_plan(the_map(ROLE), [], [story], [])
    assert plan.recommended_area_key == "stakeholder-management"


def test_sentence_case_keeps_acronyms() -> None:
    assert sentence_case("Stakeholder Management") == "Stakeholder management"
    assert sentence_case("Power BI dashboards") == "Power BI dashboards"


def test_plan_copy_avoids_levels_and_numbers() -> None:
    plan = build_plan(the_map(ROLE), [item("You met stakeholders every week")], [], [])
    text = " ".join(area.strengthen for area in plan.areas).lower()
    for word in ("intermediate", "score", "%", "evidence", "gap", "weak"):
        assert word not in text


# ------------------------------------------------------------------ the routes


def _story(title, themes):
    return SimpleNamespace(id=uuid4(), title=title, themes=list(themes), **{part: None for part in STORY_PARTS})


class FakeReadiness:
    def __init__(self, owned, evidence):
        self.owned, self.evidence = owned, evidence

    async def interview_map(self, role_profile_id, user_id):
        if role_profile_id not in self.owned.get(user_id, ()):
            raise RoleProfileNotFoundForUser
        return the_map(role_profile_id)

    async def approved_evidence(self, user_id):
        return [row for row in self.evidence if row.user_id == user_id and row.status == "APPROVED"]


class FakeStories:
    def __init__(self, rows):
        self.rows = rows  # {user_id: [story]}

    async def list_for_user(self, user_id):
        return self.rows.get(user_id, [])

    async def framings_for_user(self, user_id, role_profile_id=None):
        return []

    async def get(self, story_id, user_id):
        return next((row for row in self.rows.get(user_id, []) if row.id == story_id), None)


@pytest.fixture
def world():
    mine, theirs = profile(USER_A), profile(USER_B, "Designer")
    sql_item = item("You wrote SQL queries for the weekly report", tools=["SQL"])
    their_item = item("You ran design sprints", user=USER_B)
    their_story = _story("A design sprint", ["Python"])
    links = MemoryCoverageLinkRepository()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_token_verifier] = lambda: RoleVerifier()
    app.dependency_overrides[get_readiness_service] = lambda: FakeReadiness(
        {USER_A: {mine.id}, USER_B: {theirs.id}}, [sql_item, their_item]
    )
    app.dependency_overrides[get_role_analysis_service] = lambda: FakeRoles({USER_A: [(mine, frozenset({mine.id}))]})
    app.dependency_overrides[get_role_preference_store] = lambda: MemoryPreferences(current=mine.id)
    app.dependency_overrides[get_story_repository] = lambda: FakeStories({USER_B: [their_story]})
    app.dependency_overrides[get_coverage_link_repository] = lambda: links
    return SimpleNamespace(
        client=TestClient(app), mine=mine, theirs=theirs, sql_item=sql_item,
        their_item=their_item, their_story=their_story, links=links,
    )


def test_get_defaults_to_the_active_role(world) -> None:
    body = world.client.get("/api/v1/plan", headers=A).json()
    assert body["role"] == {"role_profile_id": str(world.mine.id), "target_role": "Data Analyst"}
    assert body["state"] == "READY" and len(body["areas"]) == 5
    assert body["areas"][0]["status"] == "GOOD" and body["recommended_area_key"] == "sql"


def test_no_role_means_no_role_state(world) -> None:
    body = world.client.get("/api/v1/plan", headers=B).json()  # B has no role family in FakeRoles
    assert body == {"role": None, "state": "NO_ROLE", "areas": [], "recommended_area_key": None}


def test_a_foreign_role_is_404_for_read_and_link(world) -> None:
    assert world.client.get(f"/api/v1/plan?role_profile_id={world.theirs.id}", headers=A).status_code == 404
    put = world.client.put(
        f"/api/v1/plan/{world.theirs.id}/areas/sql/link", headers=A,
        json={"evidence_item_id": str(world.sql_item.id), "confirmed": True},
    )
    assert put.status_code == 404 and world.links.rows == {}


def test_owner_isolation_for_items_stories_and_needs(world) -> None:
    url = f"/api/v1/plan/{world.mine.id}/areas/forecasting/link"
    assert world.client.put(url, headers=A, json={"evidence_item_id": str(world.their_item.id), "confirmed": True}).status_code == 404
    assert world.client.put(url, headers=A, json={"story_id": str(world.their_story.id), "confirmed": True}).status_code == 404
    unknown = f"/api/v1/plan/{world.mine.id}/areas/not-a-need/link"
    assert world.client.put(unknown, headers=A, json={"evidence_item_id": str(world.sql_item.id), "confirmed": True}).status_code == 404
    both = {"evidence_item_id": str(world.sql_item.id), "story_id": str(world.their_story.id), "confirmed": True}
    assert world.client.put(url, headers=A, json=both).status_code == 422
    assert world.links.rows == {}


def test_confirm_then_dismiss_updates_the_plan(world) -> None:
    url = f"/api/v1/plan/{world.mine.id}/areas/forecasting/link"
    body = world.client.put(url, headers=A, json={"evidence_item_id": str(world.sql_item.id), "confirmed": True}).json()
    forecasting = next(area for area in body["areas"] if area["key"] == "forecasting")
    assert forecasting["status"] == "GOOD" and forecasting["have"][0]["reason"] == "CONFIRMED"

    body = world.client.put(url, headers=A, json={"evidence_item_id": str(world.sql_item.id), "confirmed": False}).json()
    forecasting = next(area for area in body["areas"] if area["key"] == "forecasting")
    assert forecasting["status"] == "BUILD" and forecasting["have"] == [] and forecasting["suggested"] == []
    assert len(world.links.rows) == 1  # one choice per need and item, updated in place

    # The other person's view of their own role is untouched by A's links.
    assert world.client.get(f"/api/v1/plan?role_profile_id={world.theirs.id}", headers=B).status_code == 200


@pytest.mark.asyncio
async def test_memory_links_are_owner_scoped() -> None:
    repo = MemoryCoverageLinkRepository()
    target = uuid4()
    await repo.save(USER_A, ROLE, "sql", LinkChoice(evidence_item_id=target, confirmed=True))
    assert await repo.list_for_role(USER_B, ROLE) == []
    assert [row.evidence_item_id for row in await repo.list_for_role(USER_A, ROLE)] == [target]
