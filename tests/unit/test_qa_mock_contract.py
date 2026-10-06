"""Drift guard for the hermetic browser-QA mock (scripts/qa/browser/mock).

The mock API answers with the JSON fixtures stored next to it. Each fixture is validated here
against the real backend pydantic model named in fixtures/contract.json, so the mock cannot
silently drift from the API the web app talks to. No network, no browser, no secrets.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "scripts" / "qa" / "browser" / "mock" / "fixtures"
CONTRACT = json.loads((FIXTURES / "contract.json").read_text(encoding="utf-8"))
ENTRIES = {name: target for name, target in CONTRACT.items() if not name.startswith("_")}


def _model(target: str):
    module, _, attr = target.partition(":")
    return getattr(importlib.import_module(module), attr)


def test_every_fixture_is_covered_by_the_contract() -> None:
    on_disk = {path.name for path in FIXTURES.glob("*.json")} - {"contract.json"}
    assert on_disk == set(ENTRIES), "add new fixtures to contract.json (and remove deleted ones)"


@pytest.mark.parametrize("name", sorted(ENTRIES))
def test_fixture_matches_backend_model(name: str) -> None:
    model = _model(ENTRIES[name])
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    model.model_validate(payload)
    # A field the backend model does not know is drift too (the models ignore extras silently).
    unknown = set(payload) - set(model.model_fields)
    assert not unknown, f"{name} has fields the backend model does not define: {sorted(unknown)}"


def test_fixtures_contain_only_obviously_fake_data() -> None:
    blob = "".join((FIXTURES / name).read_text(encoding="utf-8") for name in ENTRIES)
    assert "mirror-qa.invalid" in blob
    for forbidden in ("supabase.co", "@gmail.", "@outlook.", "sk-", "eyJ"):
        assert forbidden not in blob


def test_round_fixtures_do_not_expose_exact_prompt_text() -> None:
    for path in FIXTURES.glob("round_*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert all("text" not in prompt for prompt in payload.get("pack", {}).get("prompts", [])), path.name


def test_researched_fixtures_are_versioned_and_fully_synthetic() -> None:
    for name in ("blueprint_researched.json", "round_coding_reasoning_researched.json"):
        payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        assert payload["match_state"] == "RESEARCHED"
        assert payload["target"]["company_key"] == "qa_company"
        assert payload["target"]["geography_key"] == "qa_land"
        claims = _all_claims(payload)
        if payload.get("blueprint"):
            assert payload["claims"]
            assert {claim["version"] for claim in claims} == {payload["blueprint"]["catalog_version"]}
        else:
            assert payload["claims"] == []  # synthetic IDs have no production round mapping
            assert all(isinstance(claim.get("version"), int) and claim["version"] >= 1 for claim in claims)
        blob = json.dumps(payload).casefold()
        assert "amazon" not in blob
        assert "india" not in blob
        assert all(claim["key"].startswith("qa.synthetic.") for claim in _all_claims(payload))


def test_researched_fixture_generator_uses_no_real_catalog() -> None:
    source = (FIXTURES.parent / "make_target_fixtures.py").read_text(encoding="utf-8")
    assert "india_catalog" not in source
    assert "load_catalog" not in source


def test_scrubbed_researched_claim_text_is_explicitly_synthetic() -> None:
    import sys

    sys.path.insert(0, str(FIXTURES.parent))
    import make_target_fixtures as generator

    _, blueprint, _, _ = generator.build(
        generator.synthetic_catalogs(), "sde_ii", "synthetic-researched", synthetic_scope=True,
    )
    assert all(claim["statement"].startswith("QA fixture") for claim in blueprint["claims"])


def test_fictional_company_alias_matches_the_synthetic_catalog() -> None:
    import sys

    sys.path.insert(0, str(FIXTURES.parent))
    import make_target_fixtures as generator

    target, blueprint, _, _ = generator.build(
        generator.synthetic_catalogs(), "sde_ii", "synthetic-researched", synthetic_scope=True,
    )
    assert target["company_key"] == "qa_company"
    assert target["geography_key"] == "qa_land"
    assert blueprint["match_state"] == "RESEARCHED"
    assert blueprint["claims"] and blueprint["conflicts"]


def _all_claims(payload: dict) -> list[dict]:
    claims = list(payload["claims"])
    claims.extend(claim for conflict in payload.get("conflicts", []) for claim in conflict["claims"])
    return claims
