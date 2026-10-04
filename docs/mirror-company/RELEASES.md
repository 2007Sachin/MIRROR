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

### Loop 1 post-remediation disposition — 2026-10-04 (current)

**DECISION: closure PENDING final-branch CI and Release Gatekeeper. G2 PASS. No production release, Loop 1 acceptance or merge is claimed.** Branch `loop1/trust-baseline`, draft PR #1 remains unmerged. The last attributed local regression checkout is `3d08c9e`; this is not a final revision CI certification.

GATES: G0 reconciliation review PENDING · G1 local PASS / final-branch CI PENDING · G2 scoped PASS · G3 earlier CI-job PASS only (KI-020/KI-022 retained) · G4 deterministic PASS · G5 final decision PENDING.

HOSTED DB: narrowly authorized cleanup `20261004121203` and abandonment `20261004121238` verified independently; abandonment maps to repository `202610010002`, not a blanket applied-through claim. WAIVERS: none. Historical green CI runs 37196654767 and 37196926810 remain evidence for their original commits only; intervening historical red runs are not reclassified.

## Hosted remediation and verification — 2026-10-04 (current)

**G2 PASS; Loop 1 closure PENDING final-branch CI and Release Gatekeeper re-decision.** This is not Loop 1 acceptance, merge authorization or a production release. Earlier green CI runs certify their recorded commits only; historical red commits remain red.

- Owner explicitly retired the nutrition application and authorized destruction of its obsolete nutrition data. Architecture, Data and Security independently approved the exact two-table scope; Security's generic retention condition was resolved by that explicit authorization, not by an asserted backup. After fresh live identity/dependency-closure refresh against the approved local manifest, the parent executed only `DROP TABLE public.detailed_food_logs RESTRICT;` and `DROP TABLE public.nutrition_goals RESTRICT;`. No CASCADE, Mirror-row mutation, shared/auth/storage removal or blanket migration replay was authorized. Raw catalogs and the deletion manifest remain local and ignored.
- Hosted cleanup ledger: `20261004121203` / `retire_verified_nutrition_tables`. Repository parity file: `supabase/migrations/20261004121203_retire_verified_nutrition_tables.sql`; its two `IF EXISTS` drops are idempotent for clean checkouts where nutrition never existed. Deployed SQL lacked `IF EXISTS`: freshly verified table existence made the two forms equivalent for that execution. This records completed scoped cleanup, not permission to apply migrations elsewhere.
- Independent fresh SELECT-only Security/Data review (`scratch/g2_post_remediation_review.md`): both nutrition tables and their inventoried automatic dependents absent; 49 retained public Mirror tables retain RLS and no anon table grants. Retained Mirror/auth/storage security metadata, policies, grants, constraints and triggers preserved except the explicitly approved lifecycle-function replacement; all 123 public foreign keys preserved. No application rows or storage objects were read for that review.
- Hosted `20261004121238` / `session_abandoned` installs the exact existing repository `202610010002_session_abandoned.sql` enum/function behavior. Filename/ledger numbering differs: expected version drift, not missing behavior; do not replay the repository migration merely to force ledger equality. Four absent future-feature tables (`interview_events`, `interview_debriefs`, `evidence_items`, `coverage_links`) remain off Loop 1 paths and are not repaired or waived. Existing lowercase enum labels, `update_claim_status` service-role EXECUTE absence and excess authenticated story/practice privileges remain separately scoped debt.
- Attributed executed evidence: 127 lifecycle/consumer tests passed (memory/fake persistence); exact migration applied twice to a minimal isolated PostgreSQL fixture, with 225 real-trigger transition pairs and 10 immutable-budget checks passing each time. This is not the full hosted schema. **Isolated real-RPC integration EXECUTED** (`scratch/abandonment_rpc_integration.md`): actual FastAPI router → InterviewStateMachine → SupabaseSessionRepository → local psql transport adapter → exact `apply_interview_state_change` SQL → persisted state/events. CREATED/PREPARING/READY/ACTIVE return 200 with one event; retries are idempotent; foreign/anonymous endpoint requests return 404/401; invalid states return 409 unchanged. Concurrent calls return 200/200 with exactly one event; forced event-insert failure rolls back the complete session update atomically. Fresh repository reads projected through DashboardDiagnostic exclude abandoned sessions from activity/practice eligibility. SQL EXECUTE denial for anon/authenticated roles was checked separately. Minimal synthetic schema and synthetic authentication are used; this does not verify PostgREST/JWT/browser/hosted RLS/service-role grants, full home/readiness recomputation, the deferred pending-write race or live review enqueue.
- Post-remediation local regression (`scratch/post_remediation_regression.md`, checkout `3d08c9e`): 1204 passed, 3 skipped, 0 failed/0 xfailed; AI partition 110 passed/2 skipped, non-AI 1094 passed/1 skipped; Node tooling 5 passed and browser-safety 16 passed; frontend typecheck, copy lint (169 files, 0 banned hits, 3 soft warnings), production build (11/11 static pages) all exit 0. These are attributed local executions, not a new browser journey, live-model run or final-branch GitHub CI.

KI-016..022 residual debt is retained without fixes or waivers (KI-021's original G2 blockers are resolved, not a blanket compatibility certification). Remaining closure work: review this reconciliation and migration parity file, obtain real CI on the final branch revision, then obtain the Gatekeeper's explicit final decision. Commit/push and exact-final-HEAD CI evidence are recorded separately in ignored `scratch/final_branch_ci.json` and `.md`; no merge, deployment, Loop 2 or acceptance is authorized by this documentation update.

### Loop 1 interim disposition — 2026-10-04 (superseded)

**DECISION: REJECTED for production release.** Independent Release Gatekeeper adjudication is STATIC-ONLY, based on attributed execution evidence in the Architecture and Security/Data follow-up reports. Scoped offline verification infrastructure is accepted, but Loop 1 remains **BLOCKED / IN PROGRESS**, not closed-with-blockers.

G0 closure documentation required status reconciliation and a full link/source audit remains NOT DONE. G1 scoped infrastructure is accepted; complete fresh platform/frontend gate evidence is not established. G2 is N/A for the no-migration slice, with hosted catalog/ledger/RLS prerequisites BLOCKED. G3 real browser verification is BLOCKED. G4 product contracts FAIL: five unmasked tests fail across B5/B7/B12. **G5 REJECTED; WAIVERS: NONE.** No release, push/deployment, hosted mutation, browser-isolation bypass, or Loop 2 is authorized.

Parent full offline run: 1060 passed, 3 skipped, 5 strict xfailed. Expected failures disclose defects and do not satisfy requirements. Gatekeeper report: `C:/Users/sachi/AppData/Local/hermes/cache/scratch/release_gatekeeper_loop1.md`. Receipt: `RECEIPTS/LR-0001-trust-baseline.md`.

Recommended next bounded objective: B5 evidence-ID validation before assessment persistence/publication. A human/CPO decision is required to continue, re-scope or suspend the trust-baseline objective; no product implementation starts from this record alone.

No production release has been made by this organization layer. (At that time no GitHub/Linux execution was recorded; see the final disposition above.) Deployment target/process and live commit remain unverified; establish those before any future release approval.
