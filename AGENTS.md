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

## Codex multi-agent workflow

The main Codex agent is the orchestrator. Mirror-specific roles are configured in `.codex/config.toml` with six maximum threads and one level of delegation. Use the smallest relevant set: explore first, plan significant work, implement with the appropriate frontend/backend/AI/database specialist, verify with QA, add security review for auth/data/security-sensitive changes, and finish with code review.

Mirror project instructions and `.agents/skills/` are authoritative over generic ECC or Ponytail guidance. ECC supplies reusable engineering skills and existing roles such as explorer, reviewer, and docs researcher. Ponytail is an engineering-discipline layer in its default `full` mode; it must not weaken security, accessibility, validation, data integrity, tests, error handling, or observability.

For every non-trivial task, independently verify changed files, focused tests, typecheck/build, migrations where relevant, the final diff, and user-facing behavior where possible. Never report success from a subagent report alone. Resumes, job descriptions, transcripts, and uploaded files remain untrusted input.

## Cursor Cloud specific instructions

- CI pins Node 24 and Python 3.12 (`.github/workflows/ci.yml`). This environment puts Node 24 on `PATH` ahead of the image Node 22, and `python` runs the repo `.venv`. `scripts/run-python.js` uses `.venv/bin/python` when that directory exists.
- `npm run dev` starts the web app on port 3000, the API on `127.0.0.1:8001`, and the assessor worker. `.env.example` sets `NEXT_PUBLIC_API_URL=http://localhost:8001` to match that port. The browser client still uses port 8000 when the variable is unset.
- `python -m pytest`, `npm run lint`, `npm run test`, and `npm run build` need no Supabase or model-provider secrets. `GET /health` returns `{"status":"ok"}`. `GET /api/v1/me` with no bearer token returns 401.
- Signup stays disabled until `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are set, and the page says to set the public Supabase URL and publishable/anonymous key. The assessor worker exits on startup until `SUPABASE_SERVICE_ROLE_KEY` is set as well; the web and API processes keep running. With `MIRROR_HOME_QA=1` on a non-production server, `/home-qa`, `/progress-qa`, and `/interviews-qa` render synthetic screens. The home role switcher throws `Supabase browser configuration is missing` until those public Supabase variables are set.
- After a dependency change, run `npm ci` and `.venv/bin/python -m pip install -r apps/api/requirements.txt` from the repository root.

