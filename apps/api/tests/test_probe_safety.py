"""B12: contradiction grounding + candidate-facing probe safety (behavioural matrix)."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.claims_models import ClaimStatus, ClaimType
from app.interviewer_models import InterviewerTurnType, TurnSpeaker
from app.probe_safety import (
    is_hostile, negation_conflict, neutral_probe, question_is_safe, safe_probe_text, statements_conflict,
)
from app.schemas import Phase
from app.skeptic_models import (
    ObservationType, SkepticAnalysis, SkepticClaim, SkepticContext, SkepticTurn,
)
from app.skeptic_processor import SkepticResultProcessor

RESUME = "Led the migration of our services to Kubernetes"


# ------------------------------------------------------------------ grounding: denial/negation is not contradiction
@pytest.mark.parametrize("answer", [
    "I never used a database before, I only followed the tutorial.",
    "I didn't do any of the frontend work.",
    "I haven't worked with Terraform yet.",
    "I wasn't responsible for payroll.",
    "I don't have a team lead title.",
    "We didn't use microservices at that stage.",
    "That's not what happened with the launch, it slipped by a week.",
    "I did not say anything about caching.",
])
def test_denial_that_does_not_touch_the_claim_is_not_a_contradiction(answer):
    assert not statements_conflict(answer, RESUME, statement_is_spoken_turn=False)


@pytest.mark.parametrize("answer", [
    "I never used Kubernetes, we deployed on plain VMs.",
    "I wasn't involved in the Kubernetes migration at all.",
    "I did not lead the migration, my manager did.",
    "We didn't migrate to Kubernetes while I was there.",
])
def test_negation_about_the_same_content_is_a_grounded_conflict(answer):
    assert statements_conflict(answer, RESUME, statement_is_spoken_turn=False)


def test_compatible_statements_and_clarifications_do_not_conflict():
    assert not statements_conflict("I led the Kubernetes migration for the billing services.", RESUME, statement_is_spoken_turn=False)
    assert not statements_conflict("I mostly supported the migration, writing the Helm charts.", RESUME, statement_is_spoken_turn=False)
    # self-correction of an earlier *spoken* answer is a clarification, not a contradiction
    assert not statements_conflict("Actually, I did not lead it, I supported the migration.",
                                   "I led the migration to Kubernetes.", statement_is_spoken_turn=True)
    # the same sentence against a resume claim is still a real discrepancy
    assert statements_conflict("Actually, I did not lead the migration, I supported it.", RESUME, statement_is_spoken_turn=False)


def test_negation_meaning_is_preserved_in_both_directions():
    assert negation_conflict("I never touched the billing service", "Owned the billing service end to end")
    assert not negation_conflict("I owned the billing service end to end", "Owned the billing service end to end")


# ------------------------------------------------------------------ processor: model-asserted contradictions
def _turn(text, *, speaker=TurnSpeaker.CANDIDATE, index=3):
    return SkepticTurn(id=uuid4(), turn_index=index, speaker=speaker, text=text, turn_type=InterviewerTurnType.DEPTH_PROBE,
                       phase=Phase.PROJECTS, created_at=datetime.now(UTC))


def _claim(text):
    return SkepticClaim(id=uuid4(), claim_text=text, claim_type=ClaimType.TOOL, source="RESUME",
                        status=ClaimStatus.UNVERIFIED, confidence=.9)


def _context(answer, claim, prior=()):
    return SkepticContext(session_id=uuid4(), current_turn=_turn(answer), related_resume_claims=[claim],
                          relevant_prior_turns=list(prior), current_phase=Phase.PROJECTS)


def _accusation(context, claim, *, probe="Your answer does not match your resume; which is true?",
                reason="The candidate is lying about this.", related=None):
    turn_id = context.current_turn.id
    return SkepticAnalysis.model_validate({
        "new_claims": [], "claim_updates": [{"claim_id": str(claim.id), "proposed_status": "CONTRADICTED", "confidence": .9,
                                             "reason": "The answer conflicts with the resume claim.", "related_turn_ids": related or [str(turn_id)]}],
        "observations": [{"observation_type": "CONTRADICTION", "summary": "The candidate contradicted themselves.", "confidence": .9,
                          "source_turn_id": str(turn_id), "related_claim_ids": [str(claim.id)], "related_turn_ids": related or [str(turn_id)]}],
        "flag_proposals": [{"flag_type": "CONTRADICTION", "claim_id": str(claim.id), "severity": "HIGH", "confidence": .95,
                            "reason": reason, "suggested_probe": probe, "safe_to_surface": True,
                            "source_turn_id": str(turn_id), "related_turn_ids": related or [str(turn_id)]}],
    })


def _normalise(analysis, context):
    return SkepticResultProcessor._conservative_normalization(analysis, context)


@pytest.mark.parametrize("answer", [
    "I never used a database before, I only followed the tutorial.",
    "I haven't worked with Terraform yet.",
    "I did not say anything about caching.",
    "I led the Kubernetes migration for the billing services.",   # compatible, no negation at all
])
def test_unsupported_model_contradiction_never_survives(answer):
    claim = _claim(RESUME)
    ctx = _context(answer, claim)
    out = _normalise(_accusation(ctx, claim), ctx)
    assert all(o.observation_type != ObservationType.CONTRADICTION for o in out.observations)
    assert all(f.flag_type != ObservationType.CONTRADICTION for f in out.flag_proposals)
    assert all(u.proposed_status != ClaimStatus.CONTRADICTED for u in out.claim_updates)
    for f in out.flag_proposals:
        assert not is_hostile(f.suggested_probe + " " + f.reason)
        assert "which is true" not in f.suggested_probe.lower() and "does not match" not in f.suggested_probe.lower()
    assert not any(is_hostile(o.summary) or "contradicted" in o.summary.lower() for o in out.observations)


def test_genuine_contradiction_with_resume_survives_and_can_be_challenged():
    claim = _claim(RESUME)
    ctx = _context("I wasn't involved in the Kubernetes migration at all.", claim)
    probe = "Your resume says you led the Kubernetes migration, but here you say you weren't involved. Help me reconcile that."
    out = _normalise(_accusation(ctx, claim, probe=probe, reason="The answer conflicts with the resume claim."), ctx)
    assert out.flag_proposals[0].flag_type == ObservationType.CONTRADICTION
    assert out.flag_proposals[0].suggested_probe == probe                       # firm and grounded: survives untouched
    assert out.observations[0].observation_type == ObservationType.CONTRADICTION
    assert out.claim_updates[0].proposed_status == ClaimStatus.CONTRADICTED


def test_evidence_linked_discrepancy_between_two_candidate_turns():
    claim = _claim("Worked on backend services")
    earlier = _turn("I led the migration to Kubernetes.", index=1)
    ctx = _context("I never touched the Kubernetes migration.", claim, prior=[earlier])
    analysis = _accusation(ctx, claim, probe="Earlier you described leading the Kubernetes migration; now you describe not touching it. Help me reconcile that.",
                           related=[str(earlier.id)])
    out = _normalise(analysis, ctx)
    assert out.flag_proposals[0].flag_type == ObservationType.CONTRADICTION
    assert "Help me reconcile" in out.flag_proposals[0].suggested_probe


def test_interviewer_authored_prior_turn_cannot_ground_a_contradiction():
    claim = _claim("Worked on backend services")
    interviewer = _turn("Tell me about the Kubernetes migration you led.", speaker=TurnSpeaker.INTERVIEWER, index=1)
    ctx = _context("I never touched the Kubernetes migration.", claim, prior=[interviewer])
    out = _normalise(_accusation(ctx, claim, related=[str(interviewer.id)]), ctx)
    assert out.flag_proposals[0].flag_type != ObservationType.CONTRADICTION


def test_normalisation_is_idempotent_so_retries_cannot_reintroduce_text():
    claim = _claim(RESUME)
    ctx = _context("I never used a database before.", claim)
    once = _normalise(_accusation(ctx, claim), ctx)
    twice = _normalise(once, ctx)
    assert once == twice


# ------------------------------------------------------------------ candidate-facing text
@pytest.mark.parametrize("hostile", [
    "You're lying about this project.",
    "That's obviously false.",
    "You contradicted yourself.",
    "You clearly didn't build this.",
    "Stop making things up and be honest with me.",
    "That sounds like a fabricated claim.",
])
def test_hostile_wording_is_replaced_with_a_neutral_rigorous_question(hostile):
    safe = safe_probe_text(hostile, claim_text=RESUME, grounded_discrepancy=True)
    assert safe != hostile and not is_hostile(safe) and safe.rstrip()[-1] in ".?"
    assert "Kubernetes" in safe                                                  # keeps the interview context


@pytest.mark.parametrize("firm", [
    "What evidence supports that result?",
    "You mentioned owning the migration. What part did you personally own?",
    "Walk me through the discrepancy between those two accounts.",
    "Earlier you described leading it; here you described supporting it. Help me reconcile those.",
    "How would you know the change actually reduced latency?",
    "What would you do differently, and what was the trade-off?",
])
def test_legitimately_strong_probes_survive_unchanged(firm):
    assert safe_probe_text(firm, claim_text=RESUME, grounded_discrepancy=False) == firm
    assert question_is_safe(firm, discrepancy_grounded=False)


def test_discrepancy_assertion_requires_grounding_but_hostility_never_passes():
    assert not question_is_safe("That does not match what you said earlier.", discrepancy_grounded=False)
    assert question_is_safe("That does not match what you said earlier.", discrepancy_grounded=True)
    assert not question_is_safe("You're lying.", discrepancy_grounded=True)


def test_fallback_is_contextual_not_generic_when_a_claim_is_known():
    assert "Kubernetes" in neutral_probe(claim_text=RESUME, grounded_discrepancy=False)
    assert neutral_probe(claim_text=None, grounded_discrepancy=False).endswith("?")


# ------------------------------------------------------------------ wiring: interviewer's own wording is gated
def _decision_ctx(question, *, flag=True, flag_type="CONTRADICTION"):
    from app.agents.definitions import AgentExecutionResult
    from app.interviewer_models import (
        InterviewerAction, InterviewerContext, InterviewerObjective, InterviewerReasonCode, PendingInterviewerFlag,
    )
    from app.planner_models import DifficultyStart, ObjectivePriority
    objective = InterviewerObjective(objective_id="obj-1", phase=Phase.PROJECTS, objective="Probe ownership",
        priority=list(ObjectivePriority)[0], initial_question="Tell me about it.", question_intent="ownership",
        time_budget_seconds=120, max_probes=2, difficulty_start=list(DifficultyStart)[0])
    pending = PendingInterviewerFlag(flag_id=uuid4(), flag_type=flag_type, reason_summary="needs reconciling",
        suggested_probe="Help me reconcile that.", recommended_turn_type=InterviewerTurnType.CONTRADICTION_PROBE if flag_type == "CONTRADICTION" else InterviewerTurnType.DEPTH_PROBE,
        confidence_band="HIGH") if flag else None
    ctx = InterviewerContext(session_id=uuid4(), current_turn_index=3, phase=Phase.PROJECTS, objective=objective, recent_turns=[],
        probe_count=0, remaining_phase_time_seconds=100, remaining_time_seconds=900, pending_flag=pending)
    out = {"action": "ASK", "question_text": question, "turn_type": "DEPTH_PROBE", "target_claim_ids": [], "target_competency_ids": [],
           "primary_thread_id": "obj-1", "reason_code": "NEED_MORE_DEPTH", "requested_phase_transition": None, "used_flag_id": None}
    if flag and flag_type == "CONTRADICTION":
        out.update(turn_type="CONTRADICTION_PROBE", reason_code="SKEPTIC_FLAG_PROBE", used_flag_id=str(pending.flag_id))
    exe = AgentExecutionResult(execution_id=uuid4(), agent_name="interviewer", model="m", prompt_version="v1", success=True,
                               output=out, latency_ms=1, retry_count=0)
    return exe, ctx


@pytest.mark.parametrize("question,flag,flag_type,ok", [
    ("What evidence supports that result?", False, "VAGUENESS", True),
    ("Earlier you described leading it; here you described supporting it. Help me reconcile those.", True, "CONTRADICTION", True),
    ("You're lying about leading that migration.", True, "CONTRADICTION", False),
    ("Honestly, that doesn't match what you told me before.", False, "VAGUENESS", False),
    ("That does not match what you said earlier. Help me reconcile it?", True, "CONTRADICTION", True),
])
def test_interviewer_wording_gate_is_enforced_on_the_candidate_facing_decision(question, flag, flag_type, ok):
    from app.interviewer_service import InterviewerOutputRejected, TextInterviewService as InterviewerService
    exe, ctx = _decision_ctx(question, flag=flag, flag_type=flag_type)
    if ok:
        assert InterviewerService._validated_decision(None, exe, ctx).question_text == question
    else:
        with pytest.raises(InterviewerOutputRejected):
            InterviewerService._validated_decision(None, exe, ctx)


# ------------------------------------------------------------------ round-1 review fixes
@pytest.mark.parametrize("text", [
    "That\u2019s a lie.", "You\u2019re not telling the truth.", "Come clean.", "Stop playing games.",
    "You took credit for the migration.", "Are you inflating your role?", "I don't buy it.",
    "You\u200b'\u200bre l\u200bying.", "You\u2019re lying.", "I don\u2019t believe you.", "Y\u043eu\u2019re lying about it.",
    "\uff39\uff4f\uff55\u2019re lying",
])
def test_paraphrased_and_obfuscated_hostility_is_caught(text):
    assert is_hostile(text) and not question_is_safe(text, discrepancy_grounded=True)


@pytest.mark.parametrize("text", [
    "That doesn\u2019t match your resume.", "Now you say you didn't. Which is it?", "That differs from your resume.",
    "You said\nyou led it,\u00a0but you didn't.", "That clashes with what you told me.",
])
def test_obfuscated_discrepancy_assertions_need_grounding(text):
    assert not question_is_safe(text, discrepancy_grounded=False)
    assert question_is_safe(text, discrepancy_grounded=True) or is_hostile(text)


@pytest.mark.parametrize("answer", [
    "I actually never led the migration.", "I wasn't actually the one who led it.", "Sorry I'm late; I never led it.",
])
def test_flat_reversals_are_not_treated_as_self_correction(answer):
    assert statements_conflict(answer, "I led the migration to Kubernetes.", statement_is_spoken_turn=True)


def test_explicit_self_correction_still_counts_as_clarification():
    assert not statements_conflict("Actually, I did not lead it, I supported it.", "I led the migration.", statement_is_spoken_turn=True)
    assert not statements_conflict("To clarify, I did not lead it.", "I led the migration.", statement_is_spoken_turn=True)


def test_replacement_never_reads_banned_copy_or_markup_aloud():
    claim = "Built **test** automation and gap analysis <b>tooling</b>\u202e that improved performance by 20%"
    probe = neutral_probe(claim_text=claim, grounded_discrepancy=True)
    from app.copy_guard import find_banned
    assert find_banned(probe) == [] and "<" not in probe and "*" not in probe and "\u202e" not in probe
    clean = neutral_probe(claim_text="Built a **Flask** to-do app\u200b with SQLite", grounded_discrepancy=False)
    assert "Flask" in clean and "*" not in clean and "\u200b" not in clean


@pytest.mark.parametrize("text", [
    "Don't lie to me.", "That was a lie.", "Is that a lie?", "You are a fraud.", "Stop fibbing.",
    "Admit you didn't do it.", "That sounds fake.", "Just admit it.", "That's simply false.",
])
def test_basic_dishonesty_accusations_never_pass(text):
    assert is_hostile(text) and not question_is_safe(text, discrepancy_grounded=True)


@pytest.mark.parametrize("text", [
    "Your story keeps changing. Why?", "Those two answers can't both be true.", "Your story has shifted since earlier.",
])
def test_story_and_both_be_true_phrasing_is_a_discrepancy_assertion(text):
    assert not question_is_safe(text, discrepancy_grounded=False)


@pytest.mark.parametrize("text", [
    "Where does the risk lie in this design?", "What would you do if the story points change mid-sprint?",
    "How did you handle a fake door test?", "What's the truth about latency under load, what did you measure?",
])
def test_ordinary_interview_language_is_not_blocked_by_the_accusation_patterns(text):
    assert question_is_safe(text, discrepancy_grounded=False)
