# Skeptic flag activation

## Control flow

```text
Candidate turn N stored ──> asynchronous Skeptic analysis ──> unresolved flag
                                                               │
Candidate turn N+1 or later ──> deterministic eligibility ─────┘
             │
             └─> one pending_flag ─> Interviewer proposes neutral probe
                                      │
                                      └─> policy + probe cap accept
                                           ─> turn stored
                                           ─> conditional flag consumption
```

The Skeptic proposes observations. `FlagEligibilityService`, PostgreSQL RPCs,
and the interview state machine control whether one can influence a later
question. No prompt can bypass these checks.

## Eligibility

A flag is eligible only when all of these are true:

- live probes are enabled and the process is not configured for shadow-only mode;
- the session belongs to the caller and is `ACTIVE`;
- the flag is unconsumed, unresolved, undisputed, and marked safe to surface;
- its confidence meets `SKEPTIC_LIVE_PROBE_MIN_CONFIDENCE` (default `0.8`);
- `detected_at_turn < current_candidate_turn_index`;
- the current primary thread has fewer than two probes.

The database enforces ownership, active status, one-turn-late timing, and flag
state. Application code repeats the non-authoritative data checks and the state
machine remains authoritative for the two-probe cap.

`SKEPTIC_SHADOW_MODE=true` disables activation even if live probes were
accidentally enabled, preserving a shadow-only production pilot. With shadow
mode disabled and `LIVE_SKEPTIC_PROBES=true`, current or previously stored safe
flags can be considered.

## Selection and context

Eligible flags are ordered deterministically by severity, confidence, relevance
to the current objective's target claims, claim verification priority, and age.
UUID breaks an otherwise exact tie. Only the winner reaches the model.

The supplied `pending_flag` contains its ID, type, short claim and reason
summaries, a suggested probe, confidence band, and application-selected probe
type. It contains no chain-of-thought. Ownership drift and direct inconsistency
map to `CONTRADICTION_PROBE`; vagueness and unsupported scale map to
`DEPTH_PROBE`. The Interviewer controls natural wording but cannot change that
classification.

## One-turn-late and asynchronous races

The strict less-than comparison is present in the SQL eligibility function, the
conditional consumption function, and application filtering. A flag detected
from turn 5 cannot enter the context built for turn 5. It can first appear for a
later candidate turn.

The live path never waits for the Skeptic worker. If the Interviewer has already
generated its response when analysis completes, the flag remains unresolved
and may be considered on a later turn. This is expected behavior.

## Consumption and failure behavior

A flag is not consumed when fetched, ranked, placed in context, ignored by the
Interviewer, rejected for accusatory wording, or blocked by the probe cap. After
an accepted question is persisted, `consume_skeptic_flag` performs one atomic,
conditional update and verifies the owned active session, candidate turn,
responding interviewer turn, one-turn-late rule, confidence, and current flag
state. Concurrent consumers cannot both succeed.

The interviewer turn and consumption use separate repository operations because
the existing turn RPC owns turn creation. A consumption outage is logged and
does not retract an already delivered live question; the conditional operation
can be reconciled later. No transcript or full Skeptic reasoning is logged.

