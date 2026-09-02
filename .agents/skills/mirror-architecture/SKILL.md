---
name: mirror-architecture
description: Protect deterministic orchestration and typed backend boundaries.
---

FastAPI services/repositories own authorization, persistence, lifecycle, phases, timing, retries, idempotency, and failures. `apps/api/app/interview_engine.py` owns deterministic interview transitions. `apps/api/app/agents/` provides schema-first provider boundaries; agents cannot execute arbitrary SQL or mutate canonical state. Supabase PostgreSQL is the system of record, with RLS and owner-scoped repositories as defense in depth. Use migrations, versioned prompts, structured logs, and deterministic fakes.

