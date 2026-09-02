# Evidence Agent

## Purpose

The Evidence Agent organizes traceable material for one claim. It answers where
the claim originated, which exact stored statements support or weaken it, the
strength of that material, and which conservative claim status may now be
justified. It does not score readiness, decide honesty, produce a final verdict,
or control the interview.

## Skeptic versus Evidence

The Skeptic watches a live conversation for potentially useful inconsistencies,
missing detail, scope changes, and future probes. Its flags are observations,
not evidence verdicts. The Evidence Agent runs selectively after a meaningful
flag, a relevant claim probe, or session completion for an unresolved
high-priority claim. It receives a bounded `EvidenceContext` containing the
claim, source excerpts, relevant turns and probes, flags, existing evidence, and
project context.

It is intentionally not invoked for every trivial turn. The deterministic
`should_resolve` policy controls whether resolution work is worthwhile.

## Structured output

`EvidenceAssessment` separates supporting, weakening, and context-only items.
Every item names its source type and ID, turn or document anchor, exact quote,
direction, strength (`NONE`, `WEAK`, `MODERATE`, or `STRONG`), and a bounded
reason code. The model may recommend a claim status but cannot persist one.

Resume, document, transcript, project, flag, and probe content is untrusted. The
versioned `prompts/evidence/v1.md` instructs the model to ignore embedded
instructions, preserve personal-versus-team ownership, avoid treating an
unsupported metric as false, and prefer uncertainty.

## Quote verification

An LLM-produced quote is never trusted on its own. `EvidenceQuoteValidator`
loads the source through the ownership-scoped repository and first checks an
exact substring. It may then normalize Unicode quote/dash variants and repeated
whitespace. It does not use embeddings, fuzzy semantic similarity, or
paraphrase matching.

The service drops failed items and logs only execution, claim, and source IDs.
The service-role PostgreSQL insertion function independently loads the owned
turn or parsed document and repeats normalized substring validation. Therefore
an application bug or forged repository call still cannot mark an invented
quote as validated evidence. Resume quotes are checked against `documents.raw_text`,
which is populated by deterministic parsing.

## Persistence and duplicate handling

Validated items extend `claim_evidence` with source type/ID, reason code,
strength label, agent model, prompt version, execution ID, and `validated=true`.
A deterministic evidence key uniquely identifies claim, source, normalized
quote, and direction. Repeated analysis is idempotent and retains the first
trusted record. Unvalidated quotes are not stored as trusted evidence.

## Status resolution

`EvidenceResolutionService` treats the model status as a recommendation and
checks only validated evidence:

- `CORROBORATED` requires meaningful support with no material weakening.
- `PARTIALLY_HELD` requires both meaningful support and weakening evidence.
- `WALKED_BACK` requires a moderate/strong explicit retraction or ownership narrowing.
- `CONTRADICTED` requires meaningful support plus strong direct-conflict evidence.
- absent substantive evidence becomes `INSUFFICIENT_EVIDENCE`.

Ambiguous scope, forgotten metric methodology, and incomplete detail therefore
do not automatically become contradictions. Accepted changes flow through the
existing Claims Graph service and create auditable claim versions.

## Observability and limitations

Structured logs record execution ID, claim ID, related-turn count, proposed and
validated item counts, quote failures, applied recommendation, latency, model,
and prompt version. Full resumes and transcript text are not logged.

There is no candidate endpoint for forcing evidence or claim changes. This
milestone supplies the internal service boundary for workers and later
orchestration. It does not implement final scoring, readiness assessment, or a
candidate-facing report. Evidence is required before those later systems can
make defensible, inspectable calculations.

