# Verdict Agent

`FinalAssessmentAggregator` deterministically creates internal readiness values, candidate-facing ranges, confidence, availability, verdict code, and one root-cause code from specialist signal strength and fixed weights. Lower signal widens ranges.

The Verdict Agent receives those fixed values plus bounded summaries and Claims Audit data. It writes only calm, direct language: a summary, root-cause explanation, and confidence note. Its schema has no numeric, verdict-code, or root-cause fields, so it cannot alter aggregation. It must not invent claims, use dishonest framing, motivational language, or candidate-facing verdict drama.

