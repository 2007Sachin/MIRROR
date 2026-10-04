# DR-0005 Lift the "no company research" non-goal, under provenance rules
Status: **Proposed — needs human approval** · 2026-10-04 · Owner: CPO + CEO role

## Problem
Current Mirror states, as product stance, that it does not research companies ("Mirror has not researched the company", `interview_brief.py`; "no company research" in `INTERVIEW_EVENTS_CONTRACT.md`). The target product requires company-aware preparation.
## Evidence
`interview_brief.py:44`; `docs/architecture/INTERVIEW_EVENTS_CONTRACT.md`; directive §§1, 4–6.
## Options
(a) Keep the non-goal (Mirror stays role-and-candidate-only). (b) Lift it with strict provenance, scope, uncertainty and candidate-safe wording. (c) Lift it unconditionally.
## Decision (proposed)
(b). Company-specific statements reach candidates only with class + scope + date + honest uncertainty (`RESEARCH_POLICY.md`); never "always"; thin evidence stays `CANDIDATE_REPORTED`/hidden.
## Reason
Real interviews differ by company; a diagnostic that ignores it is capped in value. The honesty rule keeps the existing product promise (stated limitations, no overclaiming).
## Consequences
Trust-sensitive: wrong company claims harm candidates. Needs Verifier gate, Journey Critic review of wording, and the legal/compliance stop condition for source use.
## Revisit when
Evidence from usage shows company-specific plans do not improve preparation, or sources become unavailable.
