# Roadmap and backlog

## Current disposition — 2026-10-10

Loop 1–3 remain accepted only within their recorded scopes. Loop 4/4B remain **BLOCKED/HELD**: no India-scoped research claim passed publication review, and the target company/role slices remain HELD. Separately, owner-authorized Loop 5A is implemented at `4dc3d306c0ea6549360217cf72393d7bf03c9d1b`; PR #6 is ready for review but not merge/release. Exact-head CI run `37984246806` passed all three required jobs, including the isolated synthetic desktop/mobile journey (41/41 steps per viewport). KI-020 is accepted by the owner as a pre-existing limitation for PR #6 only and remains open. Hosted migration/integration is NOT VERIFIED; no hosted changes, deployment, new research, merge, or Loop 5B. See `RECEIPTS/LR-0005-loop5a-candidate-driven-interview-planning.md`.

> The roadmap below is the pre-Loop2 planning snapshot. Its milestone/backlog statuses are historical and do not supersede the current disposition above.

Order is by dependency first, candidate value second. One objective in flight at a time (`LOOP.md`). Items marked ⛔ need human approval before work starts.

## Original planning rationale (historical pre-Loop2)

Mirror 2.0's value (company/round-aware preparation) rests on an intelligence layer and a multi-round blueprint, both of which add schema and AI behaviour. The repo cannot yet *prove* those changes are safe: no CI, no signed-in QA path, no executable AI eval, unknown hosted-DB state. So the trust baseline comes first, kept small; then a thin vertical slice proves the data model with curated, verified data before any pipeline or scale.

## Original milestone plan (historical pre-Loop2)

| # | Milestone | Candidate value | Depends on | Gate focus |
|---|---|---|---|---|
| M0 | Org bootstrap (this folder) | Indirect | — | G0 — **done (LR-0000)** |
| M1 | **Trust baseline** (Loop 1, LR-0001): CI; deterministic typecheck/build; test isolation from `.env`/network; AI-eval suite; hermetic browser QA; read-only hosted-Supabase inspection | Indirect, but unblocks safe change | — | G1, G3, G4 — **IN PROGRESS: final test reconciliation, successful browser execution and independent reviewer verdicts still required; no Loop 1 closure or release approval yet** |
| M1b | **Journey hygiene** (found by the Product Critic; cheap, candidate-visible, and M4's brief is moot if nobody reaches it): make Pressure Test and the interview record/brief/debrief reachable (`/roles/[id]` redirects to `/plan`); stop repeat drills asking identical questions; make the onboarding company field do something or remove it; send empty states to the mode choice instead of a 20-minute default | High | M1 | G1, G3 |
| M1c | ⛔ **Hosted compatibility decision**: inspect missing-object drift and migration ledger before proposing reconciliation for `202609300001`, `202610010001`, `202610010002`, `202610010003` (lifecycle-trigger replacement requires semantic review); no automatic replay; decide the shared-project question (`HOSTED_SUPABASE_DRIFT.md` D3) | Unblocks shipping HEAD | M1 | G2, G5 |
| M1d | **Skeptic hardening** (two defects recorded as strict xfails in `tests/ai_eval`): the false-contradiction guard is bypassed by honest phrasing such as "I never used a database", and accusatory model text is forwarded to the interviewer unchanged | High (protects honest candidates) | M1 | G4 |
| M2 | Taxonomy v1 (round types, competencies, role families, seniority, geography) + schema proposal review (docs only) | Indirect | M0 | G0, Architecture/Security review |
| M3 | ⛔ **Target model**: company + geography + seniority on the candidate target; additive migration | Medium: Mirror finally knows *where* you're interviewing | M1, M2, DR-0004 | G2, G3 |
| M4 | ⛔ **Intelligence v0**: curated, verified claims for 3–5 slices from official sources; provenance-labelled wording in brief + Interview Map | High: first honest company-specific preparation | M3, DR-0005 | G2, G3, G4 |
| M5 | Multi-round **blueprint** + round-scoped sessions + per-round assessment + cross-round adjudication | High | M4 | G2, G3, G4 |
| M6 | Question Intelligence: Question Designer, validators, per-competency difficulty state, communication assessor, persisted follow-up reasons | High | M5 | G4 |
| M7 | Progress model across round/competency/company/skill/family | High | M5, M6 | G3 |
| M8 | Research pipeline + refresh + scale (⛔ scraping scope) | Compounding | M4 | Research loop |

Parallel low-cost hygiene (can ride along, never blocks; the first two were already found by Loop 1): fix `skeptic_repository.py:426` (`users` was renamed `profiles`); add a migration-contract test asserting every public table has RLS and no anon grant (prerequisite for any `ii_*` migration); split `main.py` by the existing `routes_*.py` pattern; resolve `/plan` vs `/roles/[id]` and `/reflect` vs `/progress` naming; retire or document dormant legacy tables after M1's read-only DB inspection; fix doc drift (KI-003); FastAPI lifespan migration.

## Earlier prioritized backlog (historical; not current authorization)

1. M1c hosted-DB rollout decision (⛔ owner) and owner-run `scripts/ops/hosted_catalog_readonly.sql`
2. M1b journey hygiene (reachability, repeat drills, company field)
3. M1d Skeptic false-contradiction guard (TDD from the two strict xfails)
4. M2 taxonomy v1 draft (map round types to existing `RoundKind`)
5. M3/M4 vertical slice specification (CPO + Head of II + UX Lead); DR-0004/0005 approved with constraints

## Earlier implementation recommendation (superseded)

Loop 1 (M1) is **in progress, not closed**. The interrupted review batch produced no saved verdicts; browser PASS and a Release Gatekeeper decision remain unproven. The following is a proposed post-Loop-1 backlog, not authorization to begin another objective. Recommended **Loop 2**: M1b journey hygiene + M1d Skeptic guard (both small, both protect candidates, both now have an executable verification path), run alongside the owner's M1c rollout decision; then the M3→M4 vertical slice for one curated company×role. DR-0004 (schema in principle) and DR-0005 (company research, with provenance constraints) are approved by the owner; **no `ii_*` schema is to be created until the DR-0004 preconditions are met** (hosted state inspected and reconciled, RLS/ownership design reviewed, one research slice demonstrating the data shape, Architecture and Security/Data approval).
