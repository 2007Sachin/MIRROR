# Architecture state

Canonical architecture lives in `docs/architecture/MIRROR_ARCHITECTURE.md` and the topic docs.

## Loop 2 local architecture disposition — 2026-10-06

At reviewed implementation HEAD `635209c43fe884c92ed62b0c03b449247354afc3`, the local slice adds an optional owner-scoped target, exact-scope versioned research matching, explicit claim-to-round mapping, multi-round blueprint/priority, guarded prompt-pack generation, immutable first-writer manifests and changed-context recovery. Research basis and question origin are separate; Mirror-generated prompt rows remain `MIRROR_GENERATED`. Architecture and Data/Supabase reviewers PASS; disposable PostgreSQL tests passed 32/32; exact GitHub CI run `37509014604` passed all required jobs.

This proves local architecture/product behavior with synthetic QA and disposable SQL only. Hosted migration/PostgREST, Amazon India validity, and production readiness are NOT proven. No hosted mutation, deployment or Loop 3.

## Pre-Loop2 forensic snapshot (historical)

This snapshot records the 2026-10-04 baseline at head `8e3193f`; the absence claims below are superseded in part by Loop 2.

## Shape

| Layer | What | Evidence |
|---|---|---|
| Web | Next.js 16 App Router, React 19, Tailwind 4, Supabase SSR, `@mirror/web` workspace. `apps/web/AGENTS.md` warns Next 16 differs from training data: read `node_modules/next/dist/docs/` first | `apps/web/package.json`, `apps/web/AGENTS.md` |
| API | FastAPI + Pydantic, Python 3.12 (`.venv`), `apps/api/app` (123 Python modules). Auth via Supabase JWT; service-role key backend-only | `apps/api/app/auth.py`, `docs/architecture/authentication.md` |
| Workers | `workers/assessor` (post-session job queue) and `workers/skeptic` (each a `worker.py`); `workers/tts` is a README-only placeholder | `scripts/run-assessor.js`, `assessment_worker.py` |
| Data | Supabase Postgres; 44 migration files; RLS enabled in 24 files, 41 `create policy` statements; anon revoked on new tables (`202609250001`); migration-contract tests | `supabase/migrations/` |
| AI | Bounded agents with typed contracts, registry, runner, provider adapters, versioned prompts (`apps/api/app/prompts/<agent>/vN.md`; planner v1-v3, every other agent v1) | `apps/api/app/agents/`, `prompts/` |
| Models | Every agent configured to `sarvam-105b-conversations`; STT `deepgram nova-3` or Sarvam `saaras:v3`; TTS Sarvam `bulbul:v3` | `apps/api/app/config.py` |
| Shared | `packages/schemas` (TS), `packages/prompts` (legacy v1 prompt copies), `packages/evaluation/personas.json` | |

Invariants (from `AGENTS.md`, kept): deterministic backend owns identity/lifecycle/phases/timing/retries/probe limits/failures; agents are bounded and never own SQL; backend state is canonical; no agent-to-agent free workflow; orchestration testable without an LLM.

## Weaknesses and debt (ranked by risk to Mirror 2.0)

1. **No target/intelligence layer** — company, geography, round, process, provenance don't exist as data; `company_id` columns are orphaned. Everything Mirror 2.0 needs sits on top of a role-and-candidate-only model.
2. **Interview model is single-session, fixed-phase** — `Phase` enum and `interview_plans` are per session; a plan cannot express "round 2 of 4 for company X". Multi-round must be additive (blueprint above sessions), not a rewrite of the state machine.
3. **Verification integrity** — Loop 1 now has CI configuration and executable deterministic AI-eval/contract tests. Latest orchestrator run before review corrections: 953 passed, 3 skipped, 2 strict xfailed. Independent Architecture review nevertheless **REJECTS** behavioral certification: quote-free invented evidence is accepted, specialist positions can be rewritten, and a typed failure check used invented metadata. Browser harness exists but Security/Data rejected isolation and false-green handling; no browser PASS exists. Source-text frontend contracts are not browser tests. See `QUALITY_GATES.md` for current evidence and blockers.
4. **Hosted compatibility gap, migration history unknown** — the retained read-only snapshot lacks exposed `interview_events`, `interview_debriefs`, `evidence_items`, `coverage_links`. This is not proof that specific migrations were never applied; enum compatibility and earlier migration completion are unverified. `detailed_food_logs` and `nutrition_goals` are exposed but unmanaged by this repo; ownership/grants are unknown. Catalog-level policies, triggers, grants and migration ledger remain blocked pending authorized read-only evidence. See corrected `HOSTED_SUPABASE_DRIFT.md`.
5. **Monoliths** — `apps/api/app/main.py` 2,540 lines (a `routes_*.py` split pattern exists but is only partly applied); `apps/web/src/lib/api.ts` 1,360; `apps/web/src/lib/copy.ts` 1,503.
6. **Single model provider for every agent** — no fallback model, no per-agent model evaluation.
7. **Legacy schema** — see `PRODUCT_STATE.md` Dormant list; also `.down.sql` exists only for the initial migration.
8. **Doc drift** — `READINESS_QA_STATUS.md` reports 455 passed; at HEAD the suite has 857 tests (856 passed, 1 skipped with a local `.env`). `IMPLEMENTATION_STATUS.md` marks "Deployment: UNKNOWN".
9. **Deprecations / process-local state** — three FastAPI `@app.on_event` hooks (`main.py:290`, `295`, `306`: a startup idle-pause loop and two shutdown hooks). The idle-pause loop and deferred writes live in process memory (lost on restart; wrong for multi-instance).
10. **Env hygiene (STATIC-ONLY)** — `.env` and `.env.bak-*` are gitignored. **All 29 commits across all refs were scanned for env filenames and key-shaped strings (JWT, `sk-`, `sb_secret_`, provider-key assignments): no hits; `.env*` was never committed** (VERIFIED-EXECUTED). They sit in a OneDrive-synced Desktop folder, so secrets are copied to cloud sync; recommended practice is now in `README.md` ("Secrets and local environment files"). Contents were not read. Before Loop 1, tests loaded `.env` (real hosted URL and keys) into every test process; the root `conftest.py` now isolates the suite (see `QUALITY_GATES.md`).

## Tooling overlap

Three agentic tools touch this repo: Codex (`.codex/`, `AGENTS.md`), Claude Code (`apps/web/CLAUDE.md`; `.claude/` exists but is empty), and Hermes (this layer). Rule: `AGENTS.md` is the shared contract; concurrent writers on the same files are prohibited (stop condition). Observed during bootstrap: `origin/main` was briefly 7 commits ahead of the local tracking ref, then equal — suggesting another session pushed; a dirty-tree/head-moved check is in the continuation protocol for that reason.

## Security boundary (STATIC-ONLY, surface review only)

Service-role key backend-only (0 hits in `apps/web/src`; built bundle not scanned); browser uses public keys; `apps/web/src/proxy.ts` (the Next 16 proxy, formerly middleware) does a UX-level redirect from verified claims and **fails open if Supabase is unreachable**; the API re-verifies every request via `GET /auth/v1/user` (no cache, so API availability is coupled to Supabase); owner-scoped RLS + ownership triggers (e.g. `sessions_verify_role_profile_ownership`); resumes/JDs/transcripts treated as untrusted input; candidate-facing responses must not expose hidden reasoning. **Static audit result (independent Security/Data Reviewer, STATIC-ONLY):** all 53 public tables end with RLS enabled; anon has no table grants; 17 tables have RLS but no policies (service-role only, apparently intentional); all 11 `SECURITY DEFINER` functions set `search_path = public` and revoke public/anon/authenticated; every one of 107 route handlers except `GET /health` sits behind an auth dependency and none takes `user_id` from the client; CORS is a single origin. **Caveats:** hardening is per-table and manual (`202609250001` covers 8 tables as a retroactive fix; there is no `ALTER DEFAULT PRIVILEGES`), so every future table, including every `ii_*` table, must revoke anon/authenticated itself and needs a contract test; 12 tables keep residual TRUNCATE/REFERENCES/TRIGGER for `authenticated` (low severity); `/api/docs` and `/openapi.json` are unauthenticated; if only the service-role key is missing, auth still works but repositories silently fall back to in-memory (writes lost on restart) while `environment` defaults to "development"; `skeptic_repository.py:426` queries a `users` table that `202608310002` renamed to `profiles` (the admin skeptic route is likely broken; it fails closed; needs a live test). **Not done:** live RLS/policy verification against the hosted project (BLOCKED, see the drift report), cross-user probe tests, dependency audit. Any Interview Intelligence content (scraped text) is a new untrusted-input class and must enter through the same rules.
