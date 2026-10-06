# DR-0006 First objective: trust baseline, then a curated vertical slice
Status: **Approved by owner for Loop 1; Loop 1 accepted 2026-10-04. Later bounded Loop 2 authorization recorded below.** · 2026-10-04 · Owner: CPO + CTO

## Problem
Which objective should the loop start with?
## Evidence
Strong backend tests (862 pass) but: no CI (KI-005), no signed-in QA path (KI-006), no executable AI eval (KI-007), hosted-DB state unknown (KI-004). Mirror 2.0 adds schema and AI behaviour exactly in the areas that cannot yet be verified.
## Options
(a) Start with Interview Intelligence schema. (b) Start with a thin trust baseline, then a vertical slice. (c) Start with multi-round engine.
## Arguments
(a)/(c) deliver value sooner but would ship unverifiable changes onto an unreconciled DB. (b) delays visible value by one small loop but makes every later G2/G3/G4 gate real.
## Decision (owner authorized Loop 1)
**Loop 1 (M1):** CI workflow (pytest from root via venv python, `lint:copy`, typecheck, build); remove the stale-`.next` typecheck flake; AI-eval harness over persona fixtures with the fake provider (including P5 honest-beginner); written QA-user proposal for human approval; human-run read-only DB reconciliation.
**Proposed Loop 2 at the time of this decision (M3→M4 slice):** one curated company×role: target model → provenance-labelled expectations in brief/Interview Map. No scraping, no multi-round engine.

## Later bounded authorization and status — 2026-10-06

After Loop 1 closure, the owner separately authorized the bounded Loop 2 local-slice task recorded in `RECEIPTS/LR-0002-amazon-swe-india-local-slice.md`. The independent Gatekeeper accepted A (local architecture/product), held B (Amazon SDE I/SDE II India), and marked C (hosted release readiness) NOT VERIFIED. This is not approval to release Amazon India research, apply hosted migrations, deploy, start Loop 3, or change the still-proposed broader DR-0004/DR-0005 status.

## Reason
Candidate value per risk: the slice proves the data model and wording with real stakes at small scale.
## Consequences
No visible candidate change from Loop 1.
## Revisit when
Human supplies verified hosted-DB state and a QA user sooner than expected (compress Loop 1), or priorities change.
