"""Generate the Loop 2 browser-QA fixtures from the REAL backend service (memory storage).

Run from apps/api: ../../.venv/Scripts/python.exe ../../scripts/qa/browser/mock/make_target_fixtures.py
Every blueprint/round fixture is produced by app.target_service through the real routes, then
ids are replaced with fixed QA ids and catalog text (statements, notes, limits, sources) with
obviously synthetic text, so fixtures assert no real company facts. The web never renders raw
catalog text anyway (it maps claim keys to reviewed copy).
"""
from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from fastapi.testclient import TestClient  # noqa: E402

import tests.test_target_routes as tr  # noqa: E402
from app.research_catalog import load_catalog  # noqa: E402
from app.target_service import StaticCatalogProvider  # noqa: E402

OUT = ROOT / "scripts" / "qa" / "browser" / "mock" / "fixtures"
QA_USER = "00000000-0000-4000-8000-000000000001"
QA_ROLE = "00000000-0000-4000-8000-000000000002"
QA_TARGET = "00000000-0000-4000-8000-000000000301"
QA_SESSION = "00000000-0000-4000-8000-000000000101"
STORY = "QA story about a reporting tool (synthetic)"


def world(catalogs):
    from types import SimpleNamespace

    from app.interview_engine import InterviewStateMachine
    from app.repository import MemorySessionRepository

    repo = tr.SpyRepository()
    sessions = MemorySessionRepository()
    engine = InterviewStateMachine(sessions, total_time_budget_seconds=1200, phase_time_budget_seconds=180)
    return SimpleNamespace(
        repo=repo, sessions=sessions, engine=engine, capability=tr.FixedCapability(),
        catalogs=StaticCatalogProvider(catalogs), stories=tr.FakeStories((STORY,)), progress=tr.FakeProgress(),
    )


def scrub(value, ids, synthetic_scope=False):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "created_at":
                out[key] = "2026-10-04T00:00:00Z"
            elif synthetic_scope and key == "key" and isinstance(item, str) and item.startswith("amazon."):
                out[key] = "qa.synthetic.claim_" + hashlib.sha256(item.encode("utf-8")).hexdigest()[:12]
            elif synthetic_scope and key == "catalog_sha256":
                out[key] = hashlib.sha256(b"mirror-loop2-qa-synthetic-catalog-v1").hexdigest()
            elif synthetic_scope and key == "company_label":
                out[key] = "QA Fictional Company"
            elif synthetic_scope and key == "company_key":
                out[key] = "qa_company"
            elif synthetic_scope and key == "geography_key":
                out[key] = "qa_land"
            elif synthetic_scope and key == "geography_label":
                out[key] = "QA Fictional Country"
            elif synthetic_scope and key == "company" and item == "amazon":
                out[key] = "qa_company"
            elif synthetic_scope and key == "geography" and item == "in":
                out[key] = "qa_land"
            elif key in ("statement",):
                out[key] = "QA fixture statement (synthetic; the web shows reviewed copy for this key instead)."
            elif key == "note":
                out[key] = "QA fixture note (synthetic)."
            elif key == "limits":
                out[key] = ["QA fixture limit (synthetic)."]
            elif key == "sources":
                out[key] = [
                    {**s, "publisher": "QA fixture publisher", "url": f"https://qa-fixture.invalid/source-{i + 1}"}
                    for i, s in enumerate(item)
                ]
            else:
                out[key] = scrub(item, ids, synthetic_scope)
        return out
    if isinstance(value, list):
        return [scrub(item, ids, synthetic_scope) for item in value]
    if isinstance(value, str):
        if synthetic_scope and value.startswith("amazon."):
            return "qa.synthetic.claim_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        for real, fake in ids.items():
            value = value.replace(real, fake)
        return value
    return value


def build(catalogs, level, label, synthetic_scope=False):
    w = world(catalogs)
    c = tr.client(w)
    created = tr.create(c, level=level).json()
    target = created["target"]
    ids = {target["id"]: QA_TARGET, str(tr.ROLE_A): QA_ROLE, str(tr.USER_A): QA_USER}
    blueprint = c.get(f"/api/v1/targets/{target['id']}/blueprint", headers=tr.A).json()
    rounds = {key: c.get(f"/api/v1/targets/{target['id']}/rounds/{key}", headers=tr.A).json()
              for key in ("coding_reasoning", "system_design", "behavioural")}
    started = tr.start(c, target["id"], round_key="coding_reasoning").json()
    ids[started["session"]["id"]] = QA_SESSION
    ids[started["link"]["prompt_set_id"]] = "00000000-0000-4000-8000-000000000401"
    if started["link"].get("blueprint_id"):
        ids[started["link"]["blueprint_id"]] = "00000000-0000-4000-8000-000000000501"
    return (scrub(target, ids, synthetic_scope), scrub(blueprint, ids, synthetic_scope),
            {k: scrub(v, ids, synthetic_scope) for k, v in rounds.items()}, scrub(started["link"], ids, synthetic_scope))


def write(name, payload):
    (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", name)


def main():
    target, not_researched, rounds_nr, link = build({1: load_catalog()}, "not_sure", "india-not-researched")
    assert not_researched["match_state"] == "NOT_RESEARCHED" and not not_researched["claims"]
    write("target.json", target)
    write("blueprint_not_researched.json", not_researched)
    for key, detail in rounds_nr.items():
        write(f"round_{key}.json", detail)
    write("round_practice_link.json", link)

    _, researched, rounds_r, _ = build({1: load_catalog(), 2: tr.india_catalog(2)}, "sde_ii", "synthetic-researched", synthetic_scope=True)
    assert researched["match_state"] == "RESEARCHED" and researched["claims"] and researched["conflicts"]
    write("blueprint_researched.json", researched)
    write("round_coding_reasoning_researched.json", rounds_r["coding_reasoning"])

    write("plan.json", {
        "role": {"role_profile_id": QA_ROLE, "target_role": "QA Analyst (test role)"},
        "state": "READY",
        "areas": [
            {"key": "qa_area_reporting", "title": "Explaining a reporting tool", "theme": "Reporting tools",
             "from_job_description": True, "why": "QA fixture excerpt (synthetic).", "status": "GOOD",
             "have": [], "suggested": [], "strengthen": "Say what changed because of your work.", "primary_action": "PRACTICE"},
            {"key": "qa_area_data", "title": "Working with data models", "theme": "Data models",
             "from_job_description": False, "why": None, "status": "BUILD",
             "have": [], "suggested": [], "strengthen": "Add one example from your work.", "primary_action": "ADD_EXAMPLE"},
        ],
        "recommended_area_key": "qa_area_reporting",
    })
    write("role_analysis.json", {
        "id": "00000000-0000-4000-8000-000000000004", "user_id": QA_USER,
        "target_role": "Software Development Engineer (test role)", "canonical_role": None, "seniority": None,
        "source_type": "SYNTHETIC_CANONICAL", "source_document_id": None, "current_analysis_version_id": "00000000-0000-4000-8000-000000000601",
        "created_at": "2026-10-04T00:00:00Z", "updated_at": "2026-10-04T00:00:00Z",
        "latest_analysis": {
            "id": "00000000-0000-4000-8000-000000000601", "role_profile_id": "00000000-0000-4000-8000-000000000004",
            "user_id": QA_USER, "version": 1, "status": "COMPLETED", "source_type": "SYNTHETIC_CANONICAL",
            "source_document_id": None, "model": "qa-fixture", "prompt_version": "qa", "analysis_version": "qa",
            "output": None, "execution_id": None, "error_type": None,
            "created_at": "2026-10-04T00:00:00Z", "completed_at": "2026-10-04T00:00:01Z",
        },
        "competencies": [],
    })
    write("interview_map.json", {
        "role_profile_id": "00000000-0000-4000-8000-000000000004", "target_role": "Software Development Engineer (test role)",
        "state": "READY", "experience_state": "READY", "role_from_job_description": False,
        "themes": [], "preparation_areas": [
            {"key": "qa_prep_one", "title": "Talking through a coding approach", "body": "QA fixture area (synthetic).",
             "action": "PRACTICE", "theme_key": None, "focus": "role"},
        ], "questions": [], "also_expected": [],
    })
    write("career_evidence.json", {"state": "READY", "items": []})


if __name__ == "__main__":
    main()
