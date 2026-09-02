# Assessment adjudication

Assessment adjudication is a narrow internal step after specialist assessment.
It is not a verdict, score, report, or candidate-facing explanation.

`AssessmentDisagreementDetector` uses deterministic application rules and
centrally configured signal-gap thresholds. It identifies material differences,
including a strong technical signal paired with weak claims evidence, or
conflicting availability of specialist signal. It does not invoke a model to
decide whether a disagreement exists.

Only when the detector returns a disagreement does `AssessmentAdjudicator` call
the Adjudicator Agent. The bounded context includes that one disagreement, the
specialist bundle, relevant rubric, validated evidence, and claim state. It
omits unrelated transcript content. The result has an affected dimension,
position, confidence, validated evidence IDs, short reason, and source
specialist positions—never chain-of-thought.

The agent must preserve multidimensionality. Strong SQL reasoning and weak
ownership evidence are separate truths, not values to average into a mediocre
single conclusion. It may not invent evidence or change specialist records.

Adjudications are append-only `assessment_adjudications` records. Invalid
evidence, malformed model output, and model failures are safe no-ops: existing
specialist assessments remain unchanged. A future Verdict Agent may consume
these records, but is intentionally outside this milestone.

