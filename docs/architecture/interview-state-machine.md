# Interview State Machine

Mirror's interview lifecycle is controlled by deterministic application and PostgreSQL logic. An LLM cannot start, extend, close, complete, or fail a session; change interview phases; exceed probe limits; or make a newly created flag eligible early.

## Responsibilities

The deterministic `InterviewStateMachine` controls:

- legal session-status transitions;
- ordered interview phases;
- configured total and per-phase time budgets;
- the active primary-question thread;
- the hard limit of two adaptive probes per primary question;
- recovery eligibility and recovery count;
- one-turn-late flag eligibility;
- completion percentage and terminal timestamps;
- ownership-scoped state access; and
- append-only session events.

Future agents may propose a primary question, a probe, a phase change, or closing the interview. Application code must submit that proposal to the state machine. The state machine can accept or reject it based only on trusted persisted state and deterministic rules.

## Lifecycle

```text
CREATED -> PREPARING -> READY -> ACTIVE -> ASSESSING -> COMPLETED
    |          |          |         |           |
    +----------+----------+---------+-----------+-> FAILED
```

Terminal sessions cannot transition again. The database also validates these transitions, so a programming error in backend code cannot bypass the lifecycle. Optimistic concurrency prevents two stale decisions from both updating the same session.

`POST /api/v1/sessions/{id}/prepare` performs the deterministic preparation boundary and leaves the session `READY`. It does not generate a question plan. `start` moves a ready session to `ACTIVE`. Until an assessor exists, `end` deterministically moves `ACTIVE` through `ASSESSING` to `COMPLETED`. Legacy `/api/sessions` paths remain aliases of the same handlers.

## Phases and time

Active phases progress in one direction:

```text
INTRO -> BACKGROUND -> PROJECTS -> ROLE_CORE -> DEEP_DIVE
      -> BEHAVIOURAL -> CLOSING -> COMPLETE
```

`COMPLETE` is entered only when an assessing session completes. Total duration and phase duration come from `INTERVIEW_DEFAULT_DURATION_SECONDS` and `INTERVIEW_PHASE_TIME_BUDGET_SECONDS`; development defaults are 20 minutes and 3 minutes. Once a session starts, its total budget is immutable. Questions and probes are rejected after either the current phase or total budget expires. Closing remains available so an expired interview cannot become stuck.

## Probe cap and recovery

Registering a primary question starts a new thread and resets its probe counter. Probe one and probe two are permitted. Probe three is rejected regardless of what a future Interviewer proposes. When probe two is registered, `PROBE_LIMIT_REACHED` is recorded and the engine requires recovery before another question thread continues. Repeated inability to answer may also trigger recovery without assigning a score.

## One-turn-late flags

A future Skeptic flag stores the candidate turn where it was detected. Eligibility is:

```text
current_turn >= detected_at_turn + 1
```

Therefore a flag detected from turn N cannot influence turn N. It becomes eligible at turn N+1 and remains eligible later until consumed. This rule is implemented without a Skeptic dependency.

## Events

State changes write ownership-scoped records to `session_events`. Events include session preparation and start, phase changes, primary questions, probes, probe-limit exhaustion, recovery, and session termination. State mutation and its primary event are committed together by `apply_interview_state_change`. Events contain identifiers and control metadata, not full transcript or resume content.

## Why lifecycle control is not delegated

Language-model output is probabilistic and may be malformed, delayed, repetitive, or influenced by untrusted interview content. Lifecycle and safety rules require repeatable outcomes, auditable transitions, bounded duration, strict authorization, and concurrency control. Those properties belong to application code and database constraints; agents remain advisory participants.

