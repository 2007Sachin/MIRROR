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
