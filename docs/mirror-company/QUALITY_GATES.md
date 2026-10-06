# Quality gates

## Evidence labels (mandatory in every report and receipt)

- **VERIFIED-EXECUTED** — a command, test, or browser/API run actually happened and its output was read.
- **STATIC-ONLY** — conclusion from reading code/docs. Never call this "verified".
- **NOT DONE** — stated explicitly, with the reason.

## Current Loop 2 disposition — local slice accepted (2026-10-06)

| Gate | Status | Evidence scope |
|---|---|---|
| G0 records/scope | **PASS** | Current sprint, research, product, roadmap, known-issues, release and receipt records reconcile the bounded local-only decision. |
| G1 code/CI | **PASS at reviewed implementation HEAD** | GitHub run `37509014604` is exact SHA `635209c43fe884c92ed62b0c03b449247354afc3`, all 3 required jobs succeeded. This run does not certify later closure-document commits; every new HEAD requires its own CI before merge. |
| G2 data/security | **PASS local-only** | Disposable PostgreSQL 16 forward/backfill/invariant/rollback run: 32/32. Hosted migration/PostgREST and current hosted applied-state are **NOT VERIFIED**. |
| G3 candidate experience | **PASS isolated synthetic browser scope** | Real Chrome in isolated CI: 36 desktop + 36 mobile steps; T09b and T16 pass both viewports; no page/console errors, failed/bad/denied requests, unmocked API calls or mobile overflow. Runner acceptance uses `okWithAcknowledgedKnownIssues=true`; strict result is false only for KI-020, which remains debt. Fake Auth/API; no Python assessment UI or real backend. |
| G4 research/AI behavior | **PASS deterministic synthetic scope** | Scope/provenance regressions and AI-eval tests pass with fictional fixtures/fake providers. No live model or Amazon India validation. |
| G5 release decision | **PASS for local slice only** | Independent final reviewers PASS; Release Gatekeeper: A PASS, B HELD, C NOT VERIFIED. No production release approval. |

**A — LOCAL ARCHITECTURE/PRODUCT: PASS. B — AMAZON INDIA RESEARCH: HELD. C — HOSTED RELEASE READINESS: NOT VERIFIED.** `LOOP 2 LOCAL SLICE ACCEPTED` authorizes only the scoped local result and repository integration under the owner's separate instruction. No hosted write, deployment, production release, or Loop 3.

## Historical Loop 1 status — LOOP 1 ACCEPTED (2026-10-04)

| Gate | Status | Evidence scope |
|---|---|---|
| G0 repository integrity | **PASS (final independent review)** | Four reconciled closure documents and exact reviewed change scope accepted by final Gatekeeper; raw catalogs/manifests remain ignored |
| G1 automated verification / real CI | **PASS at reviewed HEAD; fresh transcription CI required** | 1204 passed/3 skipped/0 xfailed; Node tooling 5, browser safety 16; typecheck/copy lint/build exit 0. Historical Linux runs 37196654767 (02afc70), 37196926810 (e885130) green, not evidence for the final revision |
| G2 hosted data/security state | **PASS (scoped independent review)** | Fresh metadata confirms approved nutrition retirement, preserved retained security state and abandonment enum/function/trigger compatibility; isolated real-RPC adapter integration executed; no hosted/PostgREST/browser/full-readiness claim |
| G3 browser/runtime | **PASS (isolated synthetic CI scope)** | Real Chrome with fake Auth/API, desktop/mobile; acknowledged KI-020 retained; Python assessment pipeline and unavailable-diagnostic UI not exercised (KI-022); local runtime stays blocked |
| G4 AI behaviour | **PASS (deterministic only)** | B5/B7/B12 accepted; no live-model evidence; residual debt retained |
| G5 independent final decision | **PASS (Loop 1 closure only)** | Independent final affirmative decision in scratch/final_gatekeeper_final.md; no production-release authority |

## Hosted remediation and verification — 2026-10-04 (historical Loop 1)

**LOOP 1 ACCEPTED — independent final Release Gatekeeper decision, 2026-10-04.** G0/G1/G2/G3/G4/G5 PASS within the bounded trust-baseline and approved remediation scope. Reviewed HEAD `8257985ff1be7f52af34e49162b0d40b5bd6c69a`; independently read real Linux CI run `37202320540` (https://github.com/2007Sachin/MIRROR/actions/runs/37202320540), completed/success with all three jobs successful at that exact SHA: frontend typecheck/build; backend/copy/AI evaluation; isolated synthetic browser critical path. Decision evidence: ignored `scratch/final_gatekeeper_final.md`. This transcription creates a new commit: fresh exact-final-HEAD CI must pass before merge; the reviewed run cannot certify that new SHA. PR #1 is unmerged at transcription. Owner authorizes final documentation commit/push and safe merge-commit finalization only after CI and repository-policy checks. No production release, deployment, further hosted mutation, debt waiver or Loop 2 is authorized. Historical red commits remain red.

- Owner explicitly retired the nutrition application and authorized destruction of its obsolete nutrition data. Architecture, Data and Security independently approved the exact two-table scope; Security's generic retention condition was resolved by that explicit authorization, not by an asserted backup. After fresh live identity/dependency-closure refresh against the approved local manifest, the parent executed only `DROP TABLE public.detailed_food_logs RESTRICT;` and `DROP TABLE public.nutrition_goals RESTRICT;`. No CASCADE, Mirror-row mutation, shared/auth/storage removal or blanket migration replay was authorized. Raw catalogs and the deletion manifest remain local and ignored.
- Hosted cleanup ledger: `20261004121203` / `retire_verified_nutrition_tables`. Repository parity file: `supabase/migrations/20261004121203_retire_verified_nutrition_tables.sql`; its two `IF EXISTS` drops are idempotent for clean checkouts where nutrition never existed. Deployed SQL lacked `IF EXISTS`: freshly verified table existence made the two forms equivalent for that execution. This records completed scoped cleanup, not permission to apply migrations elsewhere.
- Independent fresh SELECT-only Security/Data review (`scratch/g2_post_remediation_review.md`): both nutrition tables and their inventoried automatic dependents absent; 49 retained public Mirror tables retain RLS and no anon table grants. Retained Mirror/auth/storage security metadata, policies, grants, constraints and triggers preserved except the explicitly approved lifecycle-function replacement; all 123 public foreign keys preserved. No application rows or storage objects were read for that review.
- Hosted `20261004121238` / `session_abandoned` installs the exact existing repository `202610010002_session_abandoned.sql` enum/function behavior. Filename/ledger numbering differs: expected version drift, not missing behavior; do not replay the repository migration merely to force ledger equality. Four absent future-feature tables (`interview_events`, `interview_debriefs`, `evidence_items`, `coverage_links`) remain off Loop 1 paths and are not repaired or waived. Existing lowercase enum labels, `update_claim_status` service-role EXECUTE absence and excess authenticated story/practice privileges remain separately scoped debt.
- Attributed executed evidence: 127 lifecycle/consumer tests passed (memory/fake persistence); exact migration applied twice to a minimal isolated PostgreSQL fixture, with 225 real-trigger transition pairs and 10 immutable-budget checks passing each time. This is not the full hosted schema. **Isolated real-RPC integration EXECUTED** (`scratch/abandonment_rpc_integration.md`): actual FastAPI router → InterviewStateMachine → SupabaseSessionRepository → local psql transport adapter → exact `apply_interview_state_change` SQL → persisted state/events. CREATED/PREPARING/READY/ACTIVE return 200 with one event; retries are idempotent; foreign/anonymous endpoint requests return 404/401; invalid states return 409 unchanged. Concurrent calls return 200/200 with exactly one event; forced event-insert failure rolls back the complete session update atomically. Fresh repository reads projected through DashboardDiagnostic exclude abandoned sessions from activity/practice eligibility. SQL EXECUTE denial for anon/authenticated roles was checked separately. Minimal synthetic schema and synthetic authentication are used; this does not verify PostgREST/JWT/browser/hosted RLS/service-role grants, full home/readiness recomputation, the deferred pending-write race or live review enqueue.
- Post-remediation local regression (`scratch/post_remediation_regression.md`, checkout `3d08c9e`): 1204 passed, 3 skipped, 0 failed/0 xfailed; AI partition 110 passed/2 skipped, non-AI 1094 passed/1 skipped; Node tooling 5 passed and browser-safety 16 passed; frontend typecheck, copy lint (169 files, 0 banned hits, 3 soft warnings), production build (11/11 static pages) all exit 0. These are attributed local executions, not a new browser journey, live-model run or final-branch GitHub CI.

KI-016..022 residual debt remains unwaived (KI-021's original G2 blockers are resolved, not blanket compatibility certification). G2 acceptance retains isolated SQL-adapter/PostgREST/JWT/hosted-RLS/full-readiness limits; G3 is isolated synthetic desktop/mobile only, with KI-020/KI-022 and local runtime blockage retained; G4 is deterministic only, not live-model or speech-quality certification. Gatekeeper G5 affirmatively accepts Loop 1 closure. Fresh exact-final-HEAD CI and policy-compliant merge remain required. Final branch/main SHAs, CI jobs and actual PR merge status will be recorded in ignored `scratch/loop1_merge_receipt.json` and `.md`, avoiding a premature merged claim or circular merge-SHA documentation commit. No deployment, hosted write or Loop 2.

### Superseded history (kept for the record)

#### Earlier status (NOT APPROVED, superseded)

### Correction verification (review still pending)

After scoped infrastructure fixes, the orchestrator's full offline suite completed with **1060 passed, 3 skipped, 5 strict xfailed**, 6 existing FastAPI warnings, exit 0 in 46.25s. Evidence: `C:/Users/sachi/AppData/Local/hermes/cache/scratch/loop1_corrected_pytest_green.txt` and `loop1_corrected_pytest.xml`. The first integration run failed with 30 test-module identity errors: isolation tests imported the nested AI-eval conftest. A root-plugin fixture fixed that collision; the full rerun passed.

(Historical, superseded 2026-10-04: all five contracts now pass; see LR-0001.) The five strict xfails exposed three invented-evidence/adjudication contract failures and two Skeptic candidate-protection failures. Production services are unchanged; these requirements do NOT pass. Hosted inspector now has tested redirect/URL/method guards and no import-time credentials; Python socket rails include bytes/UDP checks and CI pins live evaluation off. Independent follow-up verdicts (`deleg_a8687fff`) now APPROVE these scoped infrastructure corrections; they explicitly do NOT approve production G4, browser runtime G3, release or Loop1 closure. Gatekeeper disposition is now final: scoped infrastructure ACCEPTED, overall Loop1 BLOCKED / IN PROGRESS, G3 BLOCKED, product G4 FAIL, G5 REJECTED. No waiver or release authorization. See `RECEIPTS/LR-0001-trust-baseline.md`. No hosted tooling execution or browser PASS is authorized by a green test run.

The baseline below is historical, not current certification. Latest orchestrator execution before reviewer corrections: **953 passed, 3 skipped, 2 strict xfailed**, exit 0, 30.99s; log/JUnit in `C:/Users/sachi/AppData/Local/hermes/cache/scratch/loop1_resume_pytest_totals.txt` and `loop1_resume_pytest.xml`. This green result does **not** prove all AI safety contracts: independent review reproduced additional untested defects.

- Architecture: **REJECT**, report `C:/Users/sachi/AppData/Local/hermes/cache/scratch/review_ci_architecture.md`. Quote-free invented transcript IDs were accepted and fed confident readiness output; real adjudicator persisted rewritten specialist positions; typed verdict failure was test-invented metadata. Correct coverage and record actual production gaps before reconsideration.
- Security/Data: **NO APPROVAL**, report `C:/Users/sachi/AppData/Local/hermes/cache/scratch/review_security_loop1.md`. Inspector redirect handling can forward credentials; do not execute hosted tooling pending corrected tests/review. Snapshot shows missing schema objects, NOT exact migration history.
- Browser: **BLOCKED / NOT VERIFIED**. Existing harness could inherit secrets/load real dotenv, overwrite ordinary `.next`, and pass empty selection or a worked-around typing failure. No safe hermetic browser PASS is established. Do not execute it until isolation preflight and Security/Data approval.
- Python guard: useful deterministic settings/socket rail, not a universal OS egress sandbox. Subprocess/native networking remains outside its guarantee.
- G5: no Release Gatekeeper approval; no release or Loop 1 closure.

Scoped correction workstreams own disjoint files: AI-eval tests/checks; snapshot/Python/CI security rails; browser harness safety. Product-service fixes, hosted changes and broad intelligence implementation remain deferred.

## Baseline (measured 2026-10-04, repo root, head `8e3193f`)

| Check | Command | Result |
|---|---|---|
| Backend + contract tests | `.venv/Scripts/python.exe -m pytest` (repo root) | **862 passed, 13 skipped, 0 failed** (VERIFIED-EXECUTED) |
| Web typecheck | `npm --workspace @mirror/web run typecheck` | Fails **only** on generated `apps/web/.next/dev/types/validator.ts`; **0 errors in source** (KI-001) |
| Copy lint | `npm run lint:copy` | NOT RUN in bootstrap |
| Production build | `npm run build` | NOT RUN in bootstrap (RAM/time; see KI-001) |
| Browser / signed-in journey | — | NOT DONE: no QA user exists (KI-006) |
| AI behaviour eval | — | NOT AVAILABLE: no executable harness (KI-007) |

Notes: run pytest from the **repo root** (the root run also collects `tests/unit/*_frontend_contract.py`). In a non-TTY shell `node scripts/run-python.js` exits with "stdin is not a tty" (KI-002); call the venv interpreter directly.

## Gates

| Gate | Applies to | Required evidence | Blocking reviewer |
|---|---|---|---|
| **G0 Docs** | Docs-only change | Links valid; no duplicate source of truth | Orchestrator |
| **G1 Code** | Any backend/frontend change | Baseline pytest green (no new failures); typecheck source-clean; `lint:copy` if copy touched; focused new tests for new behaviour | QA Engineer, Architecture Reviewer |
| **G2 Data** | Migration / RLS / repository change | Forward + `.down.sql` where the pattern exists; migration contract test (`tests/unit/*_migration_contract.py` pattern); no destructive statement without human approval; RLS owner-scoped + anon revoked; compatibility with existing rows reasoned | Security/Data Reviewer, CTO. **Applying to hosted Supabase: human only.** |
| **G3 Candidate experience** | Any candidate-visible change | `lint:copy`; real browser pass at desktop + mobile widths where an auth path exists, else recorded NOT DONE; Journey Critic review (confusion, overload, dead ends, CTA clarity, terminology); no agent-system complexity exposed | Journey Critic, UX Lead |
| **G4 AI behaviour** | Prompt, model, agent contract, question generation, follow-up policy | Prompt version bumped (never edit a shipped version in place); structured-output validation tests; AI Evaluation scenarios run (fake provider for determinism; live provider only with approval); the honest-beginner protection (P5) stays green | AI Evaluation Agent, AI Systems Engineer | **STATUS 2026-10-04: PASS (fake-provider deterministic evaluation).** B5, B7, B12 accepted by independent Gatekeepers; B10 degrade-safe tests pass; 1204 passed/3 skipped/0 xfailed. Scope: deterministic evaluation only; no live-model evidence (debt KI-019, KI-017a). G1/G2/G3/G5 unaffected.
| **G5 Release** | Anything leaving the workspace | G1–G4 as applicable all passed; hosted-DB migration state confirmed by a human; `RELEASES.md` entry; known issues listed | **Release Gatekeeper** (only a human can waive, in writing, in `RELEASES.md`) |

## Independence rule

The author of a change is never its only verifier. QA, Architecture, Security/Data, Journey Critic, AI Evaluation are separate invocations from the implementer.

## Historical gates that could not run (superseded)

The executable AI-eval harness now exists, but independent review rejected its current verification claim; missing real-system guard coverage and known production defects are recorded above. Browser G3 remains BLOCKED on safe isolation and actual desktop/mobile execution. Neither test counts nor static inspection substitutes for these gates.
