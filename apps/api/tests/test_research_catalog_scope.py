"""Exact scope matching and immutable catalog history.

Owner decision (2026-10-04): global (non-India) guidance must never be shown for an India
target. Geography is matched exactly; "global" is a literal geography, not a wildcard.
"""

from __future__ import annotations

import copy
import json

import pytest

from app.research_catalog import (
    CONTENT_DIR,
    TargetScope,
    load_catalog,
    match_scope,
    parse_document,
    validate_history,
)

RAW_V1 = (CONTENT_DIR / "catalog_v1.json").read_bytes()
C2 = "amazon.sde.sde_ii.process_sequence"
TIMING = "amazon.sde.sde_ii.oa_section_timing"
SDE = "software_development_engineering"


def _target(level: str | None, geography: str | None, company: str = "amazon") -> TargetScope:
    return TargetScope(company=company, role_family=SDE, level=level, geography=geography)


@pytest.mark.parametrize("level", ["sde_i", "sde_ii", "sde_iii", "university", None])
def test_an_india_target_never_receives_global_guidance(level: str | None) -> None:
    match = match_scope(load_catalog(), _target(level, "in"))

    assert match.state == "NOT_RESEARCHED"
    assert match.claims == ()
    assert match.conflict_sets == ()
    assert "amazon.sde.india_specific_process" in {unknown.key for unknown in match.unknowns}
    assert all(unknown.scope.geography == "in" for unknown in match.unknowns)


def test_a_global_sde_ii_target_gets_its_level_and_general_claims_only() -> None:
    catalog = load_catalog()
    match = match_scope(catalog, _target("sde_ii", "global"))

    ids = {claim.id for claim in match.claims}
    assert match.state == "RESEARCHED"
    assert C2 in ids
    assert "amazon.all.process_differs_by_role" in ids
    assert "amazon.sde.all.interview_topics" in ids
    assert not any(claim.scope.level in {"sde_iii", "university"} for claim in match.claims)
    assert "amazon.sde.all.india_listings_observed" not in ids  # provenance only, never shown
    assert (match.catalog_version, match.content_sha256) == (catalog.version, catalog.content_sha256)


def test_conflicting_claims_are_returned_together_and_never_merged() -> None:
    match = match_scope(load_catalog(), _target("sde_ii", "global"))

    (conflict,) = match.conflict_sets
    assert conflict.key == TIMING
    members = [claim for claim in match.claims if claim.conflict_set == TIMING]
    assert {claim.id for claim in members} == set(conflict.claim_ids)
    assert {json.dumps(claim.value, sort_keys=True) for claim in members} == {
        '{"system_design_minutes": 20, "work_style_minutes": 8}',
        '{"system_design_minutes_approx": 15, "work_style_minutes_approx": 10}',
    }


def test_levels_never_widen() -> None:
    catalog = load_catalog()
    sde_iii = {claim.scope.level for claim in match_scope(catalog, _target("sde_iii", "global")).claims}
    assert sde_iii <= {"sde_iii", "all"}

    sde_i = match_scope(catalog, _target("sde_i", "global"))
    assert sde_i.state == "GENERAL_ONLY"
    assert {claim.scope.level for claim in sde_i.claims} == {"all"}
    assert "amazon.sde.sde_i.experienced_process" in {unknown.key for unknown in sde_i.unknowns}

    not_sure = match_scope(catalog, _target(None, "global"))
    assert not_sure.state == "GENERAL_ONLY"
    assert {claim.scope.level for claim in not_sure.claims} == {"all"}


def test_unspecified_geography_or_unknown_company_is_not_researched() -> None:
    catalog = load_catalog()
    assert match_scope(catalog, _target("sde_ii", None)).state == "NOT_RESEARCHED"
    assert match_scope(catalog, _target("sde_ii", None)).claims == ()
    other = match_scope(catalog, _target("sde_ii", "global", company="google"))
    assert (other.state, other.claims, other.unknowns) == ("NOT_RESEARCHED", (), ())


def test_target_scope_keys_must_be_normalised() -> None:
    with pytest.raises(ValueError):
        TargetScope(company="amazon", role_family=SDE, level="sde_ii", geography="IN")


# ------------------------------------------------------------------ immutable history


def _v1() -> dict:
    return json.loads(RAW_V1.decode("utf-8"))


def _v2_from(v1: dict) -> dict:
    v2 = copy.deepcopy(v1)
    v2["version"] = 2
    v2["supersedes_version"] = 1
    return v2


def _history(*documents: dict) -> list[str]:
    return validate_history([parse_document(json.dumps(d).encode("utf-8")) for d in documents])


def _claim(document: dict, claim_id: str) -> dict:
    return next(claim for claim in document["claims"] if claim["id"] == claim_id)


def test_an_unchanged_next_version_is_valid_history() -> None:
    v1 = _v1()
    assert _history(v1, _v2_from(v1)) == []


def test_a_published_claim_cannot_change_in_place() -> None:
    v1 = _v1()
    v2 = _v2_from(v1)
    _claim(v2, C2)["statement"] = "Amazon always runs four interviews."
    assert f"published_claim_mutated:{C2}@1" in _history(v1, v2)


def test_a_change_creates_a_new_claim_version_that_supersedes_the_old() -> None:
    v1 = _v1()
    v2 = _v2_from(v1)
    claim = _claim(v2, C2)
    claim["statement"] = "Amazon's published SDE II guidance (re-checked) describes four interviews."
    claim["version"] = 2
    claim["supersedes"] = 1
    assert _history(v1, v2) == []

    claim["supersedes"] = None
    assert f"claim_version_must_supersede_previous:{C2}@2" in _history(v1, v2)


def test_catalog_versions_are_contiguous_and_chained() -> None:
    v1 = _v1()
    v2 = _v2_from(v1)
    v2["supersedes_version"] = None
    assert "catalog_version_must_supersede_previous:2" in _history(v1, v2)

    v3 = _v2_from(v1)
    v3["version"] = 3
    v3["supersedes_version"] = 2
    assert "catalog_versions_not_contiguous" in _history(v1, v3)


def test_the_published_v1_file_is_frozen() -> None:
    # Double entry with LOCK.json: editing v1 needs a new catalog version, never a new hash here.
    lock = json.loads((CONTENT_DIR / "LOCK.json").read_text(encoding="utf-8"))
    assert lock["catalogs"]["catalog_v1.json"]["sha256"] == V1_SHA256


V1_SHA256 = "21a4c5d7fa3cdddc1fbe51b78d296cd21cffd19a450a6a5cb9c6f8926fd76391"
