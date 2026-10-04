"""Reusable behavioural check functions. Each returns a list of violation strings ([] == pass).

A check never touches production code; it only inspects artefacts produced by a run.
Tests pair real-system contracts with deliberately broken negative controls. Real
contract defects remain visible as strict known-gap xfails, not passing controls.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from uuid import UUID

CRITICISM_TYPES = {"CONTRADICTION", "OWNERSHIP_DRIFT", "UNSUPPORTED_SCALE"}
CRITICISM_STATUSES = {"CONTRADICTED", "WALKED_BACK"}
ACCUSATION_WORDS = re.compile(
    r"\b(lying|lied|liar|dishonest|fabricat\w*|untruthful|misrepresent\w*|exaggerat\w*|mislead\w*|"
    r"false claim)\b", re.I)
ACCUSATORY_PROBE = re.compile(
    r"does(?:n't| not) match|which is (?:true|correct)|are you sure|conflicts? with your resume|"
    r"you (?:said|claimed) .* but", re.I)
_STOP = {
    "answer", "could", "more", "detail", "details", "please", "elaborate", "candidate", "about",
    "with", "that", "this", "from", "have", "were", "what", "your", "their", "there", "which",
    "specifics", "prove", "verifiable", "lacks", "does", "name", "names", "states", "stated",
    "without", "claim", "resume", "says", "gives", "give", "example", "personally", "tell",
}
_TOKEN = re.compile(r"[a-z0-9+#]{4,}")


def _val(x):
    return getattr(x, "value", x)


def tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.casefold()) if t not in _STOP}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


# ----------------------------------------------------------------- (1)
def check_flag_rate(runs: Iterable, *, max_rate: float = 0.5) -> list[str]:
    """Skeptic must not challenge every answer; strong evidenced answers raise no flag."""
    runs = list(runs)
    turns = flagged = 0
    out: list[str] = []
    for run in runs:
        for turn in run.candidate.candidate_turns:
            turns += 1
            here = [f for f in run.flags if f["turn_index"] == turn.index]
            flagged += bool(here)
            if here and turn.category == "strong":
                out.append(f"{run.candidate.cid}/{turn.key}: strong evidenced answer was flagged "
                           f"({[_val(f['proposal'].flag_type) for f in here]})")
    if turns == 0:
        out.append("no candidate turns evaluated")
    elif flagged / turns > max_rate:
        out.append(f"flag rate {flagged}/{turns}={flagged / turns:.2f} exceeds {max_rate}")
    return out


# ----------------------------------------------------------------- (2)
def check_delayed_flags(selections: Iterable) -> list[str]:
    """A flag detected at turn N is never selected at turn N; only 'active' mode selects."""
    out: list[str] = []
    for s in selections:
        if s.selected_flag_id is None:
            continue
        if s.mode != "active":
            out.append(f"{s.candidate}/{s.turn_key}: mode {s.mode!r} selected a flag for probing")
        if s.selected_detected_at is not None and s.selected_detected_at >= s.evaluated_at:
            out.append(f"{s.candidate}/{s.turn_key}: flag detected at turn {s.selected_detected_at} "
                       f"selected at turn {s.evaluated_at}")
    return out


def check_state_machine_flag_gating(state_factory, flag_factory) -> list[str]:
    """InterviewState.eligible_flags: not same-turn, not consumed, only skeptic_mode == 'active'."""
    out: list[str] = []
    state = state_factory(current_turn=5)
    same_turn = flag_factory(id="same", detected_at_turn=5)
    earlier = flag_factory(id="earlier", detected_at_turn=4)
    consumed = flag_factory(id="used", detected_at_turn=1, consumed=True)
    flags = [same_turn, earlier, consumed]
    ids = {f.id for f in state.eligible_flags(flags, skeptic_mode="active")}
    if "same" in ids:
        out.append("same-turn flag eligible")
    if "used" in ids:
        out.append("consumed flag eligible")
    if "earlier" not in ids:
        out.append("earlier unconsumed flag not eligible in active mode")
    for mode in ("shadow", "off", ""):
        if state.eligible_flags(flags, skeptic_mode=mode):
            out.append(f"skeptic_mode {mode!r} produced eligible flags")
    return out


# ----------------------------------------------------------------- (3)
def check_no_unsupported_criticism(run, *, strong_only: bool = True) -> list[str]:
    """Strong answers get no contradiction / ownership / scale criticism or CONTRADICTED updates."""
    strong = {t.id: t for t in run.candidate.candidate_turns if (t.category == "strong" or not strong_only)}
    out: list[str] = []
    for row in run.flags:
        p = row["proposal"]
        if p.source_turn_id in strong and _val(p.flag_type) in CRITICISM_TYPES:
            out.append(f"flag {_val(p.flag_type)} on strong turn {strong[p.source_turn_id].key}")
    for o in run.observations:
        if o.source_turn_id in strong and _val(o.observation_type) in CRITICISM_TYPES:
            out.append(f"observation {_val(o.observation_type)} on strong turn {strong[o.source_turn_id].key}")
    for u in run.proposals:
        if any(t in strong for t in u.related_turn_ids) and _val(u.proposed_status) in CRITICISM_STATUSES:
            out.append(f"claim update {_val(u.proposed_status)} citing strong turn")
    return out


# ----------------------------------------------------------------- (4)
def check_vague_followup_justified(run, *, min_confidence: float = 0.8) -> list[str]:
    """Each vague answer yields a surfaceable flag whose reason AND probe are tied to its content."""
    out: list[str] = []
    claim_text = {c["id"]: c["text"] for c in run.candidate.claims.values()}
    vague = [t for t in run.candidate.candidate_turns if t.category == "vague"]
    if not vague:
        return ["fixture has no vague turns"]
    for turn in vague:
        mine = [r for r in run.flags if r["turn_index"] == turn.index]
        surfaceable = [r for r in mine if r["proposal"].confidence >= min_confidence
                       and r["proposal"].safe_to_surface and (run.mode == "active" and not r["shadow_mode"])]
        if not surfaceable:
            out.append(f"{run.candidate.cid}/{turn.key}: vague answer produced no surfaceable flag")
            continue
        for r in surfaceable:
            p = r["proposal"]
            context = tokens(turn.text) | tokens(claim_text.get(p.claim_id, ""))
            if not (tokens(p.reason) & context):
                out.append(f"{run.candidate.cid}/{turn.key}: reason not tied to answer/claim content: {p.reason!r}")
            if not (tokens(p.suggested_probe) & context):
                out.append(f"{run.candidate.cid}/{turn.key}: probe not tied to content: {p.suggested_probe!r}")
    for s in run.selections:
        if s.selected_flag_type == "VAGUENESS" and s.turn_type != "DEPTH_PROBE":
            out.append(f"vagueness flag mapped to {s.turn_type}, expected DEPTH_PROBE")
    return out


# ----------------------------------------------------------------- (5)
def check_no_invented_evidence(assessments: Iterable, transcript: dict[UUID, str]) -> list[str]:
    """Every cited turn id exists and every quoted span occurs in that turn's text."""
    out: list[str] = []
    for item in assessments:
        result = item.result_json if hasattr(item, "result_json") else item
        cites = list(result.evidence_quotes)
        for d in [*result.dimensions, *result.competency_or_domain_assessments]:
            cites.extend(d.evidence_quotes)
        declared_ids = list(result.evidence_turn_ids)
        for d in [*result.dimensions, *result.competency_or_domain_assessments]:
            declared_ids.extend(d.evidence_turn_ids)
        for turn_id in declared_ids:
            if turn_id not in transcript:
                out.append(f"{_val(result.assessor_type)}: evidence turn {turn_id} not in transcript")
        for c in cites:
            text = transcript.get(c.turn_id)
            if text is None:
                out.append(f"{_val(result.assessor_type)}: quote cites unknown turn {c.turn_id}")
            elif _norm(c.quote) not in _norm(text):
                out.append(f"{_val(result.assessor_type)}: quote {c.quote!r} not found in its turn")
    return out


def check_no_numeric_publish_without_evidence(bundle, aggregated, *, wide_range: int = 30,
                                              transcript: dict[UUID, str] | None = None) -> list[str]:
    """Only COMPLETE specialists with transcript-validated IDs/spans support publishing.

    Legacy calls remain accepted, but absent transcript cannot prove evidence support.
    """
    rows = [bundle.technical, bundle.behaviour, bundle.claims]
    evidenced = [r for r in rows if r is not None
                 and _val(r.result_json.status) == "COMPLETE"
                 and r.result_json.evidence_turn_ids
                 and transcript is not None
                 and not check_no_invented_evidence([r], transcript)]
    out: list[str] = []
    if evidenced:
        return out
    if aggregated.availability_status != "LIMITED_SIGNAL":
        out.append(f"availability_status={aggregated.availability_status} with zero evidence")
    if aggregated.overall_signal_confidence != 0:
        out.append(f"signal confidence {aggregated.overall_signal_confidence} with zero evidence")
    for name in ("role_readiness", "interview_readiness"):
        width = getattr(aggregated, f"{name}_high") - getattr(aggregated, f"{name}_low")
        if width < wide_range:
            out.append(f"{name} range width {width} < {wide_range} with zero evidence")
    if _val(aggregated.verdict_code) not in {"NOT_READY_YET"}:
        out.append(f"verdict {_val(aggregated.verdict_code)} published with zero evidence")
    return out


# ----------------------------------------------------------------- (6)
def feedback_items(run) -> list[dict]:
    items: list[dict] = []
    for r in run.flags:
        p = r["proposal"]
        items.append({"kind": "flag", "turn_ids": [p.source_turn_id, *p.related_turn_ids],
                      "claim_ids": [p.claim_id] if p.claim_id else [], "quote": None})
    for o in run.observations:
        items.append({"kind": "observation", "turn_ids": [o.source_turn_id, *o.related_turn_ids],
                      "claim_ids": list(o.related_claim_ids), "quote": None})
    for u in run.proposals:
        items.append({"kind": "claim_update", "turn_ids": list(u.related_turn_ids),
                      "claim_ids": [u.claim_id], "quote": None})
    return items


def check_feedback_references(items: Iterable[dict], candidate) -> list[str]:
    """Feedback/recommendations only reference turns, claims and quotes that exist in the fixture."""
    turns = candidate.transcript_text()
    claims = {c["id"] for c in candidate.claims.values()}
    out: list[str] = []
    for item in items:
        for t in item.get("turn_ids", []):
            if t not in turns:
                out.append(f"{item['kind']}: unknown turn {t}")
        for c in item.get("claim_ids", []):
            if c not in claims:
                out.append(f"{item['kind']}: unknown claim {c}")
        quote = item.get("quote")
        if quote:
            text = turns.get(item["turn_ids"][0], "") if item.get("turn_ids") else ""
            if _norm(quote) not in _norm(text):
                out.append(f"{item['kind']}: quote {quote!r} not in cited turn")
    return out


# ----------------------------------------------------------------- (7)
def check_adjudication(*, detector, bundle, snapshot_before: dict, bundle_after, calls_to_model_in_detect: int,
                       records: Iterable, expect_disagreement: bool) -> list[str]:
    out: list[str] = []
    first = [d.model_dump() for d in detector.detect(bundle)]
    second = [d.model_dump() for d in detector.detect(bundle)]
    if first != second:
        out.append("disagreement detection is not deterministic")
    if bool(first) != expect_disagreement:
        out.append(f"expected disagreement={expect_disagreement}, detected {len(first)}")
    if calls_to_model_in_detect:
        out.append("detector invoked the model")
    if bundle_after.model_dump() != snapshot_before:
        out.append("specialist outputs were mutated by adjudication")
    positions = {d["affected_dimension"]: d["specialist_positions"] for d in first}
    for rec in records:
        decision = rec.final_decision
        if not expect_disagreement:
            out.append("adjudication stored although specialists agree")
        elif decision.affected_dimension not in positions:
            out.append(f"decision for undetected dimension {decision.affected_dimension}")
        elif decision.specialist_positions != positions[decision.affected_dimension]:
            out.append("decision altered the specialists' recorded positions")
    return out


# ----------------------------------------------------------------- (8)
def check_plan_constraints(plan, planner_input, phase_order, *, max_probes: int = 2, ordered=None) -> list[str]:
    """`ordered` = objectives in the order the interviewer will consume them (defaults to stored order)."""
    out: list[str] = []
    order = {str(_val(p)): i for i, p in enumerate(phase_order)}
    total = sum(o.time_budget_seconds for o in plan.objectives)
    if total > planner_input.interview_duration_seconds:
        out.append(f"objective time {total}s exceeds budget {planner_input.interview_duration_seconds}s")
    if plan.coverage_summary.estimated_duration_seconds > planner_input.interview_duration_seconds:
        out.append("estimated duration exceeds budget")
    last = -1
    for o in (ordered if ordered is not None else plan.objectives):
        phase = str(_val(o.phase))
        if phase == "COMPLETE":
            out.append(f"{o.objective_id}: COMPLETE-phase objective")
        idx = order.get(phase, -1)
        if idx < last:
            out.append(f"{o.objective_id}: phase {phase} out of order")
        last = max(last, idx)
        if o.max_probes > max_probes:
            out.append(f"{o.objective_id}: max_probes {o.max_probes} > {max_probes}")
        for kind, allowed, got in (
            ("claim", {c.id for c in planner_input.claims_summary}, o.target_claim_ids),
            ("competency", {c.id for c in planner_input.role_competencies}, o.target_competency_ids),
            ("project", {p.id for p in planner_input.projects}, o.target_project_ids),
        ):
            bad = [g for g in got if g not in allowed]
            if bad:
                out.append(f"{o.objective_id}: unknown {kind} ids {bad}")
    return out


# ----------------------------------------------------------------- (9)
VALID_REJECTION = {"invalid_structured_output", "validation_failure"}


def check_structured_output_rejected(outcomes: Iterable[dict]) -> list[str]:
    """Each bad payload: failure result, typed error, no output, nothing persisted."""
    out: list[str] = []
    for o in outcomes:
        name = o["name"]
        if o["success"]:
            out.append(f"{name}: invalid payload accepted")
        if _val(o["error_type"]) not in VALID_REJECTION:
            out.append(f"{name}: untyped/unexpected error_type {_val(o['error_type'])!r}")
        if o["output"] is not None:
            out.append(f"{name}: output exposed despite rejection")
        if o["stored"]:
            out.append(f"{name}: {o['stored']} artefacts persisted from rejected output")
    return out


# ---------------------------------------------------------------- (10)
TYPED_ERRORS = {"provider_failure", "timeout", "invalid_structured_output", "validation_failure",
                "internal_failure", "input_validation", "plan_validation_failure"}


def check_safe_degradation(outcomes: Iterable[dict], *, require_typed_error: bool = True) -> list[str]:
    """Inspect observed failure artefacts, not inferred provider metadata.

    None-returning services may explicitly opt out of typed-error checking; this
    proves no content only, not a typed error, persistence or flow advancement.
    Optional stored/flow fields assert only the observations actually supplied.
    """
    out: list[str] = []
    for o in outcomes:
        name = o["name"]
        if o.get("success") is True:
            out.append(f"{name}: success reported on failure")
        if require_typed_error and _val(o.get("error_type")) not in TYPED_ERRORS:
            out.append(f"{name}: failure not surfaced as typed error ({_val(o.get('error_type'))!r})")
        if o.get("content") is not None:
            out.append(f"{name}: fabricated content returned on failure: {o['content']!r}")
        if o.get("stored"):
            out.append(f"{name}: {o['stored']} artefacts stored on failure")
        if not o.get("flow_advanced", True):
            out.append(f"{name}: interview flow did not continue")
    return out


# ---------------------------------------------------------------- (11)
def check_no_cross_candidate_leak(runs: list, provider_requests: list, *, markers: dict[str, str]) -> list[str]:
    """No candidate's unique marker appears in another candidate's model requests or stored artefacts."""
    out: list[str] = []
    owner = {}
    for run in runs:
        for t in run.candidate.turns:
            owner[str(t.id)] = run.candidate.cid
    for req in provider_requests:
        blob = " ".join(str(m.get("content", "")) for m in req.messages)
        import json
        try:
            turn_id = json.loads(req.messages[1]["content"])["current_turn"]["id"]
        except Exception:  # noqa: BLE001
            out.append("unparseable request")
            continue
        cid = owner.get(turn_id)
        for other, marker in markers.items():
            if other != cid and marker.casefold() in blob.casefold():
                out.append(f"request for {cid} contains {other}'s marker {marker!r}")
    for run in runs:
        cid = run.candidate.cid
        texts = [r["proposal"].reason + " " + r["proposal"].suggested_probe for r in run.flags]
        texts += [o.summary for o in run.observations]
        for other, marker in markers.items():
            if other != cid and any(marker.casefold() in t.casefold() for t in texts):
                out.append(f"stored artefact for {cid} contains {other}'s marker")
        for r in run.flags:
            if r["session_id"] != run.candidate.session_id:
                out.append(f"{cid}: flag stored under foreign session")
    return out


# ---------------------------------------------------------------- (12)
def check_p5_not_accused(run) -> list[str]:
    """Honest beginner: no contradiction/ownership flag, probe, claim downgrade or honesty language."""
    out: list[str] = []
    for r in run.flags:
        p = r["proposal"]
        if _val(p.flag_type) in CRITICISM_TYPES:
            out.append(f"flag {_val(p.flag_type)} raised against honest beginner")
        for text in (p.reason, p.suggested_probe):
            if ACCUSATION_WORDS.search(text) or ACCUSATORY_PROBE.search(text):
                out.append(f"accusatory language in flag: {text!r}")
    for o in run.observations:
        if _val(o.observation_type) in CRITICISM_TYPES:
            out.append(f"observation {_val(o.observation_type)} against honest beginner")
        if ACCUSATION_WORDS.search(o.summary):
            out.append(f"accusatory observation: {o.summary!r}")
    for u in run.proposals:
        if _val(u.proposed_status) in CRITICISM_STATUSES:
            out.append(f"claim update {_val(u.proposed_status)} against honest beginner")
    for s in run.selections:
        if s.turn_type == "CONTRADICTION_PROBE":
            out.append(f"CONTRADICTION_PROBE selected at turn {s.evaluated_at}")
    return out
