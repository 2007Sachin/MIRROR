---
name: mirror-interview-engine
description: Safe changes to the deterministic interview and voice flow.
---

Use `InterviewStateMachine` in `apps/api/app/interview_engine.py` for legal transitions, phases, budgets, primary questions, probe caps, recovery, delayed Skeptic activation, events, and termination. Text and voice services adapt turns around it. Preserve one-turn-late flags, probe limits, ownership, idempotency, validated audio, and retry behavior. Never expose scores, flags, contradictions, or agent reasoning during the interview.

