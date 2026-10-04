"""Versioned research catalog: repo JSON + lock file, one loader, a policy validator.

Owner decision (2026-10-04): global Amazon guidance is never shown for an India target.
Geography matching is exact; an India target with no India-scoped claims is NOT_RESEARCHED.
"""

from __future__ import annotations

import copy
import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.research_catalog import (
    CONTENT_DIR,
    CatalogError,
    content_sha256,
    load_catalog,
    parse_document,
    validate_document,
)

APPROVED_REFS = {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "V1", "V2", "V3"}
RAW_V1 = (CONTENT_DIR / "catalog_v1.json").read_bytes()
C2 = "amazon.sde.sde_ii.process_sequence"


def _doc() -> dict:
    return copy.deepcopy(json.loads(RAW_V1.decode("utf-8")))


def _codes(document: dict) -> list[str]:
    return validate_document(parse_document(json.dumps(document).encode("utf-8")))


def _claim(document: dict, claim_id: str) -> dict:
    return next(claim for claim in document["claims"] if claim["id"] == claim_id)


def test_the_repo_catalog_loads_and_seeds_only_verifier_approved_claims() -> None:
    catalog = load_catalog()

    assert catalog.version == 1
    assert {claim.verifier_ref for claim in catalog.claims} == APPROVED_REFS
    for claim in catalog.claims:
        assert claim.scope.geography == "global"
        assert claim.retrieved_at == date(2026, 10, 4)
        assert claim.published_at is None
        assert claim.provenance_class != "CANDIDATE_REPORTED"


def test_the_seeded_catalog_satisfies_research_policy() -> None:
    assert _codes(_doc()) == []


def test_browser_researched_fixture_never_rescopes_real_amazon_claims_to_india() -> None:
    fixture_path = CONTENT_DIR.parents[3] / "scripts" / "qa" / "browser" / "mock" / "fixtures" / "blueprint_researched.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    real_claim_ids = {claim["id"] for claim in _doc()["claims"]}
    assert not (real_claim_ids & {claim["key"] for claim in fixture["claims"]})
    assert fixture["target"]["company_label"] == "QA Fictional Company"
    assert fixture["target"]["company_key"] == "qa_company"
    assert fixture["target"]["geography_key"] == "qa_land"
    assert all(claim["scope"]["company"] == "qa_company" for claim in fixture["claims"])
    assert all(claim["scope"]["geography"] == "qa_land" for claim in fixture["claims"])
    assert "amazon." not in json.dumps(fixture)


def test_fact_requires_a_t1_official_supporting_source() -> None:
    document = _doc()
    for source in document["sources"]:
        if source["id"] == "amazon_jobs.sde_ii_interview_prep":
            source["tier"] = "T2_REPUTABLE"
    assert f"fact_requires_t1_official:{C2}" in _codes(document)

    document = _doc()
    for source in document["sources"]:
        if source["id"] == "amazon_jobs.sde_ii_interview_prep":
            source["official"] = False
    assert f"fact_requires_t1_official:{C2}" in _codes(document)


def test_an_undated_fact_is_retrieval_dated_unverified_and_never_high() -> None:
    document = _doc()
    _claim(document, C2)["dating"] = "PUBLISHED_DATE"
    assert f"undated_claim_must_be_retrieved_only:{C2}" in _codes(document)

    document = _doc()
    _claim(document, C2)["freshness"] = "CURRENT"
    assert f"undated_claim_freshness_unverified:{C2}" in _codes(document)

    document = _doc()
    _claim(document, C2)["confidence_band"] = "HIGH"
    assert f"unverified_freshness_band_capped:{C2}" in _codes(document)


def test_candidate_reported_is_locked_low_and_never_published_in_v1() -> None:
    document = _doc()
    claim = _claim(document, C2)
    claim["provenance_class"] = "CANDIDATE_REPORTED"
    claim["confidence_band"] = "MEDIUM"
    codes = _codes(document)
    assert f"candidate_reported_must_be_low:{C2}" in codes
    assert f"candidate_reported_not_publishable:{C2}" in codes

    claim["confidence_band"] = "LOW"
    assert f"candidate_reported_not_publishable:{C2}" in _codes(document)


def test_supported_pattern_needs_three_independent_groups() -> None:
    document = _doc()
    _claim(document, C2)["provenance_class"] = "SUPPORTED_PATTERN"
    assert f"supported_pattern_needs_3_independent:{C2}" in _codes(document)


def test_inference_needs_a_basis_and_mirror_generated_is_not_research() -> None:
    document = _doc()
    _claim(document, C2)["provenance_class"] = "INFERENCE"
    assert f"inference_needs_basis:{C2}" in _codes(document)

    document = _doc()
    _claim(document, C2)["provenance_class"] = "MIRROR_GENERATED"
    assert f"mirror_generated_not_research:{C2}" in _codes(document)


def test_every_claim_needs_known_sources_and_supporting_evidence() -> None:
    document = _doc()
    _claim(document, C2)["evidence"][0]["source_id"] = "nowhere"
    assert f"unknown_source:{C2}:nowhere" in _codes(document)

    document = _doc()
    for item in _claim(document, C2)["evidence"]:
        item["stance"] = "CONTEXT"
    assert f"no_supporting_evidence:{C2}" in _codes(document)


def test_scope_fields_are_required_and_well_formed() -> None:
    document = _doc()
    del _claim(document, C2)["scope"]["geography"]
    with pytest.raises(ValidationError):
        parse_document(json.dumps(document).encode("utf-8"))

    document = _doc()
    _claim(document, C2)["scope"]["level"] = "SDE II"
    with pytest.raises(ValidationError):
        parse_document(json.dumps(document).encode("utf-8"))


def test_conflicts_are_kept_side_by_side_and_never_merged() -> None:
    document = _doc()
    document["conflict_sets"][0]["claim_ids"] = document["conflict_sets"][0]["claim_ids"][:1]
    assert "conflict_set_needs_2_claims:amazon.sde.sde_ii.oa_section_timing" in _codes(document)

    document = _doc()
    _claim(document, C2)["conflict_set"] = "amazon.sde.sde_ii.oa_section_timing"
    assert f"conflict_membership_mismatch:{C2}" in _codes(document)

    document = _doc()
    _claim(document, C2)["conflict_set"] = "made.up"
    assert f"unknown_conflict_set:{C2}:made.up" in _codes(document)

    document = _doc()
    document["conflict_sets"][0]["merged_value"] = {"system_design_minutes": 17.5}
    with pytest.raises(ValidationError):
        parse_document(json.dumps(document).encode("utf-8"))


def test_unknowns_are_explicit() -> None:
    document = _doc()
    document["unknowns"] = []
    assert "unknowns_required" in _codes(document)

    document = _doc()
    document["unknowns"][0]["related_claim_ids"] = ["missing.claim"]
    assert "unknown_references_missing_claim:amazon.sde.india_specific_process:missing.claim" in _codes(document)


def test_a_published_catalog_has_a_receipt_and_only_published_unique_claims() -> None:
    document = _doc()
    document["verifier_receipt"] = None
    assert "published_without_verifier_receipt" in _codes(document)

    document = _doc()
    _claim(document, C2)["status"] = "DRAFT"
    assert f"unpublished_claim_in_published_catalog:{C2}" in _codes(document)

    document = _doc()
    document["claims"].append(copy.deepcopy(_claim(document, C2)))
    assert f"duplicate_claim:{C2}" in _codes(document)


def _copy_content(tmp_path: Path) -> Path:
    target = tmp_path / "content"
    shutil.copytree(CONTENT_DIR, target)
    return target


def test_the_loader_refuses_content_that_does_not_match_the_lock(tmp_path: Path) -> None:
    content = _copy_content(tmp_path)
    path = content / "catalog_v1.json"
    path.write_bytes(path.read_bytes().replace(b"four 55-minute", b"three 55-minute", 1))

    with pytest.raises(CatalogError) as error:
        load_catalog(content)
    assert "lock_mismatch:catalog_v1.json" in error.value.codes


def test_the_loader_refuses_locked_content_that_breaks_policy(tmp_path: Path) -> None:
    content = _copy_content(tmp_path)
    document = _doc()
    _claim(document, C2)["confidence_band"] = "HIGH"
    raw = json.dumps(document).encode("utf-8")
    (content / "catalog_v1.json").write_bytes(raw)
    lock = json.loads((content / "LOCK.json").read_text(encoding="utf-8"))
    lock["catalogs"]["catalog_v1.json"]["sha256"] = content_sha256(raw)
    (content / "LOCK.json").write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(CatalogError) as error:
        load_catalog(content)
    assert f"unverified_freshness_band_capped:{C2}" in error.value.codes


def test_the_lock_hash_ignores_line_ending_conversion() -> None:
    assert content_sha256(b"a\r\nb\n") == content_sha256(b"a\nb\n")
