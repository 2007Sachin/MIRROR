# Specialist assessors

Mirror separates post-session assessment into three narrow, independent agents.
This reduces category leakage and makes later review more inspectable. The
legacy Assessor V1 schema remains untouched as a temporary compatibility path;
these results do not change the candidate-facing API, create a verdict, or
produce a report.

| Assessor | Owns | Must not judge |
|---|---|---|
| Technical | Demonstrated role capability, reasoning, trade-offs, implementation and project depth | Style, nervousness, ownership stability unless it changes competence |
| Behaviour | Clarity, structure, communication, recovery, specificity and follow-up response | Personality, psychology, health, accent, grammar variation, Indian-English usage, technical competence |
| Claims | Ownership specificity, claim consistency, outcome/metric support and evidence quality | Honesty score, dishonest labels, treating all self-correction as negative, low skill as dishonesty |

`AssessmentOrchestrator` loads a bounded internal context for each assessor and
runs the three calls concurrently. Assessors cannot call each other, access SQL,
or change claims, scores, sessions, or lifecycle state. Each output is strictly
validated and stored as an immutable `specialist_assessments` row.

Every assessment must either provide traceable transcript turn IDs and exact
quotes, or return `NOT_ENOUGH_SIGNAL`. The orchestrator rechecks quotes against
the supplied stored transcript with the same exact/normalized matching policy
as the Evidence layer. Hallucinated quotes are rejected before storage.

The orchestrator records signal-availability differences as descriptive
disagreements only. It deliberately performs no reconciliation or adjudication;
that responsibility belongs to the future Verdict Agent. All prompts treat
resume, transcript, claim, flag, and evidence content as untrusted input.

