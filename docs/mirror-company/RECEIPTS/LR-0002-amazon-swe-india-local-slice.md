# LR-0002 — Amazon SWE India local slice — ACCEPTED (bounded)

Date: 2026-10-06 · Branch: `loop2/amazon-swe-india-v1` · Reviewed implementation HEAD: `635209c43fe884c92ed62b0c03b449247354afc3` · Base: `3b7950901d7afad2ee2a358cd44ee3a75b42ff05`

## Decision and boundary

**Independent final Release Gatekeeper:** A — **LOCAL ARCHITECTURE/PRODUCT SLICE: PASS**; B — **AMAZON INDIA RESEARCH: HELD**; C — **HOSTED RELEASE READINESS: NOT VERIFIED**. **LOOP 2 LOCAL SLICE ACCEPTED.** This is local hypothesis/architecture acceptance, not production release approval.

Owner constraints retained: no Loop 3, no further product behavior changes, no hosted migration or integration, Amazon SDE I/SDE II India remain held, production release/deployment remain NOT APPROVED. The owner separately authorized repository PR/merge after fresh exact-final-HEAD CI; that is source integration only and does not authorize deployment or hosted work.

## Proven

Only within the bounded local slice, with fictional/synthetic QA inputs and disposable local PostgreSQL:

- Exact company + role-family + seniority + geography matching; global-only, wrong geography/level, wrong round, unmapped, removed, or rescoped claims do not gain the target round's research effect.
- Explicit claim-to-round mapping produces a round-specific research basis, blueprint content, priority, and practice context. A claim mapped to one round does not leak to another through a shared competency.
- Research basis and question origin remain separate. `PUBLISHED_GUIDANCE_AREA`/published guidance can explain why a practice theme was selected while the prompt row remains `MIRROR_GENERATED`; generated questions are not called official. The practice-start response does not expose prompt text prematurely.
- First-writer prompt manifests are immutable and owner/context scoped. Retries recover the claimed attempt and its original blueprint/manifest instead of regenerating from changed context. Partial/mismatched sets fail closed; only a valid `PENDING → COMPLETE` transition makes a pack usable. Generic links have no prompt manifest. Authenticated direct reads of generated-question text are revoked; the guarded backend flow uses service-role access.
- Same-key replay/concurrent starts, partial persistence/retry, changed context/blueprint recovery, no-target recovery, and candidate/global data separation have regression coverage.
- The actual isolated CI browser journey exercised the researched-round-to-review and optional-target-failure-to-general-plan paths at desktop and mobile sizes.

## Not proven

- Amazon SDE I/SDE II India interview-process validity or release eligibility. The existing India research verifier is FAIL/UNVERIFIED; no qualifying India-specific research is approved. No additional Amazon India research was performed during final closure. Synthetic fixtures are not Amazon evidence.
- Hosted application of migration `20261005210000`, current hosted migration state for this slice, hosted PostgREST/JWT/RLS behavior, or production integration.
- Production release readiness, deployment, live-provider quality, or speech quality.

## Provenance blocker resolved

The red synthetic practice-start result came from conflating the preparation/research basis with the origin of the generated question in the browser mock. The existing domain already represented the two meanings separately: research rationale (`rationale_code`, e.g. `PUBLISHED_GUIDANCE_AREA`) versus prompt origin (`provenance_class`, `MIRROR_GENERATED`). The mock/fixture mapping and regression were corrected; production semantics were not changed merely to make a fixture pass. Exact-scope research remains visible as the basis, while the generated question remains Mirror-generated.

## Prompt-pack invariants and SQL

The prompt-backed session link snapshots its manifest on first write; retries use that immutable snapshot. Completion verifies expected count, ordering, and stored content; inconsistent/incomplete packs are not returned as complete. Link identity, context, manifest, and `COMPLETE` state cannot be rewritten. Duplicate prompt positions are rejected. Question rows remain backend-private until the guarded practice flow; parent cleanup cascades only within the owner-scoped session data.

**VERIFIED-EXECUTED, local only:** disposable PostgreSQL 16 migration/backfill/invariant/rollback harness returned **32/32 passed**. It exercised backfill, generic/context-bound manifest rules, incomplete and valid completion, duplicate positions, immutable `COMPLETE`, question update/delete guards, authenticated question-text denial, service-role access, parent cleanup/cascade, rollback refusal with live rows, successful rollback after cleanup, and grant restoration. No hosted database was used.

## Research-effect and prompt-origin test inventory

The final source includes these six synthetic service/product regressions in `apps/api/tests/test_target_research_product_behavior.py`:

1. `test_in_scope_synthetic_research_changes_blueprint_round_and_priority_basis`
2. `test_removing_rescoping_or_level_mismatch_removes_product_effects`
3. `test_unmapped_research_claim_does_not_change_coding_round`
4. `test_out_of_scope_source_does_not_suppress_pack_but_matched_source_does`
5. `test_synthetic_research_changes_service_blueprint_round_detail_and_priorities`
6. `test_practice_start_keeps_research_basis_separate_from_generated_question_origin`

Related integrity/recovery tests are in `apps/api/tests/test_target_repository.py`, `apps/api/tests/test_target_routes.py`, and `apps/api/tests/test_supabase_session_idempotency.py`. Migration/privacy contracts are in `tests/unit/test_loop2_candidate_targets_migration_contract.py` and `tests/unit/test_loop2_prompt_completeness_migration_contract.py`. Scope/priority mapping is also covered by `apps/api/tests/test_research_catalog_scope.py`, `apps/api/tests/test_target_priority.py`, `apps/api/tests/test_target_rounds.py`, and `tests/unit/test_loop2_research_mapping_contract.py`. Web copy/recovery tests are in `apps/web/tests/target-copy.test.mjs` and `apps/web/tests/target-recovery.test.mjs`.

Browser coverage: `scripts/qa/browser/tests/target-journeys.mjs` T09b (researched round → practice → answers → review) and T16 (optional target setup failure → general plan); mock/network contracts are in `targets-mock.test.mjs` and `network.test.mjs`. Assertions retain exact-scope, unsupported-scope, no-premature-prompt-text, no-target, desktop/mobile, and no-unexpected-network controls. `targets-mock.test.mjs` contains **10 tests; all 10 passed** in the final 27-test browser unit run. The 10 test names are: “default is the real India behaviour: one target, not yet researched, no claims”; “error and unavailable states are deliberate mocked answers, not unmocked 404s”; “researched scenario carries a conflict side by side and a synthetic text only”; “synthetic research reaches its mapped round priority and prompt metadata without revealing text”; “creating a target records the body and a second target for the same role is a 409”; “round practice creates one session per idempotency key, links it, and history counts it”; “short pack is reported on the round and refused at start, before any session”; “unknown rounds and targets are 404; plan follows the requested role”; “the critical path runs the Loop 2 journeys before sign-out, and every allowed error names a real step”; and “server wires the Loop 2 routes, the scenario control and delayed answers”. The “real India behaviour” label is a test-only no-research baseline, not evidence about Amazon India.

## Fresh regression evidence at the reviewed implementation HEAD

**VERIFIED-EXECUTED, local (parent-observed):**

- Full Python: **1,434 passed, 3 skipped, 0 failed**.
- AI evaluation directory: **125 passed, 2 skipped, 0 failed**.
- Focused target/repository/route/research/migration suite: **107 passed**.
- Web Node tests: **29 passed**.
- Browser safety/mock/network/target-mock harness: **27 passed**.
- Copy lint: **178 files scanned, 0 banned-word hits, 3 soft-avoid warnings**.
- Frontend typecheck and production build: exit 0.

**VERIFIED-EXECUTED, exact GitHub CI:** run `37509014604`, exact head `635209c43fe884c92ed62b0c03b449247354afc3`, all required jobs succeeded:

- `Backend, copy lint, AI evaluation`: backend/contract partition **1,324 passed, 1 skipped, 112 deselected**; AI-marked CI partition **110 passed, 2 skipped, 1,325 deselected**; copy lint passed.
- `Frontend typecheck and production build`: passed.
- `Browser critical path (isolated, synthetic)`: real Chrome, 36 desktop steps at 1280×800 and 36 mobile steps at 390×844; T09b and T16 passed at both sizes. No page errors, console errors, failed/bad/denied requests, unmocked API calls, or mobile horizontal overflow. Runner summary: `okWithAcknowledgedKnownIssues=true`; strict `ok=false` solely for the acknowledged KI-020 typing-only-room issue. This is not hidden or represented as a strict clean browser result.

The isolated browser uses fake Auth/API and fictional fixtures; it verifies the web journey, not hosted PostgREST or the Python assessment pipeline through the UI.

## Independent reviews

All seven final reviewers returned PASS against the same implementation HEAD `635209c43fe884c92ed62b0c03b449247354afc3`: Architecture, Security/Data, Data/Supabase, Product/CPO, AI Evaluation, QA, and Journey Critic. The prior Architecture copy concern was resolved by distinguishing overall scope match from per-round basis. Evidence scopes differed: some final reviews used supplied exact-HEAD excerpts/results; QA verified CI status but could not fetch the artifact contents; Journey Critic was explicitly STATIC-ONLY. No reviewer reported a concrete remaining acceptance violation.

**Independent Gatekeeper:** A PASS / B HELD / C NOT VERIFIED; local slice accepted. Gatekeeper did not rerun the suites or fetch CI artifacts; those results are attributed to the parent-observed execution evidence above.

## Git, CI, and external state

The reviewed implementation branch was clean and pushed at `635209c43fe884c92ed62b0c03b449247354afc3`; origin matched. Run `37509014604` covered that exact code SHA. This receipt is a closure-record update and therefore must be included in a new branch HEAD that receives its own fresh exact-SHA CI before any PR merge. Repository PR/merge outcome is tracked separately from production release; no hosted migration, hosted integration, deployment, or production release is implied.

## Known debt / stop conditions

- **KI-020:** typing-only interview room can stick after answer; explicitly acknowledged by CI and remains open.
- **KI-022:** fixture-backed browser does not exercise the Python assessment pipeline or unavailable-diagnostic report state through the UI.
- **KI-023:** Journey Critic reported a fixed-bottom-navigation overlap with the first plan card at one mobile scroll position; non-blocking visual debt, not fixed in this verification-only closure.
- **KI-024:** synthetic fixture labels appear in some QA screenshots; test-artifact presentation debt only, no real candidate/company data.
- No additional cleanup or product behavior work is authorized. No Loop 3 started.

## Reflection and next recommendation

The slice proves a reusable, scope-safe local architecture hypothesis and a synthetic candidate journey, not the truth of Amazon India research or operational readiness. Preserve the separation in every future status: **PROVEN** local scope/provenance/blueprint/priority/practice/manifest/recovery/concurrency/privacy/browser contracts; **NOT PROVEN** Amazon India evidence, hosted migration/PostgREST integration, and production release readiness. Stop here; any future objective requires a separate owner decision.
