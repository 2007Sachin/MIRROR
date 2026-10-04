"""Suite hygiene: persona coverage, variant determinism, live gating, no-network rail."""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

import ai_eval_harness as h

pytestmark = pytest.mark.ai_eval
MANIFEST = Path(__file__).resolve().parents[2] / "packages" / "evaluation" / "personas.json"


def test_every_manifest_persona_has_a_fixture_and_all_variants_build():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scenarios = h.load_scenarios()
    assert [p["id"] for p in manifest["personas"]] == sorted(scenarios)
    assert tuple(manifest["variants_per_persona"]) == h.VARIANTS
    for pid in scenarios:
        for variant in h.VARIANTS:
            cand = h.build_candidate(pid, variant)
            assert cand.candidate_turns and all(t.text for t in cand.candidate_turns)


def test_variants_are_deterministic_and_markers_survive():
    for pid, raw in h.load_scenarios().items():
        for variant in h.VARIANTS:
            a, b = h.build_candidate(pid, variant), h.build_candidate(pid, variant)
            assert [t.text for t in a.turns] == [t.text for t in b.turns]
            assert [t.id for t in a.turns] == [t.id for t in b.turns]
    assert h.apply_variant("Hello, World. Second.", "short-answer") == "Hello, World."


def test_live_scaffold_is_gated_on_both_flag_and_key():
    import importlib.util

    path = Path(__file__).parent / "live" / "test_eval_live_skeptic.py"
    spec = importlib.util.spec_from_file_location("live_gate_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    on = {"MIRROR_LIVE_EVAL": "1", "SARVAM_API_KEY": "k", "MIRROR_LIVE_MODEL": "m"}
    assert mod.live_enabled(on)
    for drop in on:
        assert not mod.live_enabled({k: v for k, v in on.items() if k != drop})
    assert not mod.live_enabled({**on, "MIRROR_LIVE_EVAL": "0"})


def test_network_rail_blocks_non_loopback_connect():
    sock = socket.socket()
    try:
        with pytest.raises(AssertionError, match="must not use the network"):
            sock.connect(("203.0.113.9", 443))
    finally:
        sock.close()
