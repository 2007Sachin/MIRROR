"""Behaviours 1-4, 6, 9, 11, 12 (+ Skeptic half of 10): Skeptic pipeline evaluated with a fake provider.

Real system under test: AgentRunner -> SkepticWorker -> SkepticContextBuilder ->
SkepticResultProcessor -> FlagEligibilityService / InterviewState (all unmodified).
"""
from __future__ import annotations

import dataclasses

import pytest

import ai_eval_checks as checks
import ai_eval_harness as h
from app.flag_activation import FlagEligibilityService
from app.agents.errors import ProviderFailureError
from app.skeptic_processor import SkepticResultProcessor
from app.state_machine import InterviewState, PendingFlag

pytestmark = pytest.mark.ai_eval

ALL = ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]


def run(cid, style="reference", *, mode="active", variant="baseline", **kw):
    cand = h.build_candidate(cid, variant)
    provider = h.ScriptedSkepticProvider([cand], style)
    return h.run_sync(h.run_candidate(cand, provider, mode=mode, **kw))


def _flag(**kw):
    kw.setdefault("consumed", False)
    return PendingFlag(severity=1, suggested_probe="p", **kw)


# -- broken doubles used as negative controls -------------------------------------------------
class NoGuardProcessor(SkepticResultProcessor):
    """Skips conservative contradiction normalisation."""

    @classmethod
    def _conservative_normalization(cls, analysis, context):  # type: ignore[override]
        return analysis


class NoRefCheckProcessor(SkepticResultProcessor):
    """Skips reference validation (accepts ids that are not in the transcript/claims)."""

    @staticmethod
    def _validate_references(analysis, context):  # type: ignore[override]
        return None


class EagerService(FlagEligibilityService):
    """Ignores same-turn delay AND shadow/active gating."""

    async def select(self, session_id, user_id, current_candidate_turn_index, **kw):
        self._enabled = self._allow_shadow = True
        return await super().select(session_id, user_id, 10**6, **kw)


class BrokenState(InterviewState):
    def eligible_flags(self, flags, *, skeptic_mode):  # type: ignore[override]
        return [f for f in flags if not f.consumed]


# ---------------------------------------------------------------- (1) bounded flag rate
def test_b1_skeptic_does_not_challenge_every_answer():
    runs = [run(cid) for cid in ALL]
    assert checks.check_flag_rate(runs) == []


def test_b1_negative_control_paranoid_skeptic_is_caught():
    runs = [run(cid, "paranoid") for cid in ALL]
    violations = checks.check_flag_rate(runs)
    assert any("exceeds" in v for v in violations)
    assert any("strong evidenced answer was flagged" in v for v in violations)


# ---------------------------------------------------------------- (2) delayed flags
@pytest.mark.parametrize("cid", ["P1", "P6"])
def test_b2_flags_are_delayed_and_only_active_probes(cid):
    selections = []
    for mode in ("active", "shadow"):
        selections += run(cid, mode=mode).selections
    assert any(s.selected_flag_id for s in selections if s.mode == "active"), "fixture must exercise probing"
    assert checks.check_delayed_flags(selections) == []
    assert not any(s.selected_flag_id for s in selections if s.mode == "shadow")


def test_b2_state_machine_gating_real():
    assert checks.check_state_machine_flag_gating(
        lambda current_turn: InterviewState(current_turn=current_turn),
        _flag) == []


def test_b2_negative_controls():
    eager_active = run("P1", service_cls=EagerService).selections
    eager_shadow = run("P1", mode="shadow", service_cls=EagerService).selections
    violations = checks.check_delayed_flags(eager_active + eager_shadow)
    assert any("selected at turn" in v for v in violations)
    assert any("mode 'shadow'" in v for v in violations)
    assert checks.check_state_machine_flag_gating(
        lambda current_turn: BrokenState(current_turn=current_turn),
        _flag)


# ---------------------------------------------------------------- (3) no unsupported criticism
@pytest.mark.parametrize("cid", ["P2", "P4", "P7"])
def test_b3_strong_answers_get_no_unsupported_criticism(cid):
    assert checks.check_no_unsupported_criticism(run(cid)) == []


@pytest.mark.parametrize("cid", ["P2", "P7"])
def test_b3_processor_guard_neutralises_an_accusing_model(cid):
    """Even if the model proposes CONTRADICTION/CONTRADICTED on a strong answer, nothing survives."""
    assert checks.check_no_unsupported_criticism(run(cid, "accuser")) == []


@pytest.mark.parametrize("cid", ["P2", "P7"])
def test_b3_negative_control_without_guard(cid):
    unguarded = run(cid, "accuser", processor_cls=NoGuardProcessor)
    assert checks.check_no_unsupported_criticism(unguarded)


# ---------------------------------------------------------------- (4) vague -> justified follow-up
@pytest.mark.parametrize("cid", ["P1", "P3"])
def test_b4_vague_answer_gets_content_tied_followup(cid):
    r = run(cid)
    assert checks.check_vague_followup_justified(r) == []
    assert any(s.selected_flag_type == "VAGUENESS" or s.selected_flag_id for s in r.selections)


@pytest.mark.parametrize("cid", ["P1", "P3"])
def test_b4_negative_control_boilerplate_followup(cid):
    violations = checks.check_vague_followup_justified(run(cid, "generic"))
    assert any("not tied" in v for v in violations)


def test_b4_negative_control_shadow_mode_never_surfaces():
    assert checks.check_vague_followup_justified(run("P3", mode="shadow"))


# ---------------------------------------------------------------- (6) references are real
@pytest.mark.parametrize("cid", ALL)
def test_b6_feedback_references_real_turns_and_claims(cid):
    r = run(cid)
    items = checks.feedback_items(r)
    assert checks.check_feedback_references(items, r.candidate) == []


def test_b6_real_processor_rejects_hallucinated_references():
    r = run("P1", "hallucinating")
    assert r.repo.failures and all(f[0] == "validation_failure" for f in r.repo.failures)
    assert checks.check_feedback_references(checks.feedback_items(r), r.candidate) == []
    assert r.flags == []


def test_b6_negative_control_without_reference_validation():
    cand = h.build_candidate("P1")
    r = h.run_sync(h.run_candidate(cand, h.ScriptedSkepticProvider([cand], "hallucinating"),
                                   processor_cls=NoRefCheckProcessor))
    assert checks.check_feedback_references(checks.feedback_items(r), cand)


def test_b6_quote_traceability_in_check_fn():
    cand = h.build_candidate("P7")
    t = cand.candidate_turns[0]
    good = {"kind": "q", "turn_ids": [t.id], "claim_ids": [], "quote": "Redis read-through cache"}
    bad = {**good, "quote": "I scaled it to ten million users"}
    assert checks.check_feedback_references([good], cand) == []
    assert checks.check_feedback_references([bad], cand)


# ---------------------------------------------------------------- (9) structured output validity
def _bad_payloads():
    flag_ok = {"flag_type": "VAGUENESS", "claim_id": None, "severity": "LOW", "confidence": 0.5,
               "reason": "reasonable reason", "suggested_probe": "probe please", "safe_to_surface": True,
               "source_turn_id": "00000000-0000-4000-8000-000000000001", "related_turn_ids": []}
    base = {"new_claims": [], "claim_updates": [], "observations": [], "flag_proposals": []}
    return {
        "not-json": "this is not json {",
        "null-content": None,
        "extra-field": {**base, "chain_of_thought": "hidden reasoning"},
        "bad-enum": {**base, "flag_proposals": [{**flag_ok, "severity": "CRITICAL"}]},
        "oversized-reason": {**base, "flag_proposals": [{**flag_ok, "reason": "x" * 5000}]},
        "too-many-flags": {**base, "flag_proposals": [flag_ok] * 31},
    }


def _outcomes_real():
    out = []
    for name, payload in _bad_payloads().items():
        cand = h.build_candidate("P7")
        cand = dataclasses.replace(cand, turns=cand.turns[:2])
        r = h.run_sync(h.run_candidate(cand, h.RawProvider(payload), mode="active"))
        execution = r.repo.analyses[0][1]
        out.append({"name": name, "success": execution.success, "error_type": execution.error_type,
                    "output": execution.output,
                    "stored": len(r.flags) + len(r.observations) + len(r.proposals)})
        assert r.worker_results[0].success is False and r.repo.failures, name
    return out


def test_b9_malformed_oversized_extra_field_outputs_rejected_with_typed_error():
    assert checks.check_structured_output_rejected(_outcomes_real()) == []


def test_b9_negative_control_lenient_validator():
    lenient = [{"name": o["name"], "success": True, "error_type": None, "output": {"x": 1}, "stored": 1}
               for o in _outcomes_real()]
    assert len(checks.check_structured_output_rejected(lenient)) >= 3 * len(lenient)


# ---------------------------------------------------------------- (10) skeptic failures degrade safely
def _degraded(provider, **runner_kw):
    cand = h.build_candidate("P7")
    cand = dataclasses.replace(cand, turns=cand.turns[:2])
    runner = h.build_runner(provider, **runner_kw)
    r = h.run_sync(h.run_candidate(cand, provider, runner=runner))
    execution = r.repo.analyses[0][1]
    state = InterviewState(current_turn=1)
    next_type = state.next_turn_type(flags=[], depth_probe_required=False, strong_answer=False,
                                     planned_questions_remaining=True, skeptic_mode="active")
    return r, {"name": type(provider).__name__, "error_type": execution.error_type,
               "content": execution.output, "stored": len(r.flags) + len(r.observations),
               "flow_advanced": next_type.value == "planned"}


def test_b10_provider_failure_is_typed_nothing_fabricated_flow_continues():
    r, outcome = _degraded(h.RaisingProvider(ProviderFailureError("boom")))
    assert r.worker_results[0].success is False and r.worker_results[0].retry_scheduled
    assert r.repo.failures == [("provider_failure", True)]
    assert checks.check_safe_degradation([outcome]) == []


def test_b10_timeout_is_typed_nothing_fabricated_flow_continues():
    r, outcome = _degraded(h.RaisingProvider(sleep=1.0), timeout_seconds=0.05)
    assert r.repo.failures and r.repo.failures[0][0] == "timeout"
    assert checks.check_safe_degradation([outcome]) == []


def test_b10_negative_control_fabricating_fallback():
    fabricated = {"name": "fallback", "error_type": None, "content": {"flag_proposals": ["invented"]},
                  "stored": 1, "flow_advanced": False}
    assert len(checks.check_safe_degradation([fabricated])) == 4


# ---------------------------------------------------------------- (11) no cross-candidate leak
MARKERS = {cid: h.load_scenarios()[cid]["marker"] for cid in ("P1", "P5", "P6", "P7")}


def _shared_runs(provider_cls):
    cands = [h.build_candidate(cid) for cid in MARKERS]
    provider = provider_cls(cands)
    repo = h.MemoryEvalRepository()
    runner = h.build_runner(provider)
    runs = [h.run_sync(h.run_candidate(c, provider, repo=repo, runner=runner)) for c in cands]
    return runs, provider


def test_b11_no_leak_between_candidates_through_shared_components():
    runs, provider = _shared_runs(h.ScriptedSkepticProvider)
    assert len(provider.requests) == sum(len(r.candidate.candidate_turns) for r in runs)
    assert checks.check_no_cross_candidate_leak(runs, provider.requests, markers=MARKERS) == []


def test_b11_negative_control_stateful_provider_leaks():
    runs, provider = _shared_runs(h.LeakyProvider)
    assert checks.check_no_cross_candidate_leak(runs, provider.requests, markers=MARKERS)


# ---------------------------------------------------------------- (12) P5 never accused
@pytest.mark.parametrize("variant", h.VARIANTS)
def test_b12_p5_never_accused_reference_model(variant):
    assert checks.check_p5_not_accused(run("P5", variant=variant)) == []


@pytest.mark.parametrize("variant", h.VARIANTS)
def test_b12_p5_guard_holds_against_accusing_model(variant):
    r = run("P5", "accuser", variant=variant)
    assert checks.check_p5_not_accused(r) == []
    assert not any(s.turn_type == "CONTRADICTION_PROBE" for s in r.selections)


def test_b12_negative_control_unguarded_processor():
    r = run("P5", "accuser", processor_cls=NoGuardProcessor)
    violations = checks.check_p5_not_accused(r)
    assert any("CONTRADICTION" in v for v in violations)
    assert any("CONTRADICTION_PROBE" in v for v in violations)


def test_b12_negative_control_accusatory_wording_detected():
    class Wording(h.ScriptedSkepticProvider):
        def _analysis(self, context, cand, turn):
            out = super()._analysis(context, cand, turn)
            out["flag_proposals"].append({
                "flag_type": "VAGUENESS", "claim_id": None, "severity": "HIGH", "confidence": 0.95,
                "reason": "The candidate is lying about the Quillon app.", "suggested_probe": "Are you sure?",
                "safe_to_surface": True, "source_turn_id": str(turn.id), "related_turn_ids": [str(turn.id)]})
            return out

    cand = h.build_candidate("P5")
    r = h.run_sync(h.run_candidate(cand, Wording([cand])))
    assert any("accusatory" in v for v in checks.check_p5_not_accused(r))


def test_b12_p5_phrase_i_never_does_not_bypass_guard():
    cand = h.build_candidate("P5")
    turns = [dataclasses.replace(t, text="I never used a database before, I only followed the tutorial.")
             if t.key == "t1" else t for t in cand.turns]
    cand = dataclasses.replace(cand, turns=turns)
    r = h.run_sync(h.run_candidate(cand, h.ScriptedSkepticProvider([cand], "accuser")))
    assert checks.check_p5_not_accused(r) == []


def test_b12_accusatory_probe_text_is_sanitised():
    class Accusing(h.ScriptedSkepticProvider):
        accuser_probe = "Your answer does not match your resume; which is true?"

    cand = h.build_candidate("P5")
    r = h.run_sync(h.run_candidate(cand, Accusing([cand], "accuser")))
    assert checks.check_p5_not_accused(r) == []
