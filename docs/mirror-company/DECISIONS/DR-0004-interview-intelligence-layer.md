# DR-0004 Interview Intelligence: additive, global, versioned, provenance-first
Status: **Proposed — needs human approval** · 2026-10-04 · Owner: CTO + Head of Interview Intelligence

## Problem
Mirror has no company/round/process data. The target needs it, stored with provenance and uncertainty, without damaging existing candidate data.
## Evidence
`GAP_ANALYSIS.md`; orphaned `company_id` columns; dormant `question_bank`/`rubrics`; `role_competencies` already carry `source_type`, `source_reference`, `confidence` (a precedent for provenance); migration-contract test pattern exists.
## Options
(a) Repurpose legacy `roles/skills/rubrics/question_bank`. (b) New `ii_*` tables, additive links to existing tables. (c) Store research as JSON blobs on `role_profiles`.
## Arguments
(a) saves tables but couples to unknown live data and a 2026-08 schema with an enum `round_type` of 4 values. (c) defeats versioning/conflicts/provenance. (b) costs more tables but is reversible and queryable.
## Decision (proposed)
(b). Global reference tables are service-written and API-mediated (not exposed to the browser Supabase client); candidate artifacts (blueprints, generated questions) are owner-scoped under RLS. No migration before: human approval, hosted-DB read-only reconciliation (KI-004), and a G2-reviewed migration plan with rollback.
## Consequences
Legacy tables remain until separately retired. A taxonomy (round types as rows, not enum) must exist first (M2).
## Revisit when
The hosted DB inspection shows legacy tables hold meaningful data or are already shaped usefully.
