# DR-0007 Candidate-driven interview planning
Status: **Bounded Loop 5A implementation reviewed; ready for PR review, not merge/release** · 2026-10-10 · Owner: CPO + CTO

## Problem

Loop 4 and Loop 4B remain BLOCKED because India-specific company-process research did not meet the publication gate. Candidates still need useful preparation without an approved company process. The owner has now directly authorized Loop 5A: build and locally verify candidate-driven preparation; do not start Loop 5B, change hosted Supabase, deploy, add research, or waive a failed gate. This instruction supersedes the stale “Do not start Loop 5” status sentence for this bounded objective only.

The initial architecture challenge required a precise candidate-stage snapshot, version/CAS rules, a read-consumer matrix, current-only notes lifecycle, and migration/compatibility behavior. This record defines those contracts. The additive migration, API/UI flow, local proofs, isolated browser journeys, and exact-head CI are complete for the bounded PR slice. CPO/CTO/Security/Data/QA/UX/Journey/AI Evaluation reviews report no remaining blocker within their reviewed scopes. Gatekeeper accepts the slice for PR review, not merge. This record does not approve a hosted migration, release, hosted operation, or deployment.

## Evidence

- `apps/api/app/target_repository.py`: owner-scoped immutable `InterviewBlueprint` rows; current PostgREST version allocation reads max then inserts; `MemoryTargetRepository` has a shared write lock.
- `apps/api/app/target_service.py`: current and historical blueprint reads use `read_candidate_stage_plan` for a coherent stage snapshot; only current reads include notes. `PUT /api/v1/targets/{id}/blueprint/stages` saves a complete CAS version. `start_round_practice` still pins the selected `blueprint_id` into a write-once session link.
- `apps/api/app/target_assessment_contract.py`: assessment resolves through the session-pinned blueprint rules version.
- `apps/api/app/research_content/taxonomy_v1.json`: role families `software_development_engineering` and `business_analysis`; existing rounds are role practice, not company stages.
- `supabase/migrations/20261004200000_loop2_candidate_targets.sql`: immutable blueprint trigger, owner RLS, browser reads, service-role writes.
- `supabase/migrations/20261005210000_target_prompt_completeness.sql`: generated question bodies and prompt manifests are server-only; client link reads are column-limited.
- **Verification evidence:** migration-contract tests 10/10 and disposable PostgreSQL 16.2 behavior verifier 90/90 (scratch-cluster cleanup verified); focused repository/routes tests 105/105 after the stale-409 regression; exact-head GitHub Actions run `37984246806` passed backend/copy/AI, frontend typecheck/build, and isolated browser jobs. The browser artifact passed 41/41 desktop and 41/41 mobile steps. Review scope and limitations are recorded in `../RECEIPTS/LR-0005-loop5a-candidate-driven-interview-planning.md`. No hosted database or deployment was accessed.
- The initial CTO and Security/Data reviews blocked the pre-API data draft; subsequent implementation and exact-head reviews resolved those findings. `BLUEPRINT_COLUMNS` remains deliberately pin-only for legacy consumers; the candidate-stage API reads the full immutable row through the coherent RPC. Do not apply the migration to any runtime; hosted rollout remains unapproved and untouched.

## Options considered

1. Keep general role practice only. Safest and shortest, but does not meet the authorized candidate-stage outcome.
2. Create a second mutable interview-plan/stage system. Rejected: duplicates the existing target blueprint, complicates session pinning and current-plan reads.
3. Store all mutable stages and notes inside the shared research catalog. Rejected: mixes candidate-owned input with shared company research.
4. Extend immutable owner-scoped target blueprints with stage snapshots and keep erasable notes in a narrowly scoped current-only table. **Selected.** The notes table owns no stage definitions, order, status, or history; the blueprint remains the only stage-plan/history model.

## Decision (proposed)

### Product flow and states

- Reuse existing company, role, seniority, geography, resume, role profile, plan, round, practice, and feedback paths. Do not add another target selector, dashboard, practice engine, runtime agent, prompt, rubric, scoring rule, or company-research claim.
- In the existing `PlanReadyStep`, show a compact, initially collapsed “What do you know about your interviews?” panel only when an active target exists. Offer “I know some stages” and “Not yet”; neither is required. “Not yet,” dismiss, missing target, or unavailable target storage keeps the existing general role-preparation and practice path available.
- Reuse the same editor in a visually separate candidate-owned section of `TargetOverview`, distinct from published guidance, so it can be revisited and edited later. Stage practice links use the existing target/role/round route and practice-start API.
- Render loading, empty, saved, retryable failure, stale-version conflict, archived-target, and unsupported-stage-mapping states. A failed save keeps the form draft in the mounted UI; a dirty form warns before navigation. Refresh after a successful save reloads the persisted plan. On a stale-version conflict, preserve the draft and require an explicit reload/reconciliation before retry; never silently overwrite another save.

### Canonical stage snapshot

Each immutable `interview_blueprints` row gains:

- `candidate_stage_state`: `NOT_ASKED`, `NOT_YET`, or `KNOWN`.
- `candidate_stage_order_known`: boolean.
- `candidate_stages`: JSON array, default `[]`.
- `candidate_stage_mapping_version`: `0` only for migrated legacy rows with no stages; `1` for new/edited stage plans.
- `candidate_stage_notes_revision`: non-negative integer; a counter only, never note text.

Each stage JSON object has **exactly** these fields: `stage_id` (stable canonical lower-case UUID text; UUID versions are not restricted, including UUIDv7), `kind`, `custom_label`, `certainty`, and `sequence`. Allowed kinds: `RECRUITER_SCREENING`, `TECHNICAL_INTERVIEW`, `CODING_EXERCISE`, `CASE_INTERVIEW`, `BEHAVIORAL_INTERVIEW`, `HIRING_MANAGER_DISCUSSION`, `PORTFOLIO_PROJECT_DISCUSSION`, `OTHER`. `OTHER` requires a trimmed 1–80 character custom label; other kinds require null. `certainty` is `SURE` or `UNCERTAIN`. Maximum 12 stages; IDs are unique. `KNOWN` requires 1–12 stages; `NOT_ASKED` and `NOT_YET` require none. When order is known, sequence is the contiguous set `1..N` and array order is canonical sequence order. When order is unknown, every sequence is null; array order is display order only and must never be represented as interview sequence. Unknown/unsupported stage types remain candidate input and never become official claims.

Validate the same invariants in Pydantic and SQL: exact object keys/types, enum values, UUID syntax, custom-label rules, unique IDs, array/text bounds, state/list consistency, and order consistency. Reject rather than coerce malformed snapshots. Existing rows receive safe empty defaults; existing `rules_version`, catalog/hash, target, and session pins are unchanged by the additive migration.

### Current-only notes and deletion

- Store optional notes (trimmed, maximum 500 characters) only in `candidate_stage_notes`, keyed by `(candidate_target_id, stage_id)` with `user_id` integrity. Notes are not in blueprint snapshots, historical session links, prompts, manifests, assessment context, or research/catalog storage.
- Notes are returned only with the current/latest candidate-stage plan. A historical blueprint read returns its stage metadata but no note text.
- Clearing a note deletes its row. Removing a stage deletes its note in the same database transaction as the new blueprint revision. Archiving a target deletes that target’s current notes; deleting a target/account follows owner-scoped FK cascades. Never retain a soft-deleted note.
- The notes table has RLS enabled, no `PUBLIC`/`anon`/`authenticated` grants or policies, and no direct browser reads or writes. Only tightly scoped server RPCs can read or mutate it. The API derives owner ID from authenticated identity and always scopes by owner plus target.

### Atomic write/retry contract

All blueprint appends and candidate-stage updates serialize on the `candidate_targets` row, so refresh, archive, and stage edits cannot allocate the same revision or overwrite newer stage state.

1. `append_target_blueprint_pin(user_id,target_id,expected_blueprint_version,catalog_version,catalog_sha256,match_state,rules_version)` locks the target `FOR UPDATE`, verifies exact owner and ACTIVE status, checks expected-version CAS, rejects catalog-version regression or a changed hash for the same catalog version, and idempotently returns an identical current pin. Otherwise it inserts version `latest+1`. It copies all candidate-stage fields and `candidate_stage_notes_revision` from the latest blueprint (or safe defaults when none exists), while applying the requested research/taxonomy pin. It never clears current notes.
2. `save_candidate_stage_plan(user_id,target_id,expected_blueprint_version,state,order_known,stages,notes)` locks the same target `FOR UPDATE`, checks owner and ACTIVE status, validates the complete desired snapshot and notes, then reads the latest blueprint and current notes.
3. If `expected_blueprint_version` is current and desired stage state/order/list/notes are unchanged, return the current version without writing. If any candidate stage field or note changes, insert exactly one immutable successor with every target/catalog/hash/match/rules pin copied unchanged, mapping version 1, and `candidate_stage_notes_revision` incremented only when notes changed. Synchronize notes in that same transaction; delete notes for removed stages and for explicit clears.
4. If the expected version is stale but the complete desired stage state/order/list/notes exactly equals current state, return the current version as an idempotent retry. Otherwise return a distinct stale-plan conflict; do not append, partially change notes, or overwrite the newer version.
5. SQL errors roll back both the blueprint row and all note changes. A target archive racing a save serializes on the target lock: save either commits before archive (whose trigger then clears notes) or sees ARCHIVED and makes no change.

The current-plan reader takes `FOR SHARE` on the owner-scoped target row before reading the immutable latest blueprint and current notes. The write/append/archive paths acquire conflicting target-row locks, so under Postgres `READ COMMITTED` a reader cannot pair an old blueprint with newer notes (or vice versa). Historical reads use the same lock but never load note rows.

All three service RPCs use schema-qualified objects, a fixed safe `search_path`, explicit owner checks, and `SECURITY DEFINER` only with those checks. Revoke execute from `PUBLIC`, `anon`, and `authenticated`; grant execute only to `service_role`. Revoke direct service-role writes to `interview_blueprints` and `candidate_stage_notes`; keep only the reads required by existing server code. The existing `SupabaseTargetRepository.create_blueprint` adapter calls `append_target_blueprint_pin` with `expected_blueprint_version` and reads back the exact returned version using an explicit pin-column projection. The current/historical `GET /api/v1/targets/{id}/blueprint[?version=N]` uses `read_candidate_stage_plan`; `PUT /api/v1/targets/{id}/blueprint/stages` uses `save_candidate_stage_plan` with the complete desired plan. The migration must not be applied to a runtime before these adapters are present. Keep blueprint UPDATE rejection unchanged. Add a composite target-owner key/FK or equivalent trigger so a note can never point to another owner's target. The read RPC returns the current full blueprint + current notes coherently; historical reads return stage metadata without notes.

### Complete reader/consumer matrix

| Reader | Required version/data |
|---|---|
| Current `GET /targets/{id}/blueprint` and `PlanReadyStep` / `TargetOverview` | Latest blueprint + candidate stage state + current-only notes + deterministic stage matches. Use no-store/current data; never mix with published guidance. |
| `GET /targets/{id}/blueprint?version=N` | Exact immutable stage snapshot N, no notes. |
| `TargetService.refresh` / `append_target_blueprint_pin` | New research pin plus latest candidate-stage metadata and notes revision; do not reset candidate input. |
| Round detail and plan round links | Existing pinned role taxonomy and round details. Stage matches are advisory links only; no company-specific assertion or changed rubric. |
| New practice start | Latest blueprint is pinned into the write-once `target_session_links.blueprint_id`; stage input only selects an existing role round and never changes prompt generation. |
| Existing/retried practice session, feedback, assessment, session-target read, generated-question read | Exact session-linked blueprint and immutable prompt manifest, never latest stage state or notes. No changes to round identity, prompt text, rubric, assessor set, adjudication, evidence, or score. |
| Research catalog | No candidate stage or note writes. Loop 4/4B statuses and publication gates remain unchanged. |

### Mapping version 1: stage kind → existing role round keys

This is deterministic, company-independent Mirror preparation. It uses only validated stage kind, role family, and the blueprint’s pinned taxonomy; stage order, company name, uncertainty, free text, and notes do not influence mapping. Every referenced round key must exist in the pinned role-family taxonomy; otherwise that match fails closed and the candidate still receives general role practice.

| Stage kind | `software_development_engineering` | `business_analysis` |
|---|---|---|
| `RECRUITER_SCREENING` | none | none |
| `TECHNICAL_INTERVIEW` | `coding_reasoning`, `system_design` | `requirements_and_stakeholders` |
| `CODING_EXERCISE` | `coding_reasoning` | none |
| `CASE_INTERVIEW` | none | `business_problem_solving` |
| `BEHAVIORAL_INTERVIEW` | `behavioural` | `behavioural` |
| `HIRING_MANAGER_DISCUSSION` | `behavioural` | `requirements_and_stakeholders`, `behavioural` |
| `PORTFOLIO_PROJECT_DISCUSSION` | `system_design`, `behavioural` | `requirements_and_stakeholders`, `behavioural` |
| `OTHER` | none | none |

When multiple candidate stages map to the same round, show the round once with the applicable stage labels. Unsupported mappings show an honest role-practice fallback; never invent a stage or a company sequence. Stage order is not practice order.

### Migration and rollback

Add one new additive migration; never edit applied migrations or touch hosted Supabase. Preserve existing owner RLS and prompt-manifest column restrictions. The migration contract covers JSON invariants, composite ownership, note membership, RLS/grants, private RPC execution, immutability, target locking, archival note cleanup, and rollback safeguards. Rollback must refuse if any non-default stage snapshot or note row would be lost; it must not use `CASCADE`. Run forward, concurrency, denial, and guarded rollback checks against a disposable PostgreSQL instance initialized solely for this test, never the shared/production database. Re-run the DB harness against the exact final migration bytes.

## Arguments / counterargument

- **For:** satisfies the direct Loop 5A authorization without waiting for company research; reuses existing target/blueprint/session/practice contracts; candidate provenance remains separate; immutable blueprint IDs protect historical sessions; notes can be erased without rewriting history.
- **Against:** adds substantial versioning and notes-lifecycle complexity to an optional flow. A single latest target can be ambiguous for a role with multiple company targets, and any RPC or RLS error must fail closed without blocking general role practice. Mitigation: use the existing target selector/role scope, show no stage editor without an unambiguous active target, keep “Not yet” and general practice immediate, serialize all writes on the target row, and test same-target concurrency, target ambiguity, archive races, and cross-owner reads.

## Acceptance criteria

A. **Stage workflow:** generic/custom stage add/edit/remove; stable IDs; certainty; known/unknown order; optional current-only notes; refresh recovery; retry and stale-conflict recovery.
B. **Planning/practice:** exact role-family mapping v1, no unsupported-stage invention, direct existing target/role/round practice links, completed practice feedback and return-to-plan path; no-stage and targetless general practice works.
C. **Privacy/data integrity:** two-owner isolation; owner/target constraints; service-only RPC; database shape validation; atomic CAS/idempotent retry; note deletion on clear/remove/archive; session-pinned history; no note/catalog/prompt/assessment leakage.
D. **Candidate experience:** copy lint; no duplicate target selection; accessible keyboard/screen-reader controls; desktop/mobile no overflow; save/refresh/error/retry/targetless states.
E. **AI/regression:** full deterministic AI-evaluation suite and regression suite; notes/company strings do not affect generated prompts, rubric selection, or scores; no prompt or assessment contract change.
F. **Research integrity:** no new research or catalog writes; candidate-entered information is always labeled as their own input; Loop 4 and 4B remain BLOCKED and all research holds remain HELD.
G. **Hosted:** NOT VERIFIED and NOT REQUIRED for local acceptance; no hosted migration, production deployment, or Loop 5B.

## Review state / revisit

The exact implementation SHA `4dc3d306c0ea6549360217cf72393d7bf03c9d1b` has scoped CPO, CTO, Security/Data, QA, UX/Journey, and AI Evaluation reviews; see `RECEIPTS/LR-0005-loop5a-candidate-driven-interview-planning.md`. Gatekeeper disposition is READY FOR PR REVIEW, NOT READY FOR MERGE. The owner accepted the pre-existing KI-020 typing-only practice limitation for PR #6 only; the issue remains open and this is not a general waiver. Revisit if database consumers require notes in history, if a requested stage cannot map safely to the pinned taxonomy, or if the isolated PostgreSQL tests cannot prove transaction/RLS invariants.
