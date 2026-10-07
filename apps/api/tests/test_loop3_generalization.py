"""Loop 3: interview intelligence generalizes across role families through data, not code.

Every company, geography, source, claim and story here is fictional test data. Two synthetic
slices share one engine: a software-engineering slice ("QA Tech Co") and a business-roles slice
("QA Consulting Co", role family ``business_analysis``). A third, structurally different slice
exists only as data in ``test_third_slice_dry_run_needs_no_code_or_schema_change``.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import json
import re
from datetime import date, datetime, timedelta, UTC
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.interview_engine import InterviewStateMachine
from app.repository import MemorySessionRepository
from app.research_catalog import CatalogDocument, RepoResearchCatalog, content_sha256, load_catalog
from app.target_priority import CompetencyInProcess, PracticeFact, prioritise
from app.target_repository import MemoryTargetRepository, TargetSessionLink
from app.target_service import (
    PracticeStart,
    RoundNotFound,
    StaticCatalogProvider,
    TargetCreate,
    TargetService,
    UnsupportedTarget,
    competency_coverage,
    practice_facts,
)
from app.target_taxonomy import TaxonomyError, load_taxonomy, taxonomy_from_dict

ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_PATH = ROOT / "apps/api/app/research_content/taxonomy_v1.json"
SDE, BA = "software_development_engineering", "business_analysis"
GEO = "qa_land"
TECH, CONSULTING = "qa_tech_co", "qa_consulting"
TODAY = date(2026, 10, 7)

C_TECH_CODING = "qa_tech_co.sde.sde_ii.qa_land.coding_round"
C_TECH_BEHAVIOURAL = "qa_tech_co.sde.sde_ii.qa_land.behavioural_round"
C_BA_CASE = "qa_consulting.ba.consultant.qa_land.case_round"
C_BA_CASE_LENGTH_A = "qa_consulting.ba.consultant.qa_land.case_length.page_a"
C_BA_CASE_LENGTH_B = "qa_consulting.ba.consultant.qa_land.case_length.page_b"
C_BA_STAKEHOLDER = "qa_consulting.ba.consultant.qa_land.stakeholder_round"
C_BA_BEHAVIOURAL = "qa_consulting.ba.consultant.qa_land.behavioural_round"
BA_CLAIMS = {C_BA_CASE, C_BA_CASE_LENGTH_A, C_BA_CASE_LENGTH_B, C_BA_STAKEHOLDER, C_BA_BEHAVIOURAL}
TECH_CLAIMS = {C_TECH_CODING, C_TECH_BEHAVIOURAL}


# ------------------------------------------------------------------ synthetic data


def taxonomy_raw() -> dict:
    raw = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    raw["companies"][TECH] = {"aliases": ["QA Tech Co (synthetic)"], "process_terms": ["qa tech co"]}
    raw["companies"][CONSULTING] = {"aliases": ["QA Consulting Co (synthetic)"], "process_terms": ["qa consulting co"]}
    return raw


def synthetic_taxonomy(raw: dict | None = None):
    return taxonomy_from_dict(raw or taxonomy_raw())


def _claim(claim_id, company, family, level, subject, band="HIGH", *, conflict_set=None, excerpt=None):
    return {
        "id": claim_id, "version": 1, "verifier_ref": "synthetic-fixture", "status": "PUBLISHED",
        "provenance_class": "FACT", "dating": "PUBLISHED_DATE", "freshness": "CURRENT",
        "published_at": "2026-09-01", "retrieved_at": "2026-10-07", "confidence_band": band,
        "confidence_features": {},
        "scope": {"company": company, "role_family": family, "level": level, "geography": GEO},
        "subject": subject, "predicate": "includes", "value": subject,
        "statement": f"Synthetic statement about {subject} for a fictional company.",
        "limits": [], "process_content": True, "candidate_visible": True,
        "conflict_set": conflict_set, "staleness_flags": [], "supersedes": None, "basis_claim_ids": [],
        "evidence": [{"source_id": "synthetic-source", "stance": "SUPPORTS",
                      "excerpt": excerpt or f"Fictional page text about {subject.replace('_', ' ')} number {abs(hash(claim_id)) % 997}."}],
    }


def synthetic_catalog(*, drop: frozenset[str] = frozenset(), version: int = 77) -> RepoResearchCatalog:
    raw = json.loads(load_catalog().document.model_dump_json(by_alias=True))
    raw.update(version=version, supersedes_version=None, status="DRAFT", verifier_receipt=None, unknowns=[])
    raw["sources"] = [{
        "id": "synthetic-source", "url": "https://example.invalid/fictional-source",
        "publisher": "Fictional Research Publisher", "tier": "T1_OFFICIAL", "official": True,
        "published_at": "2026-09-01", "retrieved_at": "2026-10-07",
        "text_sha256_prefix": "0123456789abcdef", "independence_group": "fictional_group",
        "access_note": "Synthetic fixture; no external source is represented.",
    }]
    claims = [
        _claim(C_TECH_CODING, TECH, SDE, "sde_ii", "coding_interview"),
        _claim(C_TECH_BEHAVIOURAL, TECH, SDE, "sde_ii", "interview_loop", "MEDIUM"),
        _claim(C_BA_CASE, CONSULTING, BA, "consultant", "case_interview"),
        _claim(C_BA_CASE_LENGTH_A, CONSULTING, BA, "consultant", "case_interview", "MEDIUM", conflict_set="qa_consulting.case_length"),
        _claim(C_BA_CASE_LENGTH_B, CONSULTING, BA, "consultant", "case_interview", "LOW", conflict_set="qa_consulting.case_length"),
        _claim(C_BA_STAKEHOLDER, CONSULTING, BA, "consultant", "stakeholder_discussion", "MEDIUM"),
        _claim(C_BA_BEHAVIOURAL, CONSULTING, BA, "consultant", "behavioural_interview", "LOW"),
    ]
    raw["claims"] = [c for c in claims if c["id"] not in drop]
    members = [c["id"] for c in raw["claims"] if c["conflict_set"]]
    raw["conflict_sets"] = [{
        "key": "qa_consulting.case_length", "claim_ids": members, "resolution": "UNRESOLVED",
        "note": "Two fictional pages disagree; show both.",
    }] if len(members) == 2 else []
    if len(members) == 1:
        for claim in raw["claims"]:
            claim["conflict_set"] = None
    document = CatalogDocument.model_validate(raw)
    return RepoResearchCatalog(document, content_sha256(json.dumps(raw, sort_keys=True).encode()))


BASE_MAPPING = {
    "schema": "mirror.research_round_mapping/1",
    "rounds": {
        "coding_reasoning": [C_TECH_CODING],
        # One shared round key for two companies: only each target's own exact-scope claims count.
        "behavioural": [C_TECH_BEHAVIOURAL, C_BA_BEHAVIOURAL],
        "business_problem_solving": [C_BA_CASE, C_BA_CASE_LENGTH_A, C_BA_CASE_LENGTH_B],
        "requirements_and_stakeholders": [C_BA_STAKEHOLDER],
    },
    "round_specific_claims": [],
    "conditional_links": [{"claim_id": C_BA_STAKEHOLDER, "round_key": "requirements_and_stakeholders"}],
}


@pytest.fixture
def mapping(monkeypatch):
    import app.target_service as service_module

    current = copy.deepcopy(BASE_MAPPING)
    monkeypatch.setattr(service_module, "_mapping_for", lambda match: None if match.state == "NOT_RESEARCHED" else current)
    return current


class Roles:
    async def get(self, _role_profile_id, _user_id):
        return SimpleNamespace(target_role="QA synthetic role")


class Stories:
    def __init__(self, titles=()):
        self.titles = titles

    async def list_for_user(self, _user_id):
        return [SimpleNamespace(title=t, archived_at=None, role_profile_id=None, created_at=datetime(2026, 9, 1, tzinfo=UTC))
                for t in self.titles]


def world(catalog=None, taxonomy=None, coverage=None, stories=()):
    catalog = catalog or synthetic_catalog()
    repo = MemoryTargetRepository()
    engine = InterviewStateMachine(MemorySessionRepository(), total_time_budget_seconds=1200, phase_time_budget_seconds=180)
    service = TargetService(
        repo, StaticCatalogProvider({catalog.version: catalog}), roles=Roles(), stories=Stories(stories), engine=engine,
        today=lambda: TODAY, taxonomy=taxonomy or synthetic_taxonomy(), coverage=coverage,
    )
    return SimpleNamespace(repo=repo, service=service, engine=engine)


def make_target(w, user_id, *, company, family, level, geography=GEO):
    target, _ = asyncio.run(w.service.create(user_id, TargetCreate(
        role_profile_id=uuid4(), company=company, role_family=family, level=level,
        geography=geography, geography_label="QA Fictional Country",
    )))
    return target


def consulting_target(w, user_id, **over):
    values = {"company": "QA Consulting Co (synthetic)", "family": BA, "level": "consultant"} | over
    return make_target(w, user_id, **values)


def tech_target(w, user_id, **over):
    values = {"company": "QA Tech Co (synthetic)", "family": SDE, "level": "sde_ii"} | over
    return make_target(w, user_id, **values)


def blueprint_of(w, target, user_id):
    return asyncio.run(w.service.blueprint(target.id, user_id))


def round_of(w, target, user_id, key):
    return asyncio.run(w.service.round_detail(target.id, key, user_id))


def all_claim_keys(view) -> set[str]:
    keys = {c.key for c in view.claims}
    keys |= {c.key for conflict in view.conflicts for c in conflict.claims}
    return keys


# ------------------------------------------------------------------ 1. same engine, different intelligence


def test_one_engine_builds_meaningfully_different_blueprints(mapping):
    w, user = world(), uuid4()
    ba = blueprint_of(w, consulting_target(w, user), user)
    sde = blueprint_of(w, tech_target(w, user), user)

    assert [r.key for r in ba.rounds] == ["business_problem_solving", "requirements_and_stakeholders", "behavioural"]
    assert [r.key for r in sde.rounds] == ["coding_reasoning", "system_design", "behavioural"]
    assert {r.question_family for r in ba.rounds} == {"case_discussion", "workplace_scenario", "past_example"}
    assert {r.question_family for r in sde.rounds} == {"coding_walkthrough", "design_discussion", "past_example"}
    ba_competencies = {k for r in ba.rounds for k in r.competency_keys}
    sde_competencies = {k for r in sde.rounds for k in r.competency_keys}
    assert ba_competencies & sde_competencies == {"behavioural_examples"}  # the one genuinely shared skill
    case = next(r for r in ba.rounds if r.key == "business_problem_solving")
    assert len(case.competency_keys) == 3  # one round, several competencies

    assert (ba.match_state, sde.match_state) == ("RESEARCHED", "RESEARCHED")
    basis = {r.key: (r.basis, r.presence) for r in ba.rounds}
    assert basis == {
        "business_problem_solving": ("PUBLISHED_GUIDANCE", "CORE"),
        "requirements_and_stakeholders": ("PUBLISHED_GUIDANCE", "CONDITIONAL"),
        "behavioural": ("PUBLISHED_GUIDANCE", "CORE"),
    }
    assert {r.key: r.basis for r in sde.rounds} == {
        "coding_reasoning": "PUBLISHED_GUIDANCE", "system_design": "MIRROR_SUGGESTED", "behavioural": "PUBLISHED_GUIDANCE",
    }


def test_conflicting_research_is_shown_side_by_side_and_never_averaged(mapping):
    w, user = world(), uuid4()
    target = consulting_target(w, user)
    detail = round_of(w, target, user, "business_problem_solving")
    assert [c.key for c in detail.conflicts] == ["qa_consulting.case_length"]
    assert {c.key for c in detail.conflicts[0].claims} == {C_BA_CASE_LENGTH_A, C_BA_CASE_LENGTH_B}
    assert {c.confidence_band for c in detail.conflicts[0].claims} == {"MEDIUM", "LOW"}
    assert C_BA_CASE in {c.key for c in detail.claims}


# ------------------------------------------------------------------ 2. isolation


def test_amazon_style_and_consulting_research_never_cross(mapping):
    w, user = world(), uuid4()
    ba_target, sde_target = consulting_target(w, user), tech_target(w, user)
    ba_view, sde_view = blueprint_of(w, ba_target, user), blueprint_of(w, sde_target, user)
    assert all_claim_keys(ba_view) <= BA_CLAIMS and all_claim_keys(sde_view) <= TECH_CLAIMS

    # The shared "behavioural" key maps claims for both companies; each target sees only its own.
    ba_behavioural = round_of(w, ba_target, user, "behavioural")
    sde_behavioural = round_of(w, sde_target, user, "behavioural")
    assert all_claim_keys(ba_behavioural) <= BA_CLAIMS
    assert all_claim_keys(sde_behavioural) <= TECH_CLAIMS
    ba_bands = {p.competency_key: p.reason_codes for p in ba_behavioural.priorities}
    assert "IN_ONE_ROUND" in ba_bands["behavioural_examples"]

    # No engineering prompt can reach a business-roles round, and the reverse.
    ba_ids = {t.id for r in w.service._rounds(ba_target) for t in r.templates}
    sde_ids = {t.id for r in w.service._rounds(sde_target) for t in r.templates}
    assert ba_ids.isdisjoint(sde_ids)
    for key in ("business_problem_solving", "requirements_and_stakeholders", "behavioural"):
        pack = round_of(w, ba_target, user, key).pack
        assert {p.question_family for p in pack.prompts} <= {"case_discussion", "workplace_scenario", "past_example"}
        assert not {p.question_family for p in pack.prompts} & {"coding_walkthrough", "design_discussion"}


def test_a_round_of_another_role_family_does_not_exist_for_this_target(mapping):
    w, user = world(), uuid4()
    target = consulting_target(w, user)
    before = (len(w.repo.questions), len(w.repo.links))
    with pytest.raises(RoundNotFound):
        round_of(w, target, user, "coding_reasoning")
    with pytest.raises(RoundNotFound):
        asyncio.run(w.service.start_round_practice(target.id, "system_design", user, PracticeStart(idempotency_key=uuid4())))
    assert (len(w.repo.questions), len(w.repo.links)) == before


def test_unknown_role_family_or_a_level_from_another_family_is_refused_before_any_write():
    w, user = world(), uuid4()
    for family, level in ((BA, "sde_ii"), (SDE, "consultant"), ("astronaut", "not_sure")):
        with pytest.raises(UnsupportedTarget):
            make_target(w, user, company="QA Consulting Co (synthetic)", family=family, level=level)
    assert asyncio.run(w.repo.list_targets(user)) == []


def test_company_names_resolve_only_through_exact_taxonomy_aliases():
    taxonomy = load_taxonomy()
    assert taxonomy.company_key("Amazon") == "amazon"
    # Two India hiring entities stay separate keys; research for one never reaches the other.
    assert taxonomy.company_key("  deloitte INDIA ") == "deloitte_india"
    assert taxonomy.company_key("Deloitte Touche Tohmatsu India LLP") == "deloitte_india"
    assert taxonomy.company_key("Deloitte USI") == "deloitte_usi"
    assert taxonomy.company_key("Deloitte Consulting India Private Limited") == "deloitte_usi"
    # A bare brand names no entity, and other member firms are not guessed into either.
    assert taxonomy.company_key("Deloitte") is None
    assert taxonomy.company_key("Deloitte Consulting LLP") is None


def test_candidate_a_plan_never_affects_candidate_b(mapping):
    calls = []

    async def coverage(role_profile_id, user_id):
        calls.append(user_id)
        return [("Stakeholder management", "STRONG")] if user_id == alice else []

    alice, bob = uuid4(), uuid4()
    w = world(coverage=coverage)
    a_target, b_target = consulting_target(w, alice), consulting_target(w, bob)
    a = {p.competency_key: p.reason_codes for p in round_of(w, a_target, alice, "requirements_and_stakeholders").priorities}
    b = {p.competency_key: p.reason_codes for p in round_of(w, b_target, bob, "requirements_and_stakeholders").priorities}
    assert "NOT_LINKED_TO_YOUR_PLAN" not in a["stakeholder_communication"]
    assert "NOT_LINKED_TO_YOUR_PLAN" in b["stakeholder_communication"]
    assert calls == [alice, bob]
    with pytest.raises(Exception):
        round_of(w, a_target, bob, "requirements_and_stakeholders")  # not Bob's target


# ------------------------------------------------------------------ 3. mutations change output deterministically


def _snapshot(w, target, user):
    view = blueprint_of(w, target, user)
    rounds = [(r.key, r.basis, r.presence) for r in view.rounds]
    first = view.rounds[0].key
    detail = round_of(w, target, user, first)
    return (view.match_state, tuple(rounds), tuple(sorted(all_claim_keys(view))),
            tuple((p.competency_key, tuple(p.reason_codes)) for p in detail.priorities))


def test_every_mutation_changes_downstream_output_deterministically(mapping):
    user = uuid4()

    def run(*, catalog=None, coverage=None, mapping_edit=None, **target_over):
        if mapping_edit:
            mapping_edit(mapping)
        w = world(catalog=catalog, coverage=coverage)
        target = consulting_target(w, user, **target_over)
        first, second = _snapshot(w, target, user), _snapshot(w, target, user)
        assert first == second, "same inputs, same output"
        mapping.clear()
        mapping.update(copy.deepcopy(BASE_MAPPING))
        return first

    base = run()
    assert base[0] == "RESEARCHED"
    mutations = {
        "remove evidence": run(catalog=synthetic_catalog(drop=frozenset(BA_CLAIMS))),
        "rescope geography": run(geography="qa_other_land"),
        "change role family": run(family=SDE, level="sde_ii"),
        "change seniority": run(level="analyst"),
        "change company": run(company="QA Tech Co (synthetic)"),
        "change round": run(mapping_edit=lambda m: m["rounds"].update(
            business_problem_solving=[], requirements_and_stakeholders=[C_BA_STAKEHOLDER, C_BA_CASE])),
        "change candidate evidence": run(coverage=_strong_problem_solving),
    }
    for name, result in mutations.items():
        assert result != base, name
    for name in ("remove evidence", "rescope geography", "change role family", "change seniority", "change company"):
        assert mutations[name][0] == "NOT_RESEARCHED", name
        assert mutations[name][2] == (), name
        assert all(basis == "MIRROR_SUGGESTED" for _, basis, _ in mutations[name][1]), name
    assert dict((k, b) for k, b, _ in mutations["change round"][1])["business_problem_solving"] == "MIRROR_SUGGESTED"
    assert [k for k, *_ in mutations["change role family"][1]] == ["coding_reasoning", "system_design", "behavioural"]


async def _strong_problem_solving(_role_profile_id, _user_id):
    return [("Problem solving", "STRONG"), ("Data analysis", "BUILD")]


# ------------------------------------------------------------------ 4. personalization


def test_plan_evidence_links_to_competencies_only_through_taxonomy_terms():
    taxonomy = load_taxonomy()
    areas = [("Stakeholder management", "STRONG"), ("Requirements gathering", "BUILD"), ("Excel", "GOOD"), ("Cooking", "STRONG")]
    coverage = competency_coverage(
        ["stakeholder_communication", "requirements_analysis", "quantitative_reasoning", "business_judgement"], taxonomy, areas,
    )
    assert coverage == {"stakeholder_communication": "STRONG", "requirements_analysis": "BUILD", "quantitative_reasoning": "GOOD"}
    assert competency_coverage(["business_judgement"], taxonomy, []) == {}


def test_personalization_for_a_non_engineering_candidate(mapping):
    async def coverage(_role_profile_id, _user_id):
        return [("Stakeholder management", "STRONG"), ("Requirements gathering", "BUILD")]

    user = uuid4()
    w = world(coverage=coverage, stories=("Reworking a regional sales report",))
    target = consulting_target(w, user)
    detail = round_of(w, target, user, "requirements_and_stakeholders")
    ranked = [(p.competency_key, p.reason_codes) for p in detail.priorities]
    # Strong confirmed example: no "no example" reason; missing example: recommended first.
    assert ranked[0][0] == "requirements_analysis" and "NO_CONFIRMED_EXAMPLE" in ranked[0][1]
    stakeholder = dict(ranked)["stakeholder_communication"]
    assert not {"NO_CONFIRMED_EXAMPLE", "SOME_EXAMPLES", "NOT_LINKED_TO_YOUR_PLAN"} & set(stakeholder)

    case = round_of(w, target, user, "business_problem_solving")
    assert "YOUR_STORY" in {p.rationale_code for p in case.pack.prompts}  # their own story title, nothing invented
    for prompt in asyncio.run(w.service._pack(user, target, w.service._round(target, "business_problem_solving"), None, synthetic_catalog())).prompts:
        if prompt.rationale_code == "YOUR_STORY":
            assert prompt.derived_from["story_titles"] == ["Reworking a regional sales report"]


def test_a_broken_plan_source_never_breaks_priorities(mapping):
    async def coverage(_role_profile_id, _user_id):
        raise RuntimeError("plan storage down")

    w, user = world(coverage=coverage), uuid4()
    detail = round_of(w, consulting_target(w, user), user, "business_problem_solving")
    assert detail.priorities and all("NOT_LINKED_TO_YOUR_PLAN" in p.reason_codes for p in detail.priorities)


# ------------------------------------------------------------------ 5. planner


def test_priority_principle_holds_without_engineering_assumptions():
    rows = [
        CompetencyInProcess(key="structured_problem_solving", round_count=2, first_round_ordinal=1, band="HIGH"),
        CompetencyInProcess(key="stakeholder_communication", round_count=0, conditional_round_count=1, first_round_ordinal=2, band="MEDIUM"),
        CompetencyInProcess(key="business_judgement", round_count=0, first_round_ordinal=1, band=None),  # unknown: no research
    ]
    weak = prioritise(rows, {"structured_problem_solving": "BUILD"}, {}, TODAY, None)
    strong = prioritise(rows, {"structured_problem_solving": "STRONG"}, {}, TODAY, None)
    codes = {item.competency_key: item.reason_codes for item in weak}
    assert weak[0].competency_key == "structured_problem_solving"
    assert codes["stakeholder_communication"][0] == "IN_CONDITIONAL_ROUND"
    assert not any(code.startswith("IN_") for code in codes["business_judgement"])
    rank = {item.competency_key: item.rank for item in strong}
    assert rank["structured_problem_solving"] > 1 or strong[0].points < weak[0].points
    # A core round outranks a round only some processes include, all else equal.
    core = prioritise([CompetencyInProcess(key="a", round_count=1, first_round_ordinal=1, band="MEDIUM"),
                       CompetencyInProcess(key="b", round_count=0, conditional_round_count=1, first_round_ordinal=1, band="MEDIUM")],
                      {}, {}, TODAY, None)
    assert [item.competency_key for item in core] == ["a", "b"]


def test_practice_history_from_unknown_or_other_family_rounds_is_ignored():
    taxonomy = load_taxonomy()
    now = datetime(2026, 10, 6, tzinfo=UTC)
    link = lambda key: TargetSessionLink(  # noqa: E731
        session_id=uuid4(), user_id=uuid4(), candidate_target_id=uuid4(), blueprint_id=None, round_key=key,
        competency_key=None, prompt_set_id=None, created_at=now,
    )
    facts = practice_facts([link("business_problem_solving"), link("coding_reasoning"), link("unknown_round")], taxonomy.rounds(BA))
    assert set(facts) == {"structured_problem_solving", "quantitative_reasoning", "business_judgement"}
    assert all(f.count == 1 for f in facts.values())


# ------------------------------------------------------------------ 6. practice


def test_case_round_practice_gets_case_prompts_and_keeps_basis_separate_from_origin(mapping):
    w, user = world(), uuid4()
    target = consulting_target(w, user)
    started = asyncio.run(w.service.start_round_practice(target.id, "business_problem_solving", user, PracticeStart(idempotency_key=uuid4())))
    rows = sorted(w.repo.questions, key=lambda q: q.position)
    case_ids = {t.id for t in w.service._round(target, "business_problem_solving").templates}
    assert len(rows) == 4 and {r.template_id for r in rows} <= case_ids
    assert all(r.round_key == "business_problem_solving" for r in rows)
    assert all(r.provenance_class == "MIRROR_GENERATED" for r in rows)  # origin: Mirror wrote it
    assert all(r.rationale_code == "PUBLISHED_GUIDANCE_AREA" for r in rows)  # basis: exact-scope research
    assert {r.competency_key for r in rows} <= {"structured_problem_solving", "quantitative_reasoning", "business_judgement"}
    assert started.session.practice_theme == "Working through a business problem"
    assert all("text" not in p.model_dump() for p in started.prompts)

    sde_target = tech_target(w, user)
    asyncio.run(w.service.start_round_practice(sde_target.id, "coding_reasoning", user, PracticeStart(idempotency_key=uuid4())))
    sde_rows = [q for q in w.repo.questions if q.candidate_target_id == sde_target.id]
    assert {q.template_id for q in sde_rows}.isdisjoint(case_ids)


# ------------------------------------------------------------------ 7. third slice: data only


def test_third_slice_dry_run_needs_no_code_or_schema_change(monkeypatch):
    """A fictional, structurally different process (site visits, a planning exercise) as pure data."""
    import app.target_service as service_module

    raw = taxonomy_raw()
    raw["question_families"]["planning_exercise"] = {"description": "Talking through a plan with constraints and numbers."}
    raw["competencies"]["safety_judgement"] = {"evidence_terms": ["health and safety", "risk assessment"]}
    raw["competencies"]["resource_planning"] = {"evidence_terms": ["scheduling", "rostering", "resource planning"]}
    raw["companies"]["qa_logistics"] = {"aliases": ["QA Logistics Co (synthetic)"], "process_terms": []}

    def tpl(prefix, n, family, competency):
        return [{"id": f"{prefix}.{i}", "family_key": family, "competency_key": competency,
                 "fallback": f"Fictional practice prompt {prefix} number {i}: walk me through what you would check first and why it matters here."}
                for i in range(1, n + 1)]

    raw["role_families"]["field_operations_coordination"] = {
        "levels": ["coordinator", "senior_coordinator", "not_sure"],
        "rounds": [
            {"key": "site_visit_scenario", "ordinal": 1, "theme": "Handling a situation on site", "question_family": "workplace_scenario",
             "competency_keys": ["safety_judgement", "stakeholder_communication"], "claim_subjects": ["site_visit"],
             "templates": tpl("qa_site", 6, "site_situation", "safety_judgement") + tpl("qa_site_people", 6, "site_people", "stakeholder_communication")},
            {"key": "shift_planning", "ordinal": 2, "theme": "Planning shifts with limits", "question_family": "planning_exercise",
             "competency_keys": ["resource_planning", "quantitative_reasoning"], "claim_subjects": ["planning_exercise"],
             "templates": tpl("qa_plan", 6, "rostering", "resource_planning") + tpl("qa_plan_numbers", 6, "rough_numbers", "quantitative_reasoning")},
        ],
    }
    taxonomy = taxonomy_from_dict(raw)
    assert "field_operations_coordination" not in load_taxonomy().document.role_families  # not in the product data

    catalog_raw = json.loads(synthetic_catalog().document.model_dump_json(by_alias=True))
    catalog_raw["claims"] = [_claim("qa_logistics.field.coordinator.qa_land.planning", "qa_logistics",
                                    "field_operations_coordination", "coordinator", "planning_exercise")]
    catalog_raw["conflict_sets"] = []
    catalog = RepoResearchCatalog(CatalogDocument.model_validate(catalog_raw), content_sha256(b"third-slice"))
    third_mapping = {"rounds": {"shift_planning": ["qa_logistics.field.coordinator.qa_land.planning"]},
                     "round_specific_claims": [], "conditional_links": []}
    monkeypatch.setattr(service_module, "_mapping_for", lambda match: None if match.state == "NOT_RESEARCHED" else third_mapping)

    w, user = world(catalog=catalog, taxonomy=taxonomy), uuid4()
    target = make_target(w, user, company="QA Logistics Co (synthetic)", family="field_operations_coordination", level="coordinator")
    view = blueprint_of(w, target, user)
    assert view.match_state == "RESEARCHED"
    assert [(r.key, r.basis, r.question_family) for r in view.rounds] == [
        ("site_visit_scenario", "MIRROR_SUGGESTED", "workplace_scenario"),
        ("shift_planning", "PUBLISHED_GUIDANCE", "planning_exercise"),
    ]
    detail = round_of(w, target, user, "shift_planning")
    assert {p.competency_key for p in detail.priorities} == {"resource_planning", "quantitative_reasoning"}
    assert all("IN_ONE_ROUND" in p.reason_codes for p in detail.priorities)
    started = asyncio.run(w.service.start_round_practice(target.id, "shift_planning", user, PracticeStart(idempotency_key=uuid4())))
    assert started.session.practice_theme == "Planning shifts with limits"
    assert {q.template_id.split(".")[0] for q in w.repo.questions} <= {"qa_plan", "qa_plan_numbers"}


# ------------------------------------------------------------------ 8. taxonomy integrity


def test_taxonomy_is_locked_and_validated():
    taxonomy = load_taxonomy()
    lock = json.loads((ROOT / "apps/api/app/research_content/LOCK.json").read_text(encoding="utf-8"))
    assert lock["taxonomies"]["taxonomy_v1.json"]["sha256"] == taxonomy.sha256
    raw = taxonomy_raw()
    raw["role_families"][BA]["rounds"][0]["competency_keys"].append("not_a_competency")
    with pytest.raises(TaxonomyError):
        taxonomy_from_dict(raw)
    raw = taxonomy_raw()
    raw["companies"]["copycat"] = {"aliases": ["Amazon"]}
    with pytest.raises(TaxonomyError):  # one alias can never name two companies
        taxonomy_from_dict(raw)
    raw = taxonomy_raw()
    raw["role_families"][BA]["levels"].remove("not_sure")
    with pytest.raises(TaxonomyError):
        taxonomy_from_dict(raw)


def test_every_template_is_original_and_uses_mirror_words():
    from app.copy_guard import find_banned
    from app.prompt_originality import GuardContext, check_prompt, excerpts_from_catalog

    taxonomy = load_taxonomy()
    context = GuardContext(source_excerpts=excerpts_from_catalog(load_catalog()),
                           company_names=tuple(taxonomy.document.companies), recent_prompts=(), today=TODAY)
    for family in taxonomy.document.role_families:
        for round_ in taxonomy.rounds(family):
            assert len(round_.templates) >= 12, round_.key
            for template in round_.templates:
                for text in {template.fallback, template.text.replace("{story}", "Reworking a regional sales report")}:
                    assert check_prompt(text, context).ok, (template.id, check_prompt(text, context).reason)
                    assert not find_banned(text), (template.id, find_banned(text))


def test_company_process_words_are_data_and_still_guarded():
    from app.prompt_originality import GuardContext, check_prompt

    context = GuardContext(source_excerpts=(), company_names=("Deloitte",), recent_prompts=(), today=TODAY)
    assert check_prompt("Walk me through how a Deloitte Touche Tohmatsu partner would open this meeting with you.", context).reason == "COMPANY_ATTRIBUTION"
    amazon = GuardContext(source_excerpts=(), company_names=("Amazon",), recent_prompts=(), today=TODAY)
    assert check_prompt("Tell me about a time you showed one of the Leadership Principles in your project.", amazon).reason == "COMPANY_ATTRIBUTION"


def test_web_role_families_match_the_backend_taxonomy():
    text = (ROOT / "apps/web/src/lib/copy-targets.ts").read_text(encoding="utf-8")
    block = text[text.index("export const ROLE_FAMILIES"):text.index("];", text.index("export const ROLE_FAMILIES"))]
    web = dict(re.findall(r'key: "([a-z_]+)",\s*hint: .*?,\s*levels: \[([^\]]*)\]', block, re.S))
    taxonomy = load_taxonomy()
    assert set(web) == set(taxonomy.document.role_families)
    for family, levels in web.items():
        offered = re.findall(r'"([a-z_]+)"', levels)
        assert set(offered) <= set(taxonomy.levels(family)) and offered[-1] == "not_sure", family


# ------------------------------------------------------------------ 9. anti-hardcoding


PRODUCT_MODULES = (
    "target_service.py", "target_rounds.py", "target_priority.py", "target_taxonomy.py", "target_repository.py",
    "target_capability.py", "routes_targets.py", "research_catalog.py", "prompt_originality.py",
    "planner_service.py", "practice_modes.py", "plan_service.py",
)
WEB_FILES = (
    "components/plan/round-page.tsx", "components/plan/target-overview.tsx", "components/plan/target-recovery.ts",
    "components/onboarding/target-fields.tsx", "components/onboarding/role-step.tsx", "components/practice/start-practice.tsx",
    "lib/api-targets.ts", "lib/target-recovery.ts",
)


def _taxonomy_literals() -> set[str]:
    taxonomy = load_taxonomy().document
    words = set(taxonomy.companies) | set(taxonomy.role_families)
    words |= {alias.casefold() for c in taxonomy.companies.values() for alias in c.aliases}
    words |= {level for f in taxonomy.role_families.values() for level in f.levels if level != "not_sure"}
    words |= {r.key for f in taxonomy.role_families.values() for r in f.rounds}
    return words


def test_no_ordinary_company_or_role_family_branching_in_product_code():
    """Fails on `if company == "amazon"`, `role in (...)`, or any company/role/level/round literal in logic.

    Docstrings and comments may name examples; code may not. There are no justified exceptions today.
    """
    literals = _taxonomy_literals()
    offenders = []
    for name in PRODUCT_MODULES:
        path = ROOT / "apps/api/app" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                if node.value.casefold() in literals:
                    offenders.append(f"{name}:{node.lineno}: literal {node.value!r}")
            if isinstance(node, ast.Name) and re.search(r"amazon|deloitte|sde|swe|consult", node.id, re.I):
                offenders.append(f"{name}:{node.lineno}: name {node.id!r}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and re.search(r"amazon|deloitte|_sde|swe|consult", node.name, re.I):
                offenders.append(f"{name}:{node.lineno}: function {node.name!r}")
    web_src = ROOT / "apps/web/src"
    comparison = re.compile(r"""(company_key|company_label|role_family_key|level_key|roundKey|round\.key)\s*[!=]==?\s*["'`]""")
    company_word = re.compile(r"\b(amazon|deloitte)\b", re.I)
    for rel in WEB_FILES:
        path = web_src / rel
        if not path.exists():
            continue
        code = re.sub(r"//[^\n]*|/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in comparison.finditer(code):
            offenders.append(f"web {rel}: comparison {match.group(0)!r}")
        for match in company_word.finditer(code):
            offenders.append(f"web {rel}: company name {match.group(0)!r}")
        if re.search(r"looksLikeSde|\bisAmazon\b|\bamazon\s*[:=]", code):
            offenders.append(f"web {rel}: company/role helper")
    assert offenders == []


def test_the_structural_check_catches_a_branch_when_one_is_added(tmp_path):
    literals = _taxonomy_literals()
    planted = ast.parse('def plan(target):\n    if target.company_key == "amazon":\n        return 1\n')
    hits = [n.value for n in ast.walk(planted) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.casefold() in literals]
    assert hits == ["amazon"]
