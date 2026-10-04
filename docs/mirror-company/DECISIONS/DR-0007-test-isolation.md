# DR-0007 Deterministic tests run in an isolated environment
Status: Accepted · 2026-10-04 · Owner: CTO role (Loop 1)

## Problem
The Python suite read the developer's real `.env` (hosted Supabase URL, service-role key, provider keys) into every test process, and five API tests only passed when such an environment existed.
## Evidence
Clean clone at HEAD, no `.env`: 851 passed, **5 failed** (`test_api.py::test_create_and_read_session`, `::test_prepare_moves_created_session_to_ready`, `test_documents.py::test_session_document_linking_...`, `test_interview_engine.py::test_v1_session_endpoints_and_isolation`, `test_interview_planner.py::test_plan_api_is_owner_scoped_and_prepare_integrates`), all HTTP 503 because service constructors refuse when `supabase_enabled` is false. With `.env` present they passed, with real credentials loaded (`config.py` `env_file=(".env", ".env.local")`, `dependencies.py:160-166`).
## Options
(a) Leave as is and make CI provide dummy env vars only. (b) Root `conftest.py` that forces sentinel env, disables `.env` reading and blocks non-loopback network access for the whole deterministic suite. (c) Rewrite the five tests to override each dependency.
## Decision
(b), with an explicit opt-out only for the optional live model evaluation (`MIRROR_LIVE_EVAL=1`).
## Reason
Fixes CI parity and removes the standing risk that a test with a missing override reaches a real project; one place, provable by test (`tests/unit/test_test_isolation.py`).
## Consequences
Every new test is offline by default. A test that legitimately needs the network must say so (live eval). Code that reads settings at import must tolerate the sentinel values.
## Revisit when
The five tests are rewritten to override their dependencies explicitly, or the data layer stops falling back silently when the service-role key is absent.
