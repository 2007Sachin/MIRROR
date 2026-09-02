# Mirror architecture

## 1. Product purpose

Mirror is an evidence-backed interview diagnostic. It connects resume and role claims to spoken interview evidence, then presents a readiness diagnosis with uncertainty, root causes, and limitations. It is not a generic mock-interview leaderboard or a placement prediction system.

## 2. Current repository architecture

The repository is an npm workspace containing a Next.js 16/React 19 web app (`apps/web`) and a Python 3 FastAPI service (`apps/api`). Supabase PostgreSQL is the persistence layer, with Supabase Auth for identity and Storage for documents/audio. Pydantic models define API and agent contracts; TypeScript schemas live in `packages/schemas`. There is no ORM and no graph database. Production database changes are SQL migrations under `supabase/migrations`; development fixtures are separate under `supabase/seed` and `apps/api/tests`.

## 3. Implementation status

See `docs/architecture/IMPLEMENTATION_STATUS.md` for the audited feature matrix. This document intentionally distinguishes complete, partial, planned, and unknown behavior.

## 4. Multi-agent architecture

`apps/api/app/agents/` contains the registry, runner, provider adapter, structured result/error models, permissioned tools, logging, and versioned prompts. Existing bounded components include Resume, Role, Interview Planner, Interviewer, Skeptic, Evidence, specialist assessors, adjudication, and verdict services. Agents reason over minimal typed context; deterministic services own persistence, authorization, workflow, and scoring/aggregation. Prescription and future calibration remain planned unless explicitly implemented.

## 5. Interview orchestration

`InterviewStateMachine` in `apps/api/app/interview_engine.py` owns legal session transitions, phases, budgets, primary questions, probe caps, recovery, delayed Skeptic flags, and session events. Text and voice services adapt turns around that state machine. A flag detected on turn N is not eligible until a later turn; the engine, not an LLM, decides whether a probe or transition is allowed.

## 6. State ownership

Supabase is the system of record. Backend repositories enforce owner-scoped access and service boundaries; database RLS provides defense in depth. The frontend owns presentation and local interaction state only. It never accepts a client-supplied user identity as authority or computes canonical readiness.

## 7. Agent boundaries

Agents cannot authenticate users, authorize access, execute arbitrary SQL, alter session lifecycle, change billing, bypass retries, or directly write canonical claim/session state. Inputs are untrusted documents/transcripts and outputs are validated against Pydantic schemas. Prompt versions and model metadata are persisted for analysis where applicable, without exposing hidden reasoning to candidates.

## 8. Data flow

Resume/JD ingestion → resume and role analysis → interview planning → deterministic interview engine → transcript/audio persistence → Skeptic/Evidence processing → claims graph and claim resolution → specialist assessment → adjudication → deterministic verdict aggregation and candidate-safe report. Each arrow is an application-controlled boundary; asynchronous jobs may be introduced without changing ownership rules.

## 9. Evidence model

Claims preserve source document/reference, status, confidence, verification priority, versions, relations to entities, and later evidence. Evidence records may reference turns or documents and have direction/strength. High-priority claims can remain insufficiently evidenced; the system does not force a true/false judgment.

## 10. Security and privacy

Supabase access tokens are verified by the FastAPI authentication dependency. Owner-scoped repositories and RLS prevent cross-user reads. Browser configuration contains only public Supabase values; service-role credentials stay backend-only. Candidate APIs omit model/debug metadata and hidden reasoning. Resumes, transcripts, and audio are sensitive data and should not appear in logs by default.

## 11. Failure and retry strategy

Provider, timeout, malformed structured output, schema, tool, and internal failures are represented separately by the agent runner. The runner retries malformed output within an agent-specific limit. Domain services use idempotency and ownership checks where required (notably voice turns and analysis versions). User-facing routes return sanitized errors.

## 12. Observability

Agent executions emit structured identifiers, model/prompt version, latency, retries, success, and error type. Voice records provider latency metrics and events. Session and domain events provide an audit trail. Full PII and hidden reasoning are intentionally excluded.

## 13. Current limitations

Live Supabase integration, provider credentials, and local database reset may not be available in every development environment. Some repositories retain in-memory/test adapters. Report and assessment behavior is contract-tested, but production calibration and outcome validation are not established. Deployment and analytics infrastructure are not represented as a complete production stack.

## 14. Planned components

Future work may add richer background jobs, calibration, prescriptions, analytics, and production deployment hardening. New work must preserve deterministic orchestration, typed boundaries, evidence provenance, and candidate-safe output.

