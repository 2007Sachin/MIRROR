# DR-0008 Hermetic browser QA; no synthetic user on the hosted project
Status: **Direction selected; implementation BLOCKED; Security/Data approval pending** · 2026-10-04 · Owner: CTO + Security/Data role (Loop 1)

## Correction after independent review

The initial harness was rejected for environment/egress isolation, ordinary `.next` contamination and false-green execution. The repaired launcher and direct critical-path entry now refuse execution unconditionally. The orchestrator independently ran safety unit checks: **11 passed, 0 failed, 0 skipped**, exit 0. This is safety-foundation evidence, not browser behavior verification. No build/browser PASS exists. Required isolation/staging/environment/build-identity work is listed in `scripts/qa/browser/SAFETY.md`; do not bypass refusal to obtain a green result.

Observed nutrition tables are unmanaged by this repo; their ownership/grants are unverified. A fake Auth/API server alone is NOT a sufficient isolation boundary for Next build/SSR or native browser processes.

## Problem
Mirror needs real-browser verification, but creating a QA user requires mutating Supabase Auth, and the only Supabase project is a shared project with real data.
## Evidence
`HOSTED_SUPABASE_DRIFT.md`: shared project (non-Mirror tables), `sessions` 32 rows, `profiles` 6. The owner's rule: the QA user must never contaminate production data/analytics, never weaken auth, and credentials must not be committed. The API authenticates only via `GET {SUPABASE_URL}/auth/v1/user` (`auth.py`), so a local stand-in for Supabase Auth plus the Mirror API is sufficient without touching production code.
## Options
(a) Create a synthetic user on the hosted project. (b) Add a dev-login bypass in production code. (c) Hermetic harness: local fake Supabase Auth + fake API on loopback, real Next production build, real system browser (`scripts/qa/browser`).
## Decision
(c). (a) is blocked pending a dedicated non-production project; (b) is rejected because it weakens authentication.
## Consequences
Browser PASS means "the real frontend, in a real browser, against contract-faithful fakes". It is **not** end-to-end against the real backend or database. A drift-guard pytest validates the mock fixtures against the real pydantic models. True end-to-end remains BLOCKED on: a separate non-production Supabase project, a QA user provisioned there by the owner, credentials supplied by env.
## Revisit when
A dedicated non-production Supabase project exists.
