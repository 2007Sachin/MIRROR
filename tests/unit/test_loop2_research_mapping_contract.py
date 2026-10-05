"""Research claims link to practice rounds only through an explicit versioned map."""
from __future__ import annotations

import json
from pathlib import Path

from app.research_catalog import load_catalog

ROOT = Path(__file__).resolve().parents[2]
MAPPING = ROOT / "apps/api/app/research_content/round_mapping_v1.json"


def test_versioned_round_mapping_is_complete_and_covers_only_reviewed_links() -> None:
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    catalog = load_catalog()
    assert mapping["catalog_version"] == catalog.version
    assert mapping["overview_only_claim_ids"]
    linked = {claim_id for ids in mapping["rounds"].values() for claim_id in ids}
    derivatives = {
        item["claim_id"]
        for item in mapping.get("round_specific_claims", [])
    }
    overview = set(mapping["overview_only_claim_ids"])
    process_claims = {c.id for c in catalog.claims if c.process_content and c.candidate_visible}
    assert linked.isdisjoint(overview | derivatives)
    assert linked | overview == process_claims
    assert derivatives <= overview
    assert derivatives == {"amazon.sde.sde_ii.process_sequence"}
    assert {"amazon.all.process_differs_by_role", "amazon.sde.sde_iii.process_sequence"} <= overview
    assert "amazon.sde.sde_ii.process_sequence" in overview
    c2 = next(item for item in mapping["round_specific_claims"] if item["claim_id"] == "amazon.sde.sde_ii.process_sequence")
    assert c2["round_key"] == "system_design"
    assert c2["copy_key"] == "amazon.sde.sde_ii.system_design_expectation"
    assert "amazon.sde.sde_ii.process_sequence" not in mapping["rounds"]["system_design"]
    assert "amazon.sde.sde_ii.oa_required" not in linked
    assert "amazon.sde.sde_ii.oa_required" in overview
    assert "amazon.sde.sde_ii.coding_expectations" in mapping["rounds"]["coding_reasoning"]
    assert "amazon.sde.sde_iii.coding_expectations" in mapping["rounds"]["coding_reasoning"]
    assert "amazon.sde.sde_ii.oa_components" in mapping["rounds"]["coding_reasoning"]
    assert "amazon.sde.sde_ii.oa_components" in mapping["rounds"]["system_design"]
    assert "amazon.sde.university.online_assessment" not in mapping["rounds"]["coding_reasoning"]
    assert "amazon.sde.sde_ii.coding_expectations" not in mapping["rounds"]["system_design"]
    assert "amazon.sde.sde_iii.coding_expectations" not in mapping["rounds"]["system_design"]
    assert "amazon.sde.all.interview_topics" in mapping["rounds"]["system_design"]
    assert "amazon.sde.sde_ii.process_sequence" not in mapping["rounds"]["system_design"]
    assert "amazon.sde.university.online_assessment" not in mapping["rounds"]["system_design"]
    assert "amazon.sde.sde_ii.oa_section_timing.oa_prep_page" in mapping["rounds"]["system_design"]
    assert "amazon.sde.sde_ii.oa_section_timing.interview_prep_page" in mapping["rounds"]["system_design"]
    assert "amazon.sde.sde_ii.oa_section_timing.oa_prep_page" not in mapping["rounds"]["coding_reasoning"]
    assert "amazon.sde.sde_ii.oa_required" not in mapping["rounds"]["system_design"]
    assert "amazon.sde.university.online_assessment" in overview

    assert "amazon.sde.sde_iii.loop_behavioural_questions" in mapping["rounds"]["behavioural"]


def test_mapping_lock_hash_and_catalog_version_match() -> None:
    import hashlib

    lock = json.loads((MAPPING.parent / "LOCK.json").read_text(encoding="utf-8"))
    raw = MAPPING.read_bytes().replace(b"\r\n", b"\n")
    entry = lock["round_mappings"][MAPPING.name]
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
    assert json.loads(raw)["catalog_version"] == entry["catalog_version"]
