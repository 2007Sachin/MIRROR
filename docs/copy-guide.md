# Mirror copy guide

Mirror is a calm place to practice talking about your experience. Everything people read or hear should feel kind, plain and unhurried. Soften the language, never the truth.

The central copy lives in `apps/web/src/lib/copy.ts`. Run `npm run lint:copy` before you commit copy changes.

## Tone

- Speak to "you". Never "the candidate" or "the user".
- Warm and encouraging, never gushing or fake.
- Short sentences and plain words. No jargon, no clinical or corporate language.
- No alarm words and no urgency pressure.
- Frame everything as practice and growth, never pass or fail.
- Say what came through well before what can grow. End on one small, doable next step.
- Spoken lines must sound natural read aloud: short, conversational, no bullets or symbols.
- "Not enough to say yet" is a valid outcome. Never guess.
- Never claim something the product does not do. Reassure only where the code backs it up.

## Glossary

| Instead of | Use |
|---|---|
| Diagnostic | Practice session (a finished one: "Your reflection is ready") |
| Diagnostics (nav or list) | Your sessions |
| Evidence library / workspace | Experience library / Your space |
| Evidence (an item) | Your work / materials ("Add your work") |
| Claims audit | What came through |
| Your verdict | Your summary |
| Your main bottleneck | Your main growth area |
| Skeptic (visible to users) | Deeper Questions |
| Assessor (visible to users) | Reflection Guide |
| Not enough signal / evidence | Not enough to say yet |
| Held | Came through clearly |
| Partially held | Mostly came through |
| Walked back | Refined during the conversation |
| Contradicted / unsupported | Worth revisiting |
| Unverified | Not yet explored |
| Retry evaluation | Try again |
| Evaluating evidence | Reflecting on your answers |
| Candidate | you |
| Strong evidence | Came through strongly |
| Recovered after hesitation | Found your footing |
| Ownership became clearer | Your role became clearer |
| Metric could not be substantiated | A number worth explaining |
| Benchmarking / role benchmark | Getting to know the role / Your target role |
| Interview thesis | Your conversation plan |
| Lines of inquiry | Areas to explore |
| Claims worth examining | Moments worth talking through |
| What remains unproven | What's still to explore |

## Banned words (fail the lint)

evidence, diagnostic(s), assessment(s), assessor, skeptic, score(d/s), weakness, gap(s), deficiency, fail(ed/ure), incorrect, wrong, red flag, critical, candidate, verdict, evaluate/evaluation, analysis/analysed, audit, test/tested, verify/verified, proof, performance, scrutiny, substantiate, flag.

Matching is by whole word, case-insensitive, with inflections. Class names, identifiers, imports and internal exception messages are not scanned.

## Soft-avoid words (warn only)

claim(s), benchmark, thesis, inquiry, probe/probing, challenged, unproven, bottleneck. Prefer the glossary alternatives.

## Where the lint applies

- Tier 1 (fails): `apps/web/src/lib/copy.ts`, string literals and JSX text in `apps/web/src`, user-facing API error details in `apps/api/app/main.py`, the Interviewer prompts, and the Verdict prompt.
- Tier 2 (no lint): the internal reasoning prompts (Skeptic, Assessor, Adjudicator, Evidence, Planner, Resume, Role) and internal docs. Internal prompts whose free text reaches people carry an "Output tone" section that repeats this guide.
- Generated reports are checked after generation. If a banned word slips through, the report is generated once more, then falls back to a safe default sentence, and the event is logged.
