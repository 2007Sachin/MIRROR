# Mirror engineering guide

Mirror is an evidence-backed interview-readiness diagnostic, not a generic mock-interview scorecard. Candidates provide a resume and target role, complete an adaptive interview, and receive a claim- and evidence-grounded diagnosis with uncertainty and limitations. The product distinguishes what a candidate claims from what interview evidence supports. During the interview the UI shows only conversation, audio state, phase, timer, and controls; hidden evaluation is never shown live.

## Architecture principles

- Deterministic backend code owns identity, persistence, lifecycle, phases, timing, retries, probe limits, delayed flags, and failures.
- Agents are bounded specialists with typed input/output contracts and versioned prompts; they reason but do not own workflow or SQL.
- Evidence-first reasoning preserves claim, source, confidence, ownership, scope, impact, chronology, and uncertainty.
- Backend state is canonical; frontend renders contracts and never computes authoritative readiness.
- No uncontrolled agent-to-agent workflow or arbitrary agent database access.
- Orchestration must be testable without an LLM.

## Repository map

`apps/api/app` is the FastAPI service (auth, Supabase repositories, domain services, interview engine, agents, prompts). `apps/api/tests` contains backend contract tests and synthetic fixtures. `apps/web/src/app` is the Next.js App Router; `apps/web/src/components` and `src/lib` contain reusable UI and API/Supabase clients. `packages/schemas` contains shared TypeScript schemas. `supabase/migrations` and `supabase/seed` contain database migrations and separate development data. `docs` contains architecture, AI, API, product, scoring, privacy, and fixture documentation. Project-specific skills are under `.agents/skills/`.

## Development rules

Inspect before modifying. Prefer incremental changes and existing patterns; do not silently replace working systems or add dependencies without justification. Keep prompts versionable and validate LLM responses. Separate orchestration, prompts, persistence, and UI; avoid duplicated schemas and business logic in React. Treat resumes, JDs, and transcripts as untrusted data. Never expose chain-of-thought, hidden agent reasoning, internal weights, or PII in candidate-facing responses.

## Verification

Run supported checks before completion: `python -m pytest`, `npm run lint`, `npm run test`, and `npm run build`. Report environment-dependent failures separately from regressions.

