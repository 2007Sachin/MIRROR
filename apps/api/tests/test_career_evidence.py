"""Career Evidence: a clean, reviewable, owner-scoped record of experience, and the only source the map reads."""

from __future__ import annotations

import asyncio
import re
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, get_current_user
from app.career_evidence import (
    CareerEvidenceService,
    EvidenceState,
    EvidenceStatus,
    EvidenceUnavailable,
    MemoryEvidenceRepository,
)
from app.evidence_quality import evidence_drafts, first_person, is_noise
from app.interview_map import Coverage, CoverageReason, ExperienceState, coverage_for
from app.pressure_test import build_pressure_test
from app.readiness_service import ReadinessService
from app.resume_models import (
    ResumeAchievement,
    ResumeAgentOutput,
    ResumeProject,
    ResumeSkill,
    ResumeTool,
    ResumeWorkExperience,
)
from app.routes_evidence import get_career_evidence_service, router
from app.story_repository import MemoryStoryRepository
from tests.test_interview_map import (
    OUTPUT,
    USER,
    FakeDocuments,
    FakeResumes,
    FakeRoles,
    _document,
    claim,
    competency,
    resume,
    role,
)

OTHER = uuid4()

CONTACT = ("priya.sharma@example.com", "+91 98765 43210", "Bengaluru, Karnataka", "linkedin.com/in/priya-sharma")

SYNTHETIC = ResumeAgentOutput(
    skills=[
        ResumeSkill(name="SQL", category="TECHNICAL", source_reference="[Page 1]", confidence=0.9),
        ResumeSkill(name="Skills", category="OTHER", source_reference="[Page 1]", confidence=0.5),
        ResumeSkill(name="https://github.com/priya", category="OTHER", source_reference="[Page 1]", confidence=0.5),
    ],
    tools=[ResumeTool(name="Power BI", source_reference="[Page 1]", confidence=0.9)],
    achievements=[
        ResumeAchievement(title="Priya Sharma", description="Priya Sharma", source_reference="[Page 1]"),
        ResumeAchievement(title="Cut month-end close from 6 days to 2 days", description="Rebuilt the reconciliation in SQL", source_reference="[Page 1]"),
        ResumeAchievement(title="Saved ₹40 lakh a year by renegotiating 12 vendor contracts", description="Saved ₹40 lakh a year by renegotiating 12 vendor contracts", source_reference="[Page 2]"),
    ],
    work_experience=[ResumeWorkExperience(
        organization="Acme Retail", role="Sales Analyst", source_reference="[Page 1]",
        claimed_outcomes=[
            "Increased repeat orders by 18% in two quarters",
            "Reduced stock-outs by 30% across 40 stores",
            "Automated 15 weekly reports, saving 10 hours a week",
            "priya.sharma@example.com | +91 98765 43210",
        ],
        claimed_responsibilities=[
            "Prepared weekly sales reports for regional managers",
            "Bengaluru, Karnataka",
            "linkedin.com/in/priya-sharma",
            "WORK EXPERIENCE",
            "References available upon request",
            "12 MG Road, Bengaluru 560001",
        ],
    )],
    projects=[ResumeProject(
        project_name="Churn model", description="Built a churn model in Power BI that cut churn by 12%",
        technologies=["Power BI", "SQL"], claimed_outcomes=["Grew renewals by 9% in one year"], source_reference="[Page 2]",
    )],
)


def test_the_quality_gate_keeps_quantified_work_first_and_drops_contact_details() -> None:
    drafts = evidence_drafts(SYNTHETIC, [claim("priya.sharma@example.com"), claim("Phone: +91 98765 43210")])
    top = drafts[:6]
    assert {draft.kind for draft in top} <= {"ACHIEVEMENT", "PROJECT"}
    assert all(re.search(r"\d", draft.title) for draft in top)
    shown = " ".join(" ".join(filter(None, (d.title, d.detail, d.outcome, d.metric, d.source_label, *d.tools))) for d in drafts)
    for detail in (*CONTACT, "Priya Sharma", "WORK EXPERIENCE", "References", "MG Road", "github", "Page"):
        assert detail.casefold() not in shown.casefold(), detail
    assert {"SQL", "Power BI"} <= {d.title for d in drafts if d.kind == "SKILL"}
    assert "Skills" not in {d.title for d in drafts}
    keys = [draft.source_key for draft in drafts]
    assert len(keys) == len(set(keys)) and keys == [d.source_key for d in evidence_drafts(SYNTHETIC)]  # stable


def test_titles_rephrase_only_the_subject_and_carry_what_was_there() -> None:
    drafts = {draft.title: draft for draft in evidence_drafts(SYNTHETIC)}
    close = drafts["You cut month-end close from 6 days to 2 days"]
    assert close.detail == "Rebuilt the reconciliation in SQL" and close.tools == ["SQL"] and close.metric == "6 days"
    assert close.source_label == "From your resume"
    orders = drafts["You increased repeat orders by 18% in two quarters"]
    assert orders.metric == "18%" and orders.source_label == "From your resume - Sales Analyst at Acme Retail"
    churn = drafts["You built a churn model in Power BI that cut churn by 12%"]
    assert churn.kind == "PROJECT" and churn.outcome == "Grew renewals by 9% in one year"
    assert set(churn.tools) == {"Power BI", "SQL"} and churn.source_label == "From your resume - Churn model project"
    assert first_person("I improved reporting") == "You improved reporting"
    assert first_person("Advanced Excel") == "Advanced Excel"  # unsure: the person's own wording stays
    assert first_person("Responsible for vendor payments") == "You were responsible for vendor payments"


def test_real_statements_are_not_mistaken_for_noise() -> None:
    for kept in ("Led a gender diversity hiring drive", "Managed 5 accounts in the banking sector",
                 "Set up CI with GitHub Actions to address flaky releases", "Best Employee Award"):
        assert not is_noise(kept), kept
    for dropped in (*CONTACT, "Priya Sharma", "EDUCATION", "Skills:", "[Page 1]", "221B Baker Street, London"):
        assert is_noise(dropped), dropped
    assert not is_noise("SQL", named=True) and is_noise("SQL")


# ------------------------------------------------------------------ service


class Documents:
    def __init__(self, *owners):
        self.documents = [_document(owner) for owner in owners]

    async def list_for_user(self, user_id, *, include_archived=False):
        return [doc for doc in self.documents if doc.user_id == user_id]


def make_service(analysis=None, owners=(USER, OTHER), repo=None):
    repo = repo or MemoryEvidenceRepository()
    return CareerEvidenceService(repo, Documents(*owners), FakeResumes(analysis or resume(SYNTHETIC))), repo


def run(coro):
    return asyncio.run(coro)


def test_states_say_what_is_happening_with_the_resume() -> None:
    service, _ = make_service(owners=())
    assert run(service.list(USER)).state == EvidenceState.NO_RESUME
    reading = CareerEvidenceService(MemoryEvidenceRepository(), Documents(USER), FakeResumes(None))
    assert run(reading.list(USER)).state == EvidenceState.READING  # uploaded, never read
    assert run(make_service(resume(status="PROCESSING"))[0].list(USER)).state == EvidenceState.READING
    failed = run(make_service(resume(status="FAILED"))[0].list(USER))
    assert failed.state == EvidenceState.UNREADABLE and failed.items == []
    ready = run(make_service()[0].list(USER))
    assert ready.state == EvidenceState.READY and ready.items
    assert all(item.status == EvidenceStatus.PENDING and not item.edited for item in ready.items)


def test_items_are_created_once_per_source() -> None:
    service, repo = make_service()
    first = run(service.list(USER))
    run(service.approve(USER, [first.items[0].id]))
    second = run(service.list(USER))
    assert [item.id for item in second.items] == [item.id for item in first.items]
    assert len(repo.rows) == len(first.items)
    assert second.items[0].status == EvidenceStatus.APPROVED  # a re-read never resets a decision


def test_approve_edit_remove_and_merge() -> None:
    from app.career_evidence import EvidenceMergeInvalid, EvidenceUpdate

    service, _ = make_service()
    a, b, c = run(service.list(USER)).items[:3]
    approved = run(service.approve(USER, [a.id, b.id, a.id]))
    assert {item.id for item in approved} == {a.id, b.id} and all(i.status == EvidenceStatus.APPROVED for i in approved)

    same = run(service.update(USER, a.id, EvidenceUpdate(title=a.title)))
    assert same.edited is False  # nothing changed
    edited = run(service.update(USER, a.id, EvidenceUpdate(title="You cut the close to two days", metric="2 days")))
    assert edited.edited and edited.title == "You cut the close to two days" and edited.status == EvidenceStatus.APPROVED

    removed = run(service.update(USER, c.id, EvidenceUpdate(status="REMOVED")))
    assert removed.status == EvidenceStatus.REMOVED and removed.edited is False

    merged = run(service.merge(USER, b.id, a.id))
    assert merged.status == EvidenceStatus.REMOVED and merged.merged_into == a.id
    assert [item.id for item in run(service.approved_items(USER))] == [a.id]
    with pytest.raises(EvidenceMergeInvalid):
        run(service.merge(USER, a.id, a.id))
    with pytest.raises(EvidenceMergeInvalid):
        run(service.merge(USER, a.id, c.id))  # c was removed
    restored = run(service.update(USER, b.id, EvidenceUpdate(status="PENDING")))
    assert restored.merged_into is None


# ------------------------------------------------------------------ routes


@pytest.fixture
def client():
    service, repo = make_service()
    users = {"a": USER, "b": OTHER}
    app = FastAPI()
    app.include_router(router)

    def current_user(request: Request) -> AuthenticatedUser:
        return AuthenticatedUser(id=users[request.headers["x-user"]], email="person@example.com")

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_career_evidence_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client, repo


A, B = {"x-user": "a"}, {"x-user": "b"}


def test_routes_list_edit_approve_and_merge(client) -> None:
    http, _ = client
    listed = http.get("/api/v1/career-evidence", headers=A)
    assert listed.status_code == 200
    body = listed.json()
    assert body["state"] == "READY"
    first, second = body["items"][:2]
    assert set(first) == {"id", "kind", "title", "detail", "outcome", "metric", "tools", "source_label",
                          "status", "merged_into", "edited", "updated_at"}  # never user_id or source_key

    patched = http.patch(f"/api/v1/career-evidence/{first['id']}", headers=A, json={"detail": "  I rebuilt it  in SQL "})
    assert patched.status_code == 200 and patched.json()["detail"] == "I rebuilt it in SQL" and patched.json()["edited"]
    assert http.patch(f"/api/v1/career-evidence/{first['id']}", headers=A, json={"title": ""}).status_code == 422
    assert http.patch(f"/api/v1/career-evidence/{first['id']}", headers=A, json={"user_id": str(OTHER)}).status_code == 422

    approved = http.post("/api/v1/career-evidence/approve", headers=A, json={"ids": [first["id"], second["id"]]})
    assert approved.status_code == 200 and {item["status"] for item in approved.json()} == {"APPROVED"}

    merged = http.post(f"/api/v1/career-evidence/{second['id']}/merge", headers=A, json={"into": first["id"]})
    assert merged.status_code == 200 and merged.json()["status"] == "REMOVED" and merged.json()["merged_into"] == first["id"]
    assert http.post(f"/api/v1/career-evidence/{first['id']}/merge", headers=A, json={"into": first["id"]}).status_code == 409


def test_another_person_can_never_read_or_change_your_items(client) -> None:
    http, repo = client
    mine = http.get("/api/v1/career-evidence", headers=A).json()["items"]
    theirs = http.get("/api/v1/career-evidence", headers=B).json()["items"]
    assert {item["id"] for item in mine}.isdisjoint({item["id"] for item in theirs})
    target = mine[0]["id"]

    assert http.patch(f"/api/v1/career-evidence/{target}", headers=B, json={"status": "REMOVED"}).status_code == 404
    assert http.post("/api/v1/career-evidence/approve", headers=B, json={"ids": [theirs[0]["id"], target]}).status_code == 404
    assert http.post(f"/api/v1/career-evidence/{target}/merge", headers=B, json={"into": theirs[0]["id"]}).status_code == 404
    assert http.post(f"/api/v1/career-evidence/{theirs[0]['id']}/merge", headers=B, json={"into": target}).status_code == 404
    assert all(row.status == EvidenceStatus.PENDING for row in repo.rows.values())  # nothing moved, not even B's own
    assert http.patch(f"/api/v1/career-evidence/{uuid4()}", headers=A, json={"status": "APPROVED"}).status_code == 404


def test_storage_that_does_not_answer_is_a_503() -> None:
    class Down(MemoryEvidenceRepository):
        async def list_for_user(self, user_id):
            raise EvidenceUnavailable

    service, _ = make_service(repo=Down())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(id=USER, email="person@example.com")
    app.dependency_overrides[get_career_evidence_service] = lambda: service
    with TestClient(app) as http:
        assert http.get("/api/v1/career-evidence").status_code == 503


# ------------------------------------------------------------------ the map reads only approved items


def _item(kind="ACHIEVEMENT", title="You built a pricing model", status="APPROVED", **fields):
    from datetime import UTC, datetime

    from app.career_evidence import EvidenceItem

    return EvidenceItem(id=uuid4(), user_id=USER, source_key=str(uuid4()), kind=kind, title=title, status=status,
                        updated_at=datetime.now(UTC), **fields)


def test_every_experience_link_says_why_and_a_skill_name_alone_is_not_enough() -> None:
    cases = [
        ("SQL", _item(tools=["SQL"]), CoverageReason.TOOL),
        ("Revenue growth", _item(outcome="Revenue growth of 20% in a year"), CoverageReason.OUTCOME),
        ("Pricing", _item(title="You recommended a new pricing tier"), CoverageReason.DECISION),
        ("Pricing", _item(title="You built the pricing model"), CoverageReason.CAPABILITY),
    ]
    for theme, item, reason in cases:
        coverage, matches = coverage_for(theme, None, [], evidence=[item])
        assert coverage == Coverage.EXPERIENCE and matches[0].reason == reason and matches[0].evidence_id == item.id
    skill = _item(kind="SKILL", title="SQL")
    assert coverage_for("SQL", None, [], evidence=[skill])[0] == Coverage.MENTIONED
    assert coverage_for("SQL", None, [], evidence=[_item(tools=["SQL"], status="PENDING")])[0] == Coverage.MISSING


def test_the_map_waits_for_review_then_uses_only_approved_items() -> None:
    analysis = role([competency("Data analysis"), competency("Pricing")])
    evidence, _ = make_service(resume(OUTPUT))
    readiness = ReadinessService(FakeRoles(analysis), FakeDocuments([_document()]), FakeResumes(resume(OUTPUT)),
                                 MemoryStoryRepository(), None, evidence=evidence)

    before = run(readiness.interview_map(analysis.id, USER))
    assert before.experience_state == ExperienceState.NEEDS_REVIEW
    assert all(theme.coverage == Coverage.MISSING for theme in before.themes)  # raw resume text is never guessed from
    assert [area.key for area in before.preparation_areas] == ["review-experience"]

    items = run(evidence.list(USER)).items  # the person opens their experience: all pending
    assert run(readiness.interview_map(analysis.id, USER)).experience_state == ExperienceState.NEEDS_REVIEW
    project = next(item for item in items if item.kind == "PROJECT")
    run(evidence.approve(USER, [project.id]))

    after = run(readiness.interview_map(analysis.id, USER))
    coverage = {theme.name: theme for theme in after.themes}
    assert after.experience_state == ExperienceState.READY
    assert coverage["Data analysis"].coverage == Coverage.EXPERIENCE
    assert {match.evidence_id for match in coverage["Data analysis"].matches} == {project.id}
    assert all(match.reason for match in coverage["Data analysis"].matches)
    assert coverage["Pricing"].coverage in (Coverage.EXPERIENCE, Coverage.MENTIONED)
    assert all(match.evidence_id == project.id for match in coverage["Pricing"].matches)

    without_source = ReadinessService(FakeRoles(analysis), FakeDocuments([_document()]), FakeResumes(resume(OUTPUT)),
                                      MemoryStoryRepository(), None)
    assert run(without_source.interview_map(analysis.id, USER)).experience_state == ExperienceState.READY  # unwired: unchanged


def test_dig_deeper_never_offers_contact_or_heading_text() -> None:
    claims = [claim("priya.sharma@example.com"), claim("+91 98765 43210"), claim("WORK EXPERIENCE"),
              claim("Priya Sharma"), claim("Cut costs by 20%", metric=20.0), claim("SQL", claim_type="SKILL")]
    built = build_pressure_test(role([competency("Cost control")]), resume(OUTPUT, claims), has_resume_document=True)
    assert {item.statement for item in built.items} == {"Cut costs by 20%", "SQL"}
