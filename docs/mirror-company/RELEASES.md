# Releases

Release authority: Release Gatekeeper (`agents/release-gatekeeper.md`); only a human can waive a failed gate, in writing, in this file.

## Release record template

```
RELEASE: <id/date>   HEAD: <sha>   SCOPE: <what changes for the candidate>
GATES: G1 <evidence> · G2 <evidence/n.a.> · G3 <evidence/n.a.> · G4 <evidence/n.a.>
HOSTED DB: migrations applied through <version> — confirmed by <human> on <date>
KNOWN ISSUES SHIPPED: <KI ids>      WAIVERS: <none | who, what, why>
DECISION: APPROVED | REJECTED   BY: Release Gatekeeper
```

## History

### Loop 4 — rejected / blocked (2026-10-08; no product release)

**DECISION: REJECTED. LOOP 4: BLOCKED.** Gatekeeper decisions `deleg_28547ba5` and confirmatory review `deleg_5328d144` at reviewed HEAD `e76176c59cb6b742e6269457c6f92b9c26986d2f`. A — PASS, STATIC-ONLY (no catalog additions; validator not rerun) · B — FAIL / NOT DONE · C — HELD (0 approved targets; all five requested company/role groups—six level-specific target slices—HELD) · D — NOT VERIFIED. G0 — PASS, STATIC-ONLY (both decisions recorded; docs reconciled) · G1 — NOT RUN (no Loop 4 suite or exact-head CI) · G2 — NOT RUN / N.A.; hosted state NOT VERIFIED · G3 — NOT DONE (no browser journey) · G4 — NOT RUN (design-only reviews are not execution evidence) · G5 — REJECTED.

Amazon SDE II candidate sources remain UNVERIFIED; Accenture guidance is general only and not India-specific. No product code or hosted operation occurred. This is a documentation-only disposition, not a product release. KNOWN ISSUES SHIPPED: none. WAIVERS: none. The receipt records product tests/browser/CI as NOT RUN; any documentation-only CI/merge evidence is distinct from product acceptance.

### Loop 3 local assessment slice — repository merged (2026-10-08; not a production release)

**DECISION: LOOP 3 LOCAL SLICE ACCEPTED.** Gatekeeper A PASS/B PASS; final AI Evaluation and Security/Data re-reviews PASS. Implementation commit `ae5ecf7cf013d0d86f80894c2192d0834085d47e`; PR #3 squash-merged into `main` as `a806aae69103db16c7543914fa62af05fad0739e`.

GATES: G0 closure records updated in this receipt commit · G1 PR CI `37708487534` passed all three required jobs at the exact implementation SHA; post-merge `main` CI `37708775297` passed all three jobs at the merge SHA · G2 scoped local tests only; hosted migration/integration NOT VERIFIED · G3 isolated synthetic browser CI and local copy tests only · G4 deterministic tests only (1,508 passed, 3 skipped; no live model) · G5 Gatekeeper A/B PASS.

HOSTED DB: no hosted access, migration, integration, or hosted writes were performed. Research remains HELD. Production release/deployment NOT APPROVED; no deployment occurred. Loop 4 was separately authorized by a later owner instruction and is recorded as BLOCKED in `RECEIPTS/LR-0004-verified-interview-intelligence-expansion.md`; this Loop 3 entry grants no release approval for it.

### Loop 2 local-slice disposition — 2026-10-06 (not a production release)

**DECISION: LOOP 2 LOCAL SLICE ACCEPTED** by independent Release Gatekeeper at implementation HEAD `635209c43fe884c92ed62b0c03b449247354afc3`. A — local architecture/product PASS; B — Amazon SDE I/SDE II India HELD; C — hosted release readiness NOT VERIFIED. This decision authorizes the bounded local hypothesis and, under the owner's explicit instruction, repository PR/merge only after fresh exact-final-HEAD CI and repository-policy checks. It is not production release approval.

GATES: G0 current records reconciled · G1 exact implementation CI run `37509014604` PASS at `635209c43fe884c92ed62b0c03b449247354afc3` (later docs-only HEADs require fresh CI) · G2 disposable local PostgreSQL 16 32/32 PASS; hosted NOT VERIFIED · G3 isolated synthetic Chrome 72/72 desktop/mobile steps pass under acknowledged-KI policy; strict result remains false for KI-020 · G4 deterministic synthetic/fake-provider PASS; no live-model or India validation · G5 independent Architecture, Security/Data, Data/Supabase, CPO, AI Evaluation, QA, Journey Critic PASS; Gatekeeper A PASS/B HELD/C NOT VERIFIED.

HOSTED DB: No Loop 2 migration or hosted integration was performed. Applied-through state for this Loop 2 migration and hosted PostgREST integration are NOT VERIFIED.

KNOWN ISSUES SHIPPED: KI-020, KI-022, KI-023, KI-024. WAIVERS: none. **PRODUCTION RELEASE: NOT APPROVED.** Amazon SDE I/SDE II India remain HELD. No deployment or Loop 3. Evidence details: `RECEIPTS/LR-0002-amazon-swe-india-local-slice.md`.

### Loop 1 post-remediation disposition — 2026-10-04 (historical)

**DECISION: LOOP 1 ACCEPTED by independent final Release Gatekeeper.** Branch `loop1/trust-baseline`, PR #1 remains unmerged at transcription; final commit CI and safe merge-commit handoff required. Reviewed HEAD `8257985ff1be7f52af34e49162b0d40b5bd6c69a`, real Linux CI `37202320540` success/all three jobs. Local regression at `3d08c9e` is separately attributed, not final-commit certification. No production release.

GATES: G0 PASS · G1 exact-reviewed-HEAD real CI PASS (new transcription CI required) · G2 scoped PASS · G3 isolated synthetic desktop/mobile PASS (KI-020/KI-022 retained) · G4 deterministic PASS · G5 independent final Loop 1 closure PASS.

HOSTED DB: narrowly authorized cleanup `20261004121203` and abandonment `20261004121238` verified independently; abandonment maps to repository `202610010002`, not a blanket applied-through claim. WAIVERS: none. Historical green CI runs 37196654767 and 37196926810 remain evidence for their original commits only; intervening historical red runs are not reclassified.

## Hosted remediation and verification — 2026-10-04 (historical Loop 1)

**LOOP 1 ACCEPTED — independent final Release Gatekeeper decision, 2026-10-04.** G0/G1/G2/G3/G4/G5 PASS within the bounded trust-baseline and approved remediation scope. Reviewed HEAD `8257985ff1be7f52af34e49162b0d40b5bd6c69a`; independently read real Linux CI run `37202320540` (https://github.com/2007Sachin/MIRROR/actions/runs/37202320540), completed/success with all three jobs successful at that exact SHA: frontend typecheck/build; backend/copy/AI evaluation; isolated synthetic browser critical path. Decision evidence: ignored `scratch/final_gatekeeper_final.md`. This transcription creates a new commit: fresh exact-final-HEAD CI must pass before merge; the reviewed run cannot certify that new SHA. PR #1 is unmerged at transcription. Owner authorizes final documentation commit/push and safe merge-commit finalization only after CI and repository-policy checks. No production release, deployment, further hosted mutation, debt waiver or Loop 2 is authorized. Historical red commits remain red.

- Owner explicitly retired the nutrition application and authorized destruction of its obsolete nutrition data. Architecture, Data and Security independently approved the exact two-table scope; Security's generic retention condition was resolved by that explicit authorization, not by an asserted backup. After fresh live identity/dependency-closure refresh against the approved local manifest, the parent executed only `DROP TABLE public.detailed_food_logs RESTRICT;` and `DROP TABLE public.nutrition_goals RESTRICT;`. No CASCADE, Mirror-row mutation, shared/auth/storage removal or blanket migration replay was authorized. Raw catalogs and the deletion manifest remain local and ignored.
- Hosted cleanup ledger: `20261004121203` / `retire_verified_nutrition_tables`. Repository parity file: `supabase/migrations/20261004121203_retire_verified_nutrition_tables.sql`; its two `IF EXISTS` drops are idempotent for clean checkouts where nutrition never existed. Deployed SQL lacked `IF EXISTS`: freshly verified table existence made the two forms equivalent for that execution. This records completed scoped cleanup, not permission to apply migrations elsewhere.
- Independent fresh SELECT-only Security/Data review (`scratch/g2_post_remediation_review.md`): both nutrition tables and their inventoried automatic dependents absent; 49 retained public Mirror tables retain RLS and no anon table grants. Retained Mirror/auth/storage security metadata, policies, grants, constraints and triggers preserved except the explicitly approved lifecycle-function replacement; all 123 public foreign keys preserved. No application rows or storage objects were read for that review.
- Hosted `20261004121238` / `session_abandoned` installs the exact existing repository `202610010002_session_abandoned.sql` enum/function behavior. Filename/ledger numbering differs: expected version drift, not missing behavior; do not replay the repository migration merely to force ledger equality. Four absent future-feature tables (`interview_events`, `interview_debriefs`, `evidence_items`, `coverage_links`) remain off Loop 1 paths and are not repaired or waived. Existing lowercase enum labels, `update_claim_status` service-role EXECUTE absence and excess authenticated story/practice privileges remain separately scoped debt.
- Attributed executed evidence: 127 lifecycle/consumer tests passed (memory/fake persistence); exact migration applied twice to a minimal isolated PostgreSQL fixture, with 225 real-trigger transition pairs and 10 immutable-budget checks passing each time. This is not the full hosted schema. **Isolated real-RPC integration EXECUTED** (`scratch/abandonment_rpc_integration.md`): actual FastAPI router → InterviewStateMachine → SupabaseSessionRepository → local psql transport adapter → exact `apply_interview_state_change` SQL → persisted state/events. CREATED/PREPARING/READY/ACTIVE return 200 with one event; retries are idempotent; foreign/anonymous endpoint requests return 404/401; invalid states return 409 unchanged. Concurrent calls return 200/200 with exactly one event; forced event-insert failure rolls back the complete session update atomically. Fresh repository reads projected through DashboardDiagnostic exclude abandoned sessions from activity/practice eligibility. SQL EXECUTE denial for anon/authenticated roles was checked separately. Minimal synthetic schema and synthetic authentication are used; this does not verify PostgREST/JWT/browser/hosted RLS/service-role grants, full home/readiness recomputation, the deferred pending-write race or live review enqueue.
- Post-remediation local regression (`scratch/post_remediation_regression.md`, checkout `3d08c9e`): 1204 passed, 3 skipped, 0 failed/0 xfailed; AI partition 110 passed/2 skipped, non-AI 1094 passed/1 skipped; Node tooling 5 passed and browser-safety 16 passed; frontend typecheck, copy lint (169 files, 0 banned hits, 3 soft warnings), production build (11/11 static pages) all exit 0. These are attributed local executions, not a new browser journey, live-model run or final-branch GitHub CI.

KI-016..022 residual debt remains unwaived (KI-021's original G2 blockers are resolved, not blanket compatibility certification). G2 acceptance retains isolated SQL-adapter/PostgREST/JWT/hosted-RLS/full-readiness limits; G3 is isolated synthetic desktop/mobile only, with KI-020/KI-022 and local runtime blockage retained; G4 is deterministic only, not live-model or speech-quality certification. Gatekeeper G5 affirmatively accepts Loop 1 closure. Fresh exact-final-HEAD CI and policy-compliant merge remain required. Final branch/main SHAs, CI jobs and actual PR merge status will be recorded in ignored `scratch/loop1_merge_receipt.json` and `.md`, avoiding a premature merged claim or circular merge-SHA documentation commit. No deployment, hosted write or Loop 2.

### Loop 1 interim disposition — 2026-10-04 (superseded)

**DECISION: REJECTED for production release.** Independent Release Gatekeeper adjudication is STATIC-ONLY, based on attributed execution evidence in the Architecture and Security/Data follow-up reports. Scoped offline verification infrastructure is accepted, but Loop 1 remains **BLOCKED / IN PROGRESS**, not closed-with-blockers.

G0 closure documentation required status reconciliation and a full link/source audit remains NOT DONE. G1 scoped infrastructure is accepted; complete fresh platform/frontend gate evidence is not established. G2 is N/A for the no-migration slice, with hosted catalog/ledger/RLS prerequisites BLOCKED. G3 real browser verification is BLOCKED. G4 product contracts FAIL: five unmasked tests fail across B5/B7/B12. **G5 REJECTED; WAIVERS: NONE.** No release, push/deployment, hosted mutation, browser-isolation bypass, or Loop 2 is authorized.

Parent full offline run: 1060 passed, 3 skipped, 5 strict xfailed. Expected failures disclose defects and do not satisfy requirements. Gatekeeper report: `C:/Users/sachi/AppData/Local/hermes/cache/scratch/release_gatekeeper_loop1.md`. Receipt: `RECEIPTS/LR-0001-trust-baseline.md`.

Recommended next bounded objective: B5 evidence-ID validation before assessment persistence/publication. A human/CPO decision is required to continue, re-scope or suspend the trust-baseline objective; no product implementation starts from this record alone.

No production release has been made by this organization layer. (At that time no GitHub/Linux execution was recorded; see the final disposition above.) Deployment target/process and live commit remain unverified; establish those before any future release approval.
