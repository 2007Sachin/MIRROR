# Scoring contract

Role Readiness and Interview Readiness remain separate. The primary UI uses bounded ranges and a descriptive band, never a single point score or unsupported percentile.

An assessment row may be `scored` only when every dimension is present and at least one candidate quote and candidate turn id support it. The database and Pydantic model both enforce this rule. Fewer than roughly two substantive exchanges produces `not_enough_signal`, with no numeric fields.

The Assessor stores provider, model, model version, prompt version, and rubric version. A calibrated Assessor model must not be changed silently. Synthetic cases can test infrastructure but cannot establish real bands, percentiles, AUC, or hiring validity.

Contradiction flags are allegations, not facts. Ambiguous team/personal differences prefer `ownership_drift`; observations below confidence 0.65 stay in shadow data and cannot produce a live probe.


