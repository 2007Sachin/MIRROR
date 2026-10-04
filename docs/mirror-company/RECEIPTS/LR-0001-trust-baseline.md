# LR-0001 — Trust baseline: LOOP 1 BLOCKED on G2 only (Gatekeeper 2026-10-04); G0, G1, G3, G4, G5 pass; B5, B7, B12 accepted

Date: 2026-10-04. Baseline: `main` at `8e3193f`; work is uncommitted. This is a continuation receipt, NOT closure or release authorization.

## Objective
Establish repeatable, truthful engineering and verification infrastructure before broad Interview Intelligence implementation. Scope is infrastructure/tests/organization documentation; production-service fixes and hosted mutations are deferred.

## Work and ownership
- Orchestrator: wrapper exit handling, clean-checkout frontend checks, CI, read-only drift assessment, durable organization state, integration verification and root-conftest identity correction.
- AI Evaluation specialist: executable offline behavior suite; corrected transcript-aware oracles, deliberately broken negative controls, actual persistence observation and truthful failure claims.
- Security infrastructure specialist: snapshot redirect/URL/method/path guards, no import-time credentials, Python byte-host/UDP rails and CI live=0/Node24.
- Browser specialist: synthetic fixtures/mocks and fail-closed safety foundation; unsafe ordinary `.next` build/reuse path removed. Actual browser/build execution intentionally disabled.
- Independent Architecture and Security/Data reviewers: initial rejection, then scoped follow-up approval.
- Release Gatekeeper: final STATIC-ONLY adjudication (`deleg_4d450c49`): infrastructure slice ACCEPTED; Loop1 BLOCKED / IN PROGRESS, not closed-with-blockers; G3 BLOCKED, product G4 FAIL, G5 REJECTED. No waiver, release, hosted writes, browser bypass or Loop2. Report: scratch/release_gatekeeper_loop1.md.

## Files / database
Changed areas: `.github/workflows/ci.yml`, npm verification scripts/config, `scripts/exit-code.*` and run wrappers, `.gitignore`/generated Next types handling, `.env.example`/README, `conftest.py`, `tests/ai_eval/**`, isolation/snapshot/mock contract tests, `scripts/ops/**`, `scripts/qa/browser/**`, `docs/mirror-company/**`.

No production API/frontend service behavior, migrations, hosted records, RLS, policies, or auth users intentionally changed. No commit/push/release. No user secret backups deleted. No hosted/tool rerun during corrections.

## Executed evidence
| Evidence | Actual result | Attribution |
|---|---|---|
| Full offline suite after corrections | **1060 passed, 3 skipped, 5 strict xfailed**, 6 existing deprecation warnings, exit 0, 46.25s | Orchestrator executed; Architecture parsed corroborating log/XML, not independent full rerun |
| Initial integration attempt | **30 failed, 1030 passed, 3 skipped, 5 xfailed** | Root isolation tests imported nested AI conftest; fixed via exact root-plugin file identity, then rerun above |
| Joint AI + isolation follow-up | **121 passed, 2 skipped, 5 xfailed**, exit 0; all39 isolation cases passed | Independently Architecture-executed |
| Known-gap run with `--runxfail` | **5 failed**, exit1, expected contract failures | Independently Architecture-executed; demonstrates real red-capable requirements |
| Security focused rails | **100 passed, 1 deselected**, exit0 | Independently Security-executed; listener case excluded by review scope |
| Optimized snapshot synthetic safety | **62 passed**, 1 expected optimization warning, exit0 | Independently Security-executed |
| Browser no-network foundation | **11 passed**, 0 failed/skipped, exit0 | Orchestrator and Security independently executed; NOT browser behavior |
| Wrapper tests | **5 passed** | Earlier independently executed reviewer evidence |
| Clean-checkout frontend verification | clean → typecheck → copy lint → build, exit0 | Earlier orchestrator execution retained in scratch/cleanroom_verify_web.txt; not fresh follow-up build or Linux CI |

Full-run evidence: `C:/Users/sachi/AppData/Local/hermes/cache/scratch/loop1_corrected_pytest_green.txt` and `loop1_corrected_pytest.xml`.

## Independent verdicts
- Architecture follow-up: **APPROVE scoped verification infrastructure**; **production G4/release NOT APPROVED**.
- Security follow-up: **APPROVE scoped snapshot/Python/CI/evidence corrections**; **APPROVE browser safety foundation only**; **runtime browser G3 REJECTED/BLOCKED**, release not approved.
- These verdicts are not authority to perform hosted actions, deploy, enable browser execution, or waive gates.

Reports: scratch `review_ci_architecture_followup.md`, `review_security_followup.md`; detailed correction evidence `ai_eval_review_fixes.md`, `security_infra_fixes.md`, `browser_safety_fixes.md`.

## B5 Evidence Integrity Fix - B5 ACCEPTED (B5 only; Loop 1 remains OPEN / BLOCKED) (2026-10-04)
**Status:** B5 ACCEPTED by B5 Release Gatekeeper after round-2 review (all round-1 fixes verified by probe; no B5 blocker). This does not close Loop 1.

**Trust boundaries closed (deterministic code, model never establishes validity):**
- `apps/api/app/evidence_validator.py`: turn ids must resolve to candidate-authored turns of the session (str ids coerced to UUID); quotes must appear in the cited turn (min 3 chars); nested evidence validated recursively, depth > 10 fails closed; malformed nested items and unattributable quotes fail.
- Fresh store: `AssessmentOrchestrator` rejects before persistence (job fails; nothing stored).
- Cached reuse: revalidated; an invalid cached row, or one with no context to verify against, is never reused and falls through to fresh generation (stale row preserved, newer row supersedes).
- Report (`report_service.py`): turns loaded via ownership-checked `list_turns`; claim-evidence and moment quotes kept only if they resolve; evidence rows with neither turn nor document are dropped.
- Legacy/unverifiable final results: provenance (not age) decides. If specialist inputs are absent or any latest specialist row fails validation, or turns cannot be loaded, the report shows no readiness range, no skill assessments, root cause UNAVAILABLE, blank model-written summary. Internal reason `UNVERIFIABLE_LEGACY_PROVENANCE` is logged only. No writes, deletes, recompute or migration; records and transcripts untouched, so recovery stays possible.
- Aggregator: a missing/unverified specialist row is excluded from the weighted score (UNKNOWN is neither strength nor weakness); lowers confidence only.

**Independent reviews round 1:** AI Eval REJECT, Security REJECT, Architecture REJECT. Defects fixed: str/UUID turn-id mismatch with real PostgREST rows (would have blanked every real report), turn-less claim evidence passed, 1-char quote accepted, cached reuse failing open without context, stale invalid cache unrecoverable, None turn_id quote skipped, non-dict nested crash, specialist row ordering. Round 2 (`scratch/review_b5_round2.md`): all fixes verified, **B5 ACCEPTED**. Non-blocking residuals: document-sourced claim evidence (document_id, no turn) not quote-verified (server-side claims pipeline); `None` nested lists raise TypeError (still fails closed); skill list order vs created_at sort; dead attributes in validator.

**Tests (exact):** `apps/api/tests tests` -> 1111 passed, 3 skipped, 3 xfailed (B7 + two B12 untouched). Report/cached/aggregator behavior in `apps/api/tests/test_report_b5.py` and `tests/ai_eval/test_eval_b5_matrix.py`; nine vacuous skip-placeholders removed.

**Known debt (not fixed, by design):** (1) legacy provenance recovery process not built; (2) UNAVAILABLE reports still carry verdict code NOT_READY_YET (existing not-enough-signal mapping); (3) one fresh specialist rejection fails the whole assessment job (safe degradation, discards passing specialists); (4) COMPLETE assessment with turn ids but no quotes is checked only for id resolution; (5) claim statuses in the report derive from the claims pipeline, outside B5.

## B7 Specialist Position Integrity - B7 ACCEPTED (B7 only; Loop 1 remains OPEN / BLOCKED) (2026-10-04)
Root cause: `AdjudicationDecision.specialist_positions` is a model-echoed field never compared to the detector-owned positions, so rewritten positions were persisted as specialist truth; live/cached specialist objects were also passed by reference. Specialist persistence is append-only (no PATCH/upsert anywhere) and no consumer reads adjudication content, so impact was stored provenance, not readiness.
Fix (`assessment_adjudication_service.py`, one prompt sentence, no schema/migration): positions must equal detector output else decision dropped; deep-copied inputs; runner gets its own context copy while the pristine context is stored; evidence allow-list snapshotted before run; contexts diverging from persisted specialist state are skipped.
Reviews: round 1 AI-eval REJECT (runner could alter stored specialist_inputs / widen evidence allow-list) -> fixed; Architecture APPROVE; Security APPROVE; round 2 + Gatekeeper: **B7 ACCEPTED** (`scratch/review_b7_round2.md`).
Tests: `apps/api/tests tests` -> 1123 passed, 3 skipped, 2 xfailed (B12 only). Tests changed: an old unit test that asserted success with rewritten positions (it encoded the bug) now uses faithful positions; AI-eval negative control (b) now simulates tampering directly because the service blocks it.

## B12 Interviewer Contradiction + Probe Safety - B12 ACCEPTED (B12 only; Loop 1 remains OPEN / BLOCKED) (2026-10-04)
Root cause: the false-contradiction guard returned early whenever the candidate turn contained a denial marker ("I never", "I didn't"...), so a bare denial kept a model-asserted CONTRADICTION; model-written reason/probe text was only retyped, never sanitized.
Fix: `apps/api/app/probe_safety.py` (new): a contradiction survives only if a negation in the current answer is about the same content as a referenced resume claim or earlier candidate turn (interviewer turns cannot ground; explicit self-correction of a spoken turn is a clarification); hostile/dishonesty wording always replaced with a neutral rigorous question (canonicalized against unicode obfuscation); discrepancy assertions allowed only when grounded. Enforced at the Skeptic store boundary (`skeptic_processor._conservative_normalization`) and the candidate-facing boundary (`interviewer_service._validated_decision`, falls to existing fallback). No prompt, schema or persistence change.
Reviews: round 1 AI-eval REJECT (paraphrases, unicode, 'actually' too broad, snippet banned copy) / Conversation APPROVE / Architecture APPROVE / Journey APPROVE; round 2 REJECT (basic accusation words missing, B-1) -> fixed; round 3 Gatekeeper: **B12 ACCEPTED**, no blockers (`scratch/review_b12_round3.md`).
Tests: `apps/api/tests tests` -> **1204 passed, 3 skipped, 0 xfailed** (0 B5/B7/B12 xfails; the 3 skips are the pre-existing live-eval skipif). Two former xfails removed after XPASS and renamed; no test weakened.
**G4 AI behaviour: PASS (deterministic fake-provider evaluation; no live-model evidence).** Known debt KI-019.

## Failures and remaining blockers
1. **G3 browser BLOCKED:** approved OS/container egress boundary, isolated secret-free/no-dotenv staging/config, minimal runtime environment, exact build identity/provenance and real desktop/mobile browser integration absent. Current launcher and direct critical path refuse execution. See `scripts/qa/browser/SAFETY.md`.
2. **G4 AI behaviour PASS (B5, B7, B12 accepted; deterministic evaluation).**
3. **Hosted G2/catalog evidence BLOCKED:** migration ledger/RLS/grants/constraints/triggers and enum compatibility unknown. Retained exposed schema lacks four required objects, but specific migration history is NOT established. No replay/repair authorized.
4. CI authored and locally exercised; actual GitHub/Linux clean run not performed.
5. Browser mock standalone listener remains callable; synthetic foundation approval is not universal listener isolation or runtime certification.

## Decisions / reflection
- Preserve working product systems; no broad implementation, destructive migration, production auth bypass or synthetic hosted QA user.
- Green CI with expected failures is infrastructure evidence, not all product requirements passing.
- Corrected drift claims retain uncertainty; empty tables do not prove safe retirement.
- Python socket rails are not an OS sandbox; native/subprocess/sendmsg and unrelated local services remain outside the guarantee.
- Independent review prevented false closure and exposed real defects that the original tests missed.
- B5 fix demonstrates deterministic evidence validation: model-generated references cannot substitute for actual persisted content.

## Next bounded work
- B5: ACCEPTED (B5 only).
- B5, B7, B12 ACCEPTED; known AI production-contract remediation phase complete. Remaining: G1 real CI, G2 hosted Supabase, G3 browser runtime, commit boundary.
- Separate proposal needed for browser isolation environment or external blocker documentation.
- Do not automatically start Loop2, migrations, paid infrastructure, or hosted actions.

## Final closure attempt (2026-10-04) — LOOP 1 BLOCKED (G2 only)
Branch `loop1/trust-baseline` @ e885130, draft PR #1, not merged. Real CI (GitHub Linux): runs 37196654767 and 37196926810 green (Backend 1094 passed/1 skipped; AI eval 110 passed/2 skipped; copy lint; clean typecheck and production build; browser job 36 steps desktop+mobile). Local: 1204 passed/3 skipped/0 xfailed. Final reviews (Architecture, Security/Data, QA, Product): APPROVE, no blockers. Release Gatekeeper: **LOOP 1 BLOCKED** — G2: hosted RLS/policies/grants/migration ledger unknown; `202610010002` state unknown. Owner action: run `scripts/ops/hosted_catalog_readonly.sql` in the Supabase SQL editor (SELECT-only), save the JSON, state whether `202610010002` is applied (or waive G2 in RELEASES.md). Known debt: KI-016a-d, KI-017a-c, KI-019, KI-020, KI-021, KI-022. See QUALITY_GATES.md and RELEASES.md.
