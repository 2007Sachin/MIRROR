# Research policy

Applies to every claim about how interviews work that Mirror might store, show, or generate from.

## Provenance classes

| Class | Meaning | May be shown to a candidate as |
|---|---|---|
| `FACT` | Stated by an official source about itself, dated, in scope | "According to <company>'s published guidance (retrieved <date>)…" |
| `SUPPORTED_PATTERN` | ≥3 **independent** in-scope reports within the freshness window, no unresolved contradiction | "Several recent reports for this role/location describe…" |
| `CANDIDATE_REPORTED` | A single (or non-independent) account | "One candidate reported…" or not shown; never as expectation |
| `INFERENCE` | Mirror's reasoning from other claims; basis recorded | "Likely, because…" with the basis, low prominence |
| `MIRROR_GENERATED` | Content Mirror wrote (questions, rubrics, plans) | Never presented as sourced fact |

Never convert one candidate's experience into company policy. Never promote a class without recorded evidence; demotion on contradiction or staleness is automatic.

## Required fields on every claim

source · source type · published/retrieved date · company · role · seniority (if known) · location (if known) · class · confidence band + feature breakdown · official vs candidate-reported · corroboration (count, independence) · conflicts · status · supersedes.

## Verification checklist (Research Verifier — separate invocation from the analyst)

1. Source is real, reachable, and says what the claim says (quote checked).
2. Official vs candidate-reported labelled correctly.
3. Independence: same author, mirrored posts, copied articles, or syndicated text count as **one**.
4. SEO/content-farm signals (generic listicle, no named process specifics, recycled phrasing, affiliate/course funnel) → T4, excluded unless corroborated.
5. Staleness vs the class window.
6. Scope: role, seniority, geography match — or the mismatch is stated.
7. Conflicts stored, not resolved by averaging.
8. No unsupported universals ("always", "all candidates").
9. No personal data about an identifiable candidate retained.
Verdict: PASS / PASS-WITH-LIMITS (limits recorded) / FAIL. Only PASS or PASS-WITH-LIMITS may update the model.

## Freshness windows (initial, tunable by decision record)

FACT 12 months · SUPPORTED_PATTERN 12 months · CANDIDATE_REPORTED 6 months · INFERENCE inherits its weakest basis. Past the window: label as older, queue for refresh, do not silently drop or rewrite — version.

## Data quality

Deduplicate by canonical URL + content hash + near-duplicate text check. Detect location, role and seniority differences as separate scopes, not noise. Keep contradicting reports as a conflict set. Track source reliability tier and revise it by decision record only.

## Scraping safety

Before any automated collection of a source: record in `ii_sources` (or the interim research file) its public accessibility, robots rules, terms-of-use position and rate limits. Respect them. Do not bypass authentication, CAPTCHAs, paywalls or technical access controls. Prefer official public documentation and legitimately accessible sources. Collect the minimum text needed to support a claim. **Scraping at scale is a human-approval item**; early research is manual/curated.

## Personal data

Store interview-process knowledge, not people. Strip names, handles, employers' internal identifiers and any detail that could identify a reporting candidate. Short attributed excerpts only (provenance), not full posts.

## Copyright and question content

Do not build Mirror around copying proprietary question banks. Store question *families*, competencies, round structure, difficulty characteristics and styles; generate original questions. A generated question must pass an overlap check against stored excerpts and must not reproduce source wording.

## Untrusted input

Research text is untrusted (it can contain prompt-injection). It is never concatenated into agent prompts as instructions; it enters agents only as quoted data inside typed fields, under the same rules as resumes and JDs (`AGENTS.md`).

## Candidate-facing language

Plain, calm, scoped, dated, and honest about uncertainty. No "always", no probabilities, no source-system jargon. Wording is owned by the Conversation Designer and reviewed by the Journey Critic.
