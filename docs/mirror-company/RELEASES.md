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

### Loop 1 final disposition — 2026-10-04 (supersedes the entry below)

**DECISION: LOOP 1 BLOCKED (G2 only). No production release was made; nothing is merged to `main`.** HEAD `e885130` on branch `loop1/trust-baseline` (draft PR #1). Commits over `main` (8e3193f): c6160bc CI/test infrastructure, 1e3c951 hosted inspector + browser QA foundation, e1d249d B5, d4df6a0 B7, 1106786 B12, 694cadc AI evaluation suite, 17eb6ac docs, ce61b71 + 12d832d + 42edee6 + dbe9ac0 + 02afc70 browser-on-CI, e885130 docs.
GATES: G0 PASS · G1 PASS (GitHub Actions runs 37196654767, 37196926810; 1204 passed/3 skipped locally and on CI) · G2 BLOCKED (hosted catalog unreadable; migration 202610010002 state unknown) · G3 PASS (CI job; KI-020 acknowledged) · G4 PASS (deterministic) · G5 PASS for Loop 1 scope.
HOSTED DB: migrations applied through UNKNOWN — not confirmed by a human. Four repo objects absent on hosted (see HOSTED_SUPABASE_DRIFT.md); no migration was applied or authorized.
KNOWN ISSUES: KI-016a-d, KI-017a-c, KI-019, KI-020, KI-021, KI-022 (none are release blockers on their own; KI-021 is the G2 blocker).
WAIVERS: none.
Required to close: owner-supplied hosted catalog JSON + written statement on `202610010002` (or a written G2 waiver here), then Gatekeeper re-decision and the merge of PR #1.
Gatekeeper report: scratch/final_gatekeeper.md (local, not committed).

### Loop 1 interim disposition — 2026-10-04 (superseded)

**DECISION: REJECTED for production release.** Independent Release Gatekeeper adjudication is STATIC-ONLY, based on attributed execution evidence in the Architecture and Security/Data follow-up reports. Scoped offline verification infrastructure is accepted, but Loop 1 remains **BLOCKED / IN PROGRESS**, not closed-with-blockers.

G0 closure documentation required status reconciliation and a full link/source audit remains NOT DONE. G1 scoped infrastructure is accepted; complete fresh platform/frontend gate evidence is not established. G2 is N/A for the no-migration slice, with hosted catalog/ledger/RLS prerequisites BLOCKED. G3 real browser verification is BLOCKED. G4 product contracts FAIL: five unmasked tests fail across B5/B7/B12. **G5 REJECTED; WAIVERS: NONE.** No release, push/deployment, hosted mutation, browser-isolation bypass, or Loop 2 is authorized.

Parent full offline run: 1060 passed, 3 skipped, 5 strict xfailed. Expected failures disclose defects and do not satisfy requirements. Gatekeeper report: `C:/Users/sachi/AppData/Local/hermes/cache/scratch/release_gatekeeper_loop1.md`. Receipt: `RECEIPTS/LR-0001-trust-baseline.md`.

Recommended next bounded objective: B5 evidence-ID validation before assessment persistence/publication. A human/CPO decision is required to continue, re-scope or suspend the trust-baseline objective; no product implementation starts from this record alone.

No production release has been made by this organization layer. (At that time no GitHub/Linux execution was recorded; see the final disposition above.) Deployment target/process and live commit remain unverified; establish those before any future release approval.
