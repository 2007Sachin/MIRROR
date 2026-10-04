# Hosted Supabase drift report (read-only inspection)

Inspected: 2026-10-04 during Loop 1 (still open). The owner authorized read-only inspection. **Nothing on the hosted project was modified or repaired.** Independent Security/Data review rejected the original overstatements and found a credential-redirect vulnerability in the inspector; do not run it again until the fix is independently approved. No credential disclosure was demonstrated; the reviewer reproduced header forwarding with synthetic requests and no network.

## Method (and its limits)

- Tool: `scripts/ops/hosted_readonly_snapshot.py`. Sends **only HTTP GET/HEAD** (enforced in code). Credentials are read from the local `.env` into memory and never printed or stored. Row *counts* only (HEAD + `Content-Range`); no application row data was requested.
- Sources used: PostgREST OpenAPI (exposed tables, columns, RPC functions), Storage bucket list, filtered count probes.
- **Not reachable with the credentials available to Hermes:** applied-migration list (`supabase_migrations.schema_migrations` → HTTP 406 over PostgREST), RLS policies, triggers, indexes, constraints, function bodies/`SECURITY DEFINER` flags, grants (postgres-meta endpoints → HTTP 404). These are **BLOCKED** pending one of: a read-only database connection, a Supabase access token, or the owner running `scripts/ops/hosted_catalog_readonly.sql` (SELECT-only) in the SQL editor and saving the JSON result to `.runtime/hosted_catalog.json`.
- Therefore **migration application history is UNKNOWN**. Missing exposed schema objects establish a compatibility gap, not proof that a particular migration was never applied. The retained snapshot contains no enum-label or filtered-status probe results; earlier enum-probe claims are unverified and excluded below.

## Findings

| # | Finding | Evidence | Severity |
|---|---|---|---|
| D1 | **Required objects are absent from the observed exposed schema:** `interview_events`, `interview_debriefs`, `evidence_items`, `coverage_links`. Corresponding repo migrations include `202609300001_interview_events`, `202610010001_career_evidence`, `202610010003_coverage_links`; their application history is unknown. `202610010002_session_abandoned` enum/trigger compatibility remains unverified. | Retained OpenAPI snapshot lacks these four tables; migration ledger inaccessible. No retained enum-probe evidence. | **High compatibility risk** for repo paths requiring these objects; confirm catalog and deployment state before rollout |
| D2 | Observed tables/columns overlap earlier repo migrations. This does not establish completion of every earlier migration or a deployed commit. `202609250001` grants cannot be confirmed. | Limited exposed-schema observation; constraints, triggers, policies, grants and ledger unreadable | Info / verification gap |
| D3 | **Tables unmanaged by this repository are exposed:** `detailed_food_logs`, `nutrition_goals` (no corresponding repo migration found). | OpenAPI definitions | **Potential cross-application boundary risk**. Ownership and actual grants are uninspected; confirm co-hosting with the owner. No test mutation is permitted on this project. |
| D4 | Legacy tables exist on hosted and had **0 rows at inspection**: `question_bank`, `question_reports`, `rubrics`, `outcomes`, `calibration_runs`, `golden_cases`, `colleges`, `roles`, `skills` | HEAD counts | Emptiness does NOT establish safe retirement/repurposing; other dependencies and consumers are unknown. Requires separate review and authorization. |
| D5 | `users` is absent and `profiles` present: **expected**; migration `202608310002` renames `users` → `profiles` | repo migration lines 7-8 | None |
| D6 | Real data exists: `sessions` 32 rows, `profiles` 6, `stories` 2, `answer_attempts` 0. A synthetic QA user must not be created here | counts | Constraint |
| D7 | Storage: 2 buckets, both private: `private-resumes` (8 MiB; pdf/docx) and `private-interview-audio` (10 MiB; webm/ogg/mp4/wav/mpeg) | `/storage/v1/bucket` | Matches docs/privacy claims at bucket level; storage **policies** not inspected |
| D8 | 26 RPC functions are exposed through the REST API surface (list in the snapshot) | OpenAPI paths | Review which are callable by `anon`/`authenticated` once catalog access exists |

## Not drift but worth knowing

Trigger/internal functions (e.g. `enforce_session_lifecycle`, `*_verify_ownership`) do not appear in the REST function list because they are not callable through the API; their absence there is **not** evidence they are missing.

## Recommended next steps (each needs an explicit decision through the loop; none was performed)

1. Owner runs `scripts/ops/hosted_catalog_readonly.sql` and saves the JSON; Hermes then diffs it against the statically derived expected schema (policies, triggers, grants, enums, indexes) and extends this report.
2. Establish catalog and migration-ledger evidence before deciding reconciliation or rollout. Review `202609300001`, `202610010001`, `202610010002`, `202610010003` individually with G2 and rollback notes; **do not automatically replay them**. `202610010002` replaces a lifecycle trigger function, so describing all four as merely additive understates semantic risk. Do not deploy paths depending on missing objects.
3. Decide whether Mirror should move to its own Supabase project (D3), or at minimum confirm the nutrition app's tables are intentionally co-hosted and covered by RLS.
4. Investigate dependencies/ownership of empty legacy tables (D4); any retirement or repurposing requires a separate decision and explicit authorization.
