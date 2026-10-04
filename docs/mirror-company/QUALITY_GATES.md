# Quality gates

## Evidence labels (mandatory in every report and receipt)

- **VERIFIED-EXECUTED** — a command, test, or browser/API run actually happened and its output was read.
- **STATIC-ONLY** — conclusion from reading code/docs. Never call this "verified".
- **NOT DONE** — stated explicitly, with the reason.

## Current Loop 1 status — BLOCKED on G2 only (Release Gatekeeper, 2026-10-04, branch loop1/trust-baseline @ e885130)

| Gate | Status | Evidence (VERIFIED-EXECUTED unless noted) |
|---|---|---|
| G0 repository integrity | **PASS** | Clean tree; `.env.example` identical to main; `apps/web/next-env.d.ts` untracked on purpose; no secrets in diff; `scratch/` excluded; 7 logical commits + follow-ups |
| G1 automated verification / real CI | **PASS** | GitHub Actions on Linux, runs 37196654767 (02afc70) and 37196926810 (e885130): Backend 1094 passed/1 skipped, AI evaluation 110 passed/2 skipped, copy lint 169 files 0 hits, wrapper tests 5/5, clean-checkout typecheck and production build, browser job. Local: 1204 passed/3 skipped/0 xfailed |
| G2 hosted data/security state | **BLOCKED** | Read-only re-verification: 4 repo objects absent on hosted (`interview_events`, `interview_debriefs`, `evidence_items`, `coverage_links`; not on any Loop 1 path); all Loop 1 tables present, no missing columns. RLS, policies, grants, triggers, migration ledger and migration `202610010002` are UNKNOWN (unreadable with available credentials). See HOSTED_SUPABASE_DRIFT.md |
| G3 browser/runtime | **PASS (CI job only)** | Ephemeral secret-free GitHub-hosted runner, real Chrome, fake Supabase Auth + fake Mirror API, real Next build; 36 steps desktop+mobile; no console errors/failed/denied/unmocked requests; no overflow. Strict result false only for acknowledged KI-020. Not exercised: Python assessment pipeline, unavailable-diagnostic UI (KI-022). Local execution stays blocked |
| G4 AI behaviour | **PASS (deterministic only)** | B5, B7, B12 independently ACCEPTED; AI evaluation 110 passed/2 skipped; no live-model evidence (KI-019) |
| G5 independent review | **PASS for Loop 1 scope** | Architecture, Security/Data, QA, Product all APPROVE, no blockers. Release-level G5 not met: no human confirmation of hosted migration state |

**Decision: LOOP 1 BLOCKED.** Minimum blocker (B1): the owner runs `scripts/ops/hosted_catalog_readonly.sql` (SELECT-only) in the Supabase SQL editor, saves the JSON, and states in writing whether migration `202610010002` is applied; the Gatekeeper then re-decides (G2 passes if RLS is enabled with owner-scoped policies and anon grants are revoked on the Loop 1 tables). Alternative: a human waives G2 in writing in `RELEASES.md`. No further engineering work is required for Loop 1.

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

## Gates that cannot run yet

The executable AI-eval harness now exists, but independent review rejected its current verification claim; missing real-system guard coverage and known production defects are recorded above. Browser G3 remains BLOCKED on safe isolation and actual desktop/mobile execution. Neither test counts nor static inspection substitutes for these gates.
