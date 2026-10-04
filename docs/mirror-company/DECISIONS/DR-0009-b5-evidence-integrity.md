# DR-0009 — B5-only assessment evidence integrity

Status: **AUTHORIZED by owner; BLOCKED pending legacy-availability decision (no production implementation yet)**. Date: 2026-10-04. Owners: AI Systems Engineer + Backend Engineer. Independent reviewers: AI Evaluation, Security/Data, Architecture, Release Gatekeeper.

## Trace and policy blocker

AI Systems and Backend completed production flow/consumer traces (`scratch/b5_ai_trace.md`, `scratch/b5_backend_trace.md`). Fresh quote-free IDs, cached specialist reuse, direct reports and existence-only final-result cache can bypass evidence validation. No schema change is required for fresh/context validation, but stored final results contain no specialist-cohort/original-context provenance. Current specialist eligibility cannot certify historical final readiness.

CPO/architecture review (`scratch/b5_legacy_policy.md`) approves narrow fresh reject-before-store and cached-current-context validation preserving useful insufficiency. It requires an owner decision before blanket unavailability of unverifiable legacy diagnostics: such containment can also hide valid historical reports. No automatic deletion/recomputation/inference or invented low score is permitted. Production code remains unchanged pending this decision; B5 remains FAIL/BLOCKED and Loop1 remains BLOCKED / IN PROGRESS.

## Scope and invariant
Model confidence or a produced identifier does not establish evidence validity. Evidence must deterministically resolve to actual candidate-authored persisted content available in the correct candidate/session/interview assessment context. Trace the real production data flow first, identify the trust boundary, then apply the smallest test-driven domain/service fix. Preserve useful uncertainty where the current contract permits it; never fabricate replacement evidence or match unrelated content.

## Authorized verification
Expand the matrix for valid/multiple, nonexistent/fabricated, cross-session/candidate, interviewer-authored, malformed/empty, mixed, duplicate and unavailable evidence where domain-supported. Include a confident adversarial output referencing a nonexistent answer. Run targeted B5, assessment/adjudication/downstream readiness/progress tests, full Python suite and production-contract AI evaluations. Remove B5 strict xfails only after the unchanged behavioral assertions pass against actual production services. Remaining failures must stay explicit.

## Limits
No Interview Intelligence, research, browser work, schema/Supabase changes, hosted mutation, redesign, unrelated refactors or Loop2. If a migration is necessary STOP for CTO/Security explanation and owner decision. No commit/push/release authorization. Loop1 stays BLOCKED / IN PROGRESS and production release REJECTED regardless of B5 acceptance.

## Baseline evidence
Orchestrator executed existing B5 tests unmasked: **2 failed, 14 deselected**, exit1, 1.50s. Unknown quote-free IDs produced 3 stored assessments; aggregate published AVAILABLE, readiness82/range78–86. Evidence: `C:/Users/sachi/AppData/Local/hermes/cache/scratch/b5_baseline_red.txt`. An initial mismatched selector exited5 (zero selection) and was corrected; it was not treated as defect evidence.

## Completion
Production trust-boundary fix, full enumerated file changes and exact commands/counts, independent adversarial/ownership/architecture review, B5-only Gatekeeper disposition and updated Loop1 receipt. Stop after reporting; no automatic next objective.
