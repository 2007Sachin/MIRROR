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

### Loop 1 disposition — 2026-10-04

**DECISION: REJECTED for production release.** Independent Release Gatekeeper adjudication is STATIC-ONLY, based on attributed execution evidence in the Architecture and Security/Data follow-up reports. Scoped offline verification infrastructure is accepted, but Loop 1 remains **BLOCKED / IN PROGRESS**, not closed-with-blockers.

G0 closure documentation required status reconciliation and a full link/source audit remains NOT DONE. G1 scoped infrastructure is accepted; complete fresh platform/frontend gate evidence is not established. G2 is N/A for the no-migration slice, with hosted catalog/ledger/RLS prerequisites BLOCKED. G3 real browser verification is BLOCKED. G4 product contracts FAIL: five unmasked tests fail across B5/B7/B12. **G5 REJECTED; WAIVERS: NONE.** No release, push/deployment, hosted mutation, browser-isolation bypass, or Loop 2 is authorized.

Parent full offline run: 1060 passed, 3 skipped, 5 strict xfailed. Expected failures disclose defects and do not satisfy requirements. Gatekeeper report: `C:/Users/sachi/AppData/Local/hermes/cache/scratch/release_gatekeeper_loop1.md`. Receipt: `RECEIPTS/LR-0001-trust-baseline.md`.

Recommended next bounded objective: B5 evidence-ID validation before assessment persistence/publication. A human/CPO decision is required to continue, re-scope or suspend the trust-baseline objective; no product implementation starts from this record alone.

No production release has been made by this organization layer. CI configuration now exists but no GitHub/Linux execution is recorded. Deployment target/process and live commit remain unverified; establish those before any future release approval.
