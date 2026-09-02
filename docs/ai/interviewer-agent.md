# Interviewer Agent (text mode)

## Purpose

The Interviewer turns an active, versioned Interview Plan into a natural text
conversation. It may ask a focused probe, adjust conversational difficulty,
move to another objective, recover after weak evidence, or suggest closing. It
does not score the candidate or control the interview lifecycle.

This milestone is text-only. There is no speech recognition, text-to-speech,
Skeptic integration, assessment, or candidate feedback.

## Execution boundary

```text
candidate text
    |
    v
authenticated API -> persist candidate turn -> InterviewerContextBuilder
                                               |
                                               v
                                    Interviewer Agent proposal
                                               |
                                               v
                                  deterministic State Machine
                                               |
                                               v
                                  persist public interviewer turn
```

The application verifies session ownership and ACTIVE status. It persists the
candidate turn before model inference, so an inference failure cannot discard
the candidate's response. A client-generated idempotency key and transactional
PostgreSQL functions prevent duplicate candidate turns and allocate the next
turn index while holding the session row lock.

## Context boundary

`InterviewerContextBuilder` supplies only:

- the current plan objective and phase;
- at most six recent turns;
- claims and role competencies explicitly targeted by that objective;
- the current primary thread and probe count;
- remaining phase and total interview time; and
- at most one application-approved, one-turn-late `pending_flag` when live
  Skeptic probes are enabled.

It does not supply a full resume, full Claims Graph, database records, scoring
rubrics, expected answers, assessment results, or authorization data. Candidate
text and all retrieved content are treated as untrusted prompt data.

## Relationship with the Planner

The Planner creates the versioned objective sequence, target IDs, initial
questions, and time allocation. The Interviewer starts with the active plan's
first objective and uses that plan as the deterministic fallback when model
output is unavailable or rejected. The Interviewer cannot edit or replace the
plan.

## Relationship with the State Machine

The model returns a typed `InterviewerDecision`; this is a proposal. Application
code validates its IDs, wording, action, turn type, and thread, then asks the
state machine whether the action is legal. The state machine remains authoritative
for READY-to-ACTIVE transition, phase progression, time budgets, the two-probe
cap, recovery, and movement toward ASSESSING. A proposed third probe becomes a
deterministic recovery/move-on. An expired total budget becomes a closing turn
without calling the model.

## Failure behavior and metadata

Malformed structured responses use the shared agent framework's retry policy.
After retries are exhausted, Mirror retains the stored candidate turn, records
`INTERVIEWER_AGENT_FAILED`, and uses a short safe probe or the next planned
question. Stored interviewer turns include execution ID, model, prompt version,
latency, retry count, and targeted entity IDs. Public API responses omit all of
that internal metadata, along with reason codes and hidden context.

## Skeptic integration

The deterministic `FlagEligibilityService` may place one eligible flag in
`pending_flag`; the Interviewer cannot query flags itself. A used flag must be
identified by `used_flag_id`, retain the application-selected probe type, and be
worded neutrally. `CONTRADICTION_PROBE` is rejected without the matching pending
flag. Ignored or rejected flags are not consumed. See
`docs/architecture/flag-activation.md` for timing and consumption rules.

## Explicit limitations

The Interviewer cannot access SQL, authorize a user, extend time, exceed probe
limits, decide truthfulness, score correctness, assess readiness, reveal a
rubric, praise or humiliate a candidate, coach an expected answer, or produce a
candidate-facing performance judgment.

