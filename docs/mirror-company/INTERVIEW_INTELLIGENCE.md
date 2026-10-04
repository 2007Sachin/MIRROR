# Interview Intelligence — design proposal (DRAFT, nothing implemented)

Status: proposal for review under DR-0004 / DR-0005. **No migration, scraping, or code exists for this.** Everything below is design to be challenged by CTO, Security/Data Reviewer, Research Verifier and UX Lead before any build.

## Purpose

Give Mirror an honest, versioned model of *what a given interview process tends to look like* — per company × role × seniority × geography — so it can build a realistic blueprint, while never presenting thin evidence as company policy.

## Design principles

1. **Claims, not pages.** Store normalized claims with provenance and uncertainty, not scraped documents.
2. **Provenance class on every claim:** `FACT` · `SUPPORTED_PATTERN` · `CANDIDATE_REPORTED` · `INFERENCE` · `MIRROR_GENERATED` (definitions and promotion rules: `RESEARCH_POLICY.md`).
3. **Scope on every claim:** company, role, seniority, geography, observed-at. A claim without scope is invalid.
4. **Version, don't overwrite.** Processes change; history is kept and a candidate's blueprint pins the version it used.
5. **Global reference data is separate from candidate-owned data.** Intelligence tables are not user-owned; candidate artifacts (blueprints, generated questions) are owner-scoped under RLS like the rest of Mirror.
6. **Patterns, not question banks.** Mirror learns question *families*, competencies and difficulty characteristics, then generates original questions.
7. **Deterministic where possible.** Confidence, process assembly, difficulty state and de-duplication are code; LLMs extract and phrase inside typed contracts (matches `AGENTS.md`).

## Proposed entities (names prefixed `ii_` to avoid colliding with dormant legacy `roles`/`skills`/`rubrics`/`question_bank`; revisit after the hosted DB is inspected)

**Reference / taxonomy:** `ii_companies` (canonical name, aliases, status) · `ii_geographies` · `ii_seniority_levels` · `ii_role_families` · `ii_roles` (canonical title, family, aliases) · `ii_company_roles` (company × role × seniority × geography) · `ii_round_types` (extensible: screening, recruiter call, assessment, coding, technical, case study, analytics, system design, product sense, execution, behavioural, leadership, presentation, portfolio review, domain, hiring manager, bar raiser, HR … — rows, not an enum, so new types need no migration) · `ii_competencies` · `ii_skills` · `ii_question_families` (pattern description, competency, difficulty characteristics, style — never verbatim questions).

**Processes (versioned):** `ii_interview_processes` (company_role → current version) · `ii_process_versions` (valid_from/to, status, supersedes, assembled-from claim ids) · `ii_rounds` (version, ordinal, round_type, purpose, typical duration, format) · `ii_round_competencies` (round, competency, weight, provenance class, confidence).

**Evidence:** `ii_sources` (url/identifier, type, publisher, official?, published_at, retrieved_at, content hash, access-policy record, reliability tier) · `ii_claims` (subject ref, predicate, value, **class**, scope, confidence band + feature breakdown, observed_at, status, superseded_by) · `ii_claim_evidence` (claim, source, stance `supports|contradicts|context`, short attributed excerpt, independence group) .

**Candidate-owned (owner-scoped RLS):** `candidate_role_targets` (reuses/extends `role_profiles`: company, seniority, geography, interview date) · `interview_blueprints` (target, process version pinned, round list, provenance mix, status) · `blueprint_rounds` (purpose, competencies, duration, question strategy, per-competency difficulty, follow-up policy, rubric ref, completion criteria, linked `session_id`) · `generated_questions` (round, competency, family, text, rationale, derived-from ids, class `MIRROR_GENERATED`, difficulty, novelty/reuse tracking).

Reuse, don't replace: `role_profiles`, `role_analysis_versions`, `role_competencies`, `interview_plans`, `stories`, `answer_attempts`, `interview_events` stay (all exist). Additive links only (nullable FKs: `role_profiles.company_id`, `sessions.blueprint_round_id`; **neither exists today**). `candidate_role_targets` is a new table that *references* `role_profiles`, not an extension of it. The free-text `profiles.target_company` and `interview_events.company_label` need an alias-mapping/backfill plan to `ii_companies`. `ii_round_types` must map to the existing `RoundKind` (SCREENING, TECHNICAL, BEHAVIOURAL, HR, OTHER) used for recorded real interviews.

## Confidence (deterministic, auditable)

Inputs per claim: source tier (official > reputable > candidate-reported > unknown), count of **independent** sources (copies collapse to one), recency (class-specific half-life), scope match (exact / partial / mismatch), presence of contradicting evidence, consistency across versions. Output: band `LOW | MEDIUM | HIGH` plus stored feature breakdown. Rules, not LLM self-rating. Promotion examples: one candidate report → `CANDIDATE_REPORTED`/LOW forever; ≥3 independent in-scope, recent reports → may become `SUPPORTED_PATTERN`; `FACT` only from an official source and dated. Conflicting reports are stored as a conflict set and surfaced as "reports differ", never averaged away.

Candidate-facing wording is generated from class + band + scope + count ("Three recent reports for this role in this location describe a technical screen followed by two technical interviews"), never "Company X always…". UX Lead owns the plain-language translation; no probabilities or jargon in the UI.

**Overclaiming guards (Product Critic findings; enforced in code, not copy):** a "...for this role in this location" sentence is only generated when scope matches exactly and the independent-report count meets a floor; the existing limitation "Mirror has not researched the company" is replaced only when intelligence exists *for the candidate's exact scope* (a mismatched role or location must not read as "researched"); generated questions inside a company-named plan are labelled as practice questions written by Mirror, never as questions that company asks (DR-0005 constraint); candidate debriefs (`interview_debriefs`) must not feed company intelligence without explicit consent.

## Source strategy (tiered; per-source access check before use)

T1 official: company careers/interview-preparation pages, official engineering/hiring blogs, public job descriptions. T2 reputable third-party: institutional career centres, established publications with named authors. T3 candidate-reported: public posts where access terms permit automated reading. T4 SEO/aggregator/copied content: not used unless corroborated by T1–T3, and flagged. Authentication walls, CAPTCHAs, paywalls and technical blocks are never bypassed. No candidate identity is stored. See `RESEARCH_POLICY.md`.

## Refresh

Per-class staleness windows (e.g. FACT 12 mo, SUPPORTED_PATTERN 12 mo, CANDIDATE_REPORTED 6 mo; tunable). A slice past its window shows an "older information" label and enters `RESEARCH_STATE.md` as a refresh target. Triggers: a candidate targets a stale slice; official page content hash changes; contradicting source appears. Refresh creates a new `process_version`.

## Question-generation architecture

```
Target (company, role, seniority, geography) + Resume claims + Stories + Interview Map coverage
+ Past competency performance + JD
        │
        ▼
Blueprint Builder (deterministic skeleton)
   process_version rounds if confidence adequate, else role-family default marked LOW/INFERENCE
        │ round purpose, competencies, duration, difficulty seed
        ▼
Question Designer (bounded agent; typed I/O; versioned prompt)
   inputs: round purpose, competency, question-FAMILY descriptors (no verbatim), JD, relevant resume claims,
           story coverage, history (to avoid repeats)
   output: question, rationale, expected evidence, follow-up triggers
        ▼
Validators (deterministic): schema · novelty vs candidate history · overlap check against stored excerpts
   (no verbatim reproduction) · provenance tag = MIRROR_GENERATED · copy-guide lint
        ▼
Existing runtime: Interviewer + Skeptic (reasons persisted) + Difficulty state per competency
        ▼
Assessors (TECHNICAL, BEHAVIOUR, CLAIMS, + COMMUNICATION) → round adjudication → cross-round adjudication → diagnosis → practice
```

Questioning, assessment, and adjudication stay separate agents (directive §9; already true in code).

## Integration points with current Mirror

- **Planner v3**: add *optional* round/target context inputs; behaviour unchanged when absent.
- **Interview Map** (deterministic, derived on read): gains round-expectation themes with provenance labels; word-overlap coverage remains.
- **Interview brief**: its limitation "Mirror has not researched the company" becomes conditional on actual intelligence + confidence.
- **Progress**: extends from role to round/competency/company later; no change to attempt immutability.
- **Skeptic/Interviewer**: receive round purpose and follow-up policy as context; flags/phase rules unchanged.
- **Security (requirements, not current facts)**: research text is untrusted input. Research tables are to be service-written and API-mediated. A browser Supabase client exists (`apps/web/src/lib/supabase.ts`) and Supabase grants anon/authenticated on new public tables by default (the repo already had to retrofit this: `202609250001`), so **every `ii_*` migration must enable RLS (default deny), explicitly `revoke all ... from anon, authenticated`, and ship a migration-contract test asserting both**.

## Delivery shape (each step gated)

II-0 design review + taxonomy v1 (docs only) → II-1 **curated** seed for 3–5 company×role slices from official sources only, hand-verified, loaded via a reviewed script → vertical slice: target → blueprint view with provenance wording (no multi-round engine yet) → II-2 multi-round blueprint + round assessments → II-3 Question Designer + difficulty state → II-4 research pipeline + refresh (only then scale; scraping at scale needs human approval).

## Open questions for the owner

1. Approve lifting the "no company research" non-goal (DR-0005)?
2. Target user geography/markets first (drives T1 source choice; code already has Sarvam/Indic-language orientation)?
3. Is curated-first (manual, small) acceptable before any automated pipeline?
4. May the hosted Supabase project be inspected read-only to settle legacy-table fate and migration state?
