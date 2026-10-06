"""Synthetic end-to-end tests for research changing target product behavior.

All company, geography, source and claim content here is fictional test data.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.interview_engine import InterviewStateMachine
from app.repository import MemorySessionRepository
from app.research_catalog import CatalogDocument, RepoResearchCatalog, content_sha256, load_catalog
from app.target_rounds import get_round
from app.target_repository import MemoryTargetRepository, TargetValues
from app.target_service import PracticeStart, StaticCatalogProvider, TargetService, _round_claims, competencies_in_process, round_summaries

COMPANY = "fictional_co"
ROLE = "software_development_engineering"
GEO = "fictional_region"
CLAIM_ID = "fictional_co.sde.sde_ii.synthetic_process"
STATEMENT = "The fictional company uses a structured debugging exercise for this fictional region."
EXCERPT = "Fictional source: You have just written a small function in a fictional setting."


def synthetic_catalog(
    *, geography: str | None = GEO, level: str = "sde_ii", subject: str = "coding_interview",
    include_claim: bool = True,
) -> RepoResearchCatalog:
    raw = json.loads(load_catalog().document.model_dump_json(by_alias=True))
    raw["version"] = 77
    raw["supersedes_version"] = 76
    raw["sources"] = [{
        "id": "synthetic-source", "url": "https://example.invalid/fictional-source",
        "publisher": "Fictional Research Publisher", "tier": "T1_OFFICIAL", "official": True,
        "published_at": "2026-01-01", "retrieved_at": "2026-10-01",
        "text_sha256_prefix": "0123456789abcdef", "independence_group": "fictional_group",
        "access_note": "Synthetic fixture; no external source is represented.",
    }]
    raw["claims"] = [{
        "id": CLAIM_ID, "version": 1, "verifier_ref": "synthetic-fixture", "status": "PUBLISHED",
        "provenance_class": "FACT", "dating": "PUBLISHED_DATE", "freshness": "CURRENT",
        "published_at": "2026-01-01", "retrieved_at": "2026-10-01", "confidence_band": "HIGH",
        "confidence_features": {},
        "scope": {"company": COMPANY, "role_family": ROLE, "level": level, "geography": geography or GEO},
        "subject": subject, "predicate": "exercise", "value": "structured_debugging",
        "statement": STATEMENT, "limits": [], "process_content": True, "candidate_visible": True,
        "conflict_set": None, "staleness_flags": [], "supersedes": None, "basis_claim_ids": [],
        "evidence": [{"source_id": "synthetic-source", "stance": "SUPPORTS", "excerpt": EXCERPT}],
    }] if include_claim else []
    raw["conflict_sets"] = []
    raw["unknowns"] = []
    raw["status"] = "DRAFT"
    raw["supersedes_version"] = None
    raw["verifier_receipt"] = None
    doc = CatalogDocument.model_validate(raw)
    canonical = json.dumps(raw, sort_keys=True).encode()
    return RepoResearchCatalog(doc, content_sha256(canonical))


def install_synthetic_round_mapping(monkeypatch, *, mapped_round="coding_reasoning"):
    import app.target_service as service_module

    monkeypatch.setattr(service_module, "_mapping_for", lambda _match: {
        "rounds": {mapped_round: [CLAIM_ID]}, "round_specific_claims": [],
    })


def test_in_scope_synthetic_research_changes_blueprint_round_and_priority_basis(monkeypatch):
    from app.research_catalog import TargetScope, match_scope

    install_synthetic_round_mapping(monkeypatch)
    match = match_scope(synthetic_catalog(), TargetScope(
        company=COMPANY, role_family=ROLE, level="sde_ii", geography=GEO,
    ))
    blueprint_rounds = round_summaries(match)
    coding = get_round("coding_reasoning")
    assert match.state == "RESEARCHED"
    assert CLAIM_ID in {claim.id for claim in match.claims}
    assert any(r.key == coding.key and r.basis == "PUBLISHED_GUIDANCE" for r in blueprint_rounds)
    assert _round_claims(match, coding)
    assert any(c.round_count > 0 and c.band == "HIGH" for c in competencies_in_process(match))


def test_removing_rescoping_or_level_mismatch_removes_product_effects(monkeypatch):
    from app.research_catalog import TargetScope, match_scope

    install_synthetic_round_mapping(monkeypatch)
    target = TargetScope(company=COMPANY, role_family=ROLE, level="sde_ii", geography=GEO)
    for catalog in (
        synthetic_catalog(geography="another_fictional_region"),
        synthetic_catalog(include_claim=False),
        synthetic_catalog(level="sde_i"),
    ):
        match = match_scope(catalog, target)
        assert match.state == "NOT_RESEARCHED"
        assert all(r.basis == "MIRROR_SUGGESTED" for r in round_summaries(match))
        assert not _round_claims(match, get_round("coding_reasoning"))
        assert all(c.round_count == 0 and c.band is None for c in competencies_in_process(match))


def test_unmapped_research_claim_does_not_change_coding_round(monkeypatch):
    install_synthetic_round_mapping(monkeypatch, mapped_round="system_design")

    class NoStories:
        async def list_for_user(self, _user_id):
            return []

    repo = MemoryTargetRepository()
    user_id = uuid4()
    target = asyncio.run(repo.create_target(user_id, TargetValues(
        role_profile_id=uuid4(), company_label="Fictional Company", company_key=COMPANY,
        role_family_key=ROLE, level_key="sde_ii", level_label=None,
        geography_key=GEO, geography_label="Fictional region", interview_date=None,
    )))
    catalog = synthetic_catalog(subject="fictional_unmapped_subject")
    service = TargetService(
        repo, StaticCatalogProvider({catalog.version: catalog}), roles=None,
        stories=NoStories(), engine=None, today=lambda: date(2026, 10, 5),
    )

    blueprint = asyncio.run(service.blueprint(target.id, user_id))
    coding = next(round_ for round_ in blueprint.rounds if round_.key == "coding_reasoning")
    assert blueprint.match_state == "RESEARCHED"
    assert coding.basis == "MIRROR_SUGGESTED"

    detail = asyncio.run(service.round_detail(target.id, "coding_reasoning", user_id))
    assert detail.match_state == "RESEARCHED"
    assert CLAIM_ID not in {claim.key for claim in detail.claims}
    assert not any("IN_ONE_ROUND" in priority.reason_codes for priority in detail.priorities)
    assert detail.pack is not None
    assert all(prompt.rationale_code != "PUBLISHED_GUIDANCE_AREA" for prompt in detail.pack.prompts)

    system_detail = asyncio.run(service.round_detail(target.id, "system_design", user_id))
    assert any("IN_ONE_ROUND" in priority.reason_codes for priority in system_detail.priorities)
    assert system_detail.pack is not None
    assert any(prompt.rationale_code == "PUBLISHED_GUIDANCE_AREA" for prompt in system_detail.pack.prompts)


def test_out_of_scope_source_does_not_suppress_pack_but_matched_source_does(monkeypatch):

    from app.target_service import scope_match

    install_synthetic_round_mapping(monkeypatch)
    global_catalog = synthetic_catalog(geography="global")
    matched_catalog = synthetic_catalog(geography=GEO)
    repo = MemoryTargetRepository()
    user_id = uuid4()
    role_profile_id = uuid4()

    def make_target(geography_key: str):
        return asyncio.run(repo.create_target(user_id, TargetValues(
            role_profile_id=role_profile_id, company_label="Fictional Company", company_key=COMPANY,
            role_family_key=ROLE, level_key="sde_ii", level_label=None,
            geography_key=geography_key, geography_label="Fictional region", interview_date=None,
        )))

    out_of_scope = make_target("fictional_other_region")
    in_scope = make_target(GEO)

    class NoStories:
        async def list_for_user(self, _user_id):
            return []

    coding = get_round("coding_reasoning")
    out_service = TargetService(
        repo, StaticCatalogProvider({global_catalog.version: global_catalog}), roles=None,
        stories=NoStories(), engine=None, today=lambda: date(2026, 10, 5),
    )
    out_match = scope_match(out_of_scope, global_catalog)
    assert out_match.state == "NOT_RESEARCHED" and out_match.claims == ()
    out_pack = asyncio.run(out_service._pack(user_id, out_of_scope, coding, out_match, global_catalog))
    assert out_pack.state == "FULL"
    assert "coding.check_before_handover" in {prompt.template_id for prompt in out_pack.prompts}
    assert all(prompt.rationale_code != "PUBLISHED_GUIDANCE_AREA" for prompt in out_pack.prompts)

    in_service = TargetService(
        repo, StaticCatalogProvider({matched_catalog.version: matched_catalog}), roles=None,
        stories=NoStories(), engine=None, today=lambda: date(2026, 10, 5),
    )
    in_match = scope_match(in_scope, matched_catalog)
    assert in_match.state == "RESEARCHED" and CLAIM_ID in {claim.id for claim in in_match.claims}
    in_pack = asyncio.run(in_service._pack(user_id, in_scope, coding, in_match, matched_catalog))
    assert in_pack.state == "FULL"
    assert "coding.check_before_handover" not in {prompt.template_id for prompt in in_pack.prompts}
    assert any(prompt.rationale_code == "PUBLISHED_GUIDANCE_AREA" for prompt in in_pack.prompts)


def test_synthetic_research_changes_service_blueprint_round_detail_and_priorities(monkeypatch):
    install_synthetic_round_mapping(monkeypatch)

    class NoStories:
        async def list_for_user(self, _user_id):
            return []

    def service_for(catalog):
        repo = MemoryTargetRepository()
        user_id = uuid4()
        target = asyncio.run(repo.create_target(user_id, TargetValues(
            role_profile_id=uuid4(), company_label="Fictional Company", company_key=COMPANY,
            role_family_key=ROLE, level_key="sde_ii", level_label=None,
            geography_key=GEO, geography_label="Fictional region", interview_date=None,
        )))
        service = TargetService(
            repo, StaticCatalogProvider({catalog.version: catalog}), roles=None,
            stories=NoStories(), engine=None, today=lambda: date(2026, 10, 5),
        )
        return service, target, user_id

    researched, target, user_id = service_for(synthetic_catalog())
    blueprint = asyncio.run(researched.blueprint(target.id, user_id))
    coding = next(round_ for round_ in blueprint.rounds if round_.key == "coding_reasoning")
    assert blueprint.match_state == "RESEARCHED"
    assert CLAIM_ID in {claim.key for claim in blueprint.claims}
    assert coding.basis == "PUBLISHED_GUIDANCE"
    detail = asyncio.run(researched.round_detail(target.id, "coding_reasoning", user_id))
    assert detail.match_state == "RESEARCHED"
    assert CLAIM_ID in {claim.key for claim in detail.claims}
    assert any("IN_ONE_ROUND" in priority.reason_codes for priority in detail.priorities)
    assert detail.pack is not None
    assert any(prompt.rationale_code == "PUBLISHED_GUIDANCE_AREA" for prompt in detail.pack.prompts)

    unsupported, target, user_id = service_for(synthetic_catalog(include_claim=False))
    blueprint = asyncio.run(unsupported.blueprint(target.id, user_id))
    coding = next(round_ for round_ in blueprint.rounds if round_.key == "coding_reasoning")
    assert blueprint.match_state == "NOT_RESEARCHED"
    assert blueprint.claims == []
    assert coding.basis == "MIRROR_SUGGESTED"
    detail = asyncio.run(unsupported.round_detail(target.id, "coding_reasoning", user_id))
    assert detail.match_state == "NOT_RESEARCHED"
    assert detail.claims == []
    assert not any("IN_ONE_ROUND" in priority.reason_codes for priority in detail.priorities)
    assert detail.pack is not None
    assert all(prompt.rationale_code != "PUBLISHED_GUIDANCE_AREA" for prompt in detail.pack.prompts)


def test_practice_start_keeps_research_basis_separate_from_generated_question_origin(monkeypatch):
    install_synthetic_round_mapping(monkeypatch)

    class NoStories:
        async def list_for_user(self, _user_id):
            return []

    class Roles:
        async def get(self, _role_profile_id, _user_id):
            return SimpleNamespace(target_role="Software Development Engineer II")

    repo = MemoryTargetRepository()
    sessions = MemorySessionRepository()
    engine = InterviewStateMachine(sessions, total_time_budget_seconds=1200, phase_time_budget_seconds=180)
    user_id = uuid4()
    target = asyncio.run(repo.create_target(user_id, TargetValues(
        role_profile_id=uuid4(), company_label="Fictional Company", company_key=COMPANY,
        role_family_key=ROLE, level_key="sde_ii", level_label=None,
        geography_key=GEO, geography_label="Fictional region", interview_date=None,
    )))
    catalog = synthetic_catalog()
    service = TargetService(
        repo, StaticCatalogProvider({catalog.version: catalog}), roles=Roles(),
        stories=NoStories(), engine=engine, today=lambda: date(2026, 10, 5),
    )

    started = asyncio.run(service.start_round_practice(
        target.id, "coding_reasoning", user_id,
        PracticeStart(idempotency_key=uuid4()),
    ))
    assert len(started.prompts) == 4
    assert all(prompt.rationale_code == "PUBLISHED_GUIDANCE_AREA" for prompt in started.prompts)
    assert all("text" not in prompt.model_dump() for prompt in started.prompts)

    rows = sorted(repo.questions, key=lambda question: question.position)
    assert len(rows) == 4
    assert all(row.rationale_code == "PUBLISHED_GUIDANCE_AREA" for row in rows)
    assert all(row.provenance_class == "MIRROR_GENERATED" for row in rows)
    assert started.link.blueprint_id == rows[0].blueprint_id
