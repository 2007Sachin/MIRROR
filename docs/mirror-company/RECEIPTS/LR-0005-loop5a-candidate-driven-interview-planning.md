# LR-0005 — Loop 5A candidate-driven interview planning

**Disposition:** READY FOR PR REVIEW; NOT MERGED / NOT RELEASED
**As of:** 2026-10-10
**Implementation SHA:** `4dc3d306c0ea6549360217cf72393d7bf03c9d1b`
**Branch / PR:** `loop5a/candidate-driven-interview-planning` / PR #6, base `main`
**Authorization boundary:** Loop 5A only. No Loop 5B, new research, hosted database changes, deployment, or release.

## Outcome

Implemented candidate-owned interview-stage planning using immutable target blueprint snapshots and current-only private notes, with deterministic advisory mappings into existing role practice. The flow includes onboarding capture, target overview editing, save/refresh recovery, target-pinned practice and feedback, stale-version reconciliation, note clearing/removal, and a general-role fallback when stage/target data is absent or unsupported.

The final stale-save review found an API adapter defect: `_raise_rpc_error` mapped every HTTP 409 to generic `TargetConflict` before inspecting the specific `stale candidate stage plan` message. Commit `4dc3d30` fixes this ordering and adds a regression for both typed stale conflict and generic 409 fallback. The earlier concern about mapping-version metadata was checked against DR-0007: mapping version is 1 for edited stage plans; notes revision increments only when notes change. SQL and memory implementations match that contract.

The owner explicitly accepted the existing `typing-only-room-stuck-after-answer` behavior as a documented, pre-existing limitation for this PR only. The issue remains open in KI-020 and is not claimed fixed or generally waived.

## Verification evidence

- **Exact-head GitHub Actions:** run `37984246806` for implementation SHA `4dc3d306c0ea6549360217cf72393d7bf03c9d1b`; all required jobs succeeded: backend/copy lint/AI evaluation, frontend typecheck/production build, isolated synthetic browser critical path.
- **Browser artifact:** 82 total steps, all assertions passed: desktop 41/41 at 1280×800; mobile 41/41 at 390×844. No overflow, page errors, console errors, failed requests, bad responses, denied requests, or unmocked API calls. The runner records KI-020 as the single acknowledged known issue. This is fixture-backed UI coverage, not a real-backend/browser or live-provider test.
- **Focused local API tests:** `apps/api/tests/test_target_repository.py` and `apps/api/tests/test_target_routes.py`: 105 passed. The 409 regression test confirms exact stale message → `StaleStagePlan` and unrelated 409 → `TargetConflict`.
- **Deterministic AI/persona suite:** 127 passed, 2 skipped, 7 deprecation warnings, on the exact implementation SHA; no live provider was exercised.
- **Database contract evidence:** migration-contract tests 10/10 and disposable PostgreSQL 16.2 verifier 90/90 were previously run against the unchanged Loop 5A migration. No hosted database was accessed or modified.
- **Repository state at implementation commit:** unrelated untracked `uv.lock` was preserved and excluded from commits.

## Independent review disposition at exact implementation SHA

- **CPO:** no remaining findings in the reviewed fixes; the mapping-version concern was resolved against the documented contract.
- **CTO:** no correctness/race findings in the stale-conflict fix; local tests were not independently run in that review.
- **Security/Data:** pass for the exact error-classification change.
- **QA:** pass; independently ran the 105 focused repository/route tests.
- **UX/Journey:** pass for the narrow fix; static review only, no independent local browser run.
- **AI Evaluation:** pass for scope; 127 passed, 2 skipped; no AI behavior changed.
- **Gatekeeper:** ready for PR review, **not ready for merge**. The exact SHA and CI were checked; the Gatekeeper reported no submitted GitHub PR reviews at that time.

## Remaining gates and limits

PR #6 has been converted from draft to ready-for-review at the owner's direction. No merge, deployment, hosted change, new research, or Loop 5B work occurred. Obtain any required formal PR reviews and a final Gatekeeper merge disposition before considering merge. Recheck exact PR head and all required checks at that time. Hosted integration, production behavior, accessibility/screen-reader signoff, live-model behavior, and deployment remain unverified/not approved. A source merge, if later authorized, is not deployment authorization.
