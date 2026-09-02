# Candidate report API

`GET /api/v1/sessions/{session_id}/report` returns the normalized, candidate-safe report for a completed interview.

The route requires the authenticated session owner. Reports are unavailable until the session is `COMPLETED` and a session assessment result exists. The aggregation service reads the session, result, claims, validated evidence, specialist assessments, and session events in bounded collection queries; route handlers do not assemble database records.

Internal model names, prompt versions, raw assessor payloads, hidden scores, suspicion signals, and chain-of-thought are intentionally excluded. Ranges are returned only when the stored assessment provides them. A `Not enough signal` readiness object has null numeric bounds rather than fabricated precision.

Example (sanitized):

```json
{
  "session": {
    "target_role": "Data Analyst",
    "completed_at": "2026-09-01T12:00:00Z",
    "duration_seconds": 1120,
    "assessment_confidence": 0.8
  },
  "verdict": {
    "code": "NEAR_READY",
    "label": "Near ready",
    "summary": "Your technical fundamentals are credible, with a few areas to strengthen."
  },
  "role_readiness": {
    "low": 61,
    "high": 68,
    "label": "Available",
    "signal_strength": "STRONG",
    "confidence_note": "This range reflects the amount and quality of evidence collected."
  },
  "interview_readiness": {
    "low": 54,
    "high": 63,
    "label": "Available",
    "signal_strength": "MODERATE",
    "confidence_note": "This range reflects the amount and quality of evidence collected."
  },
  "claims_audit": {
    "held": [],
    "partially_held": [],
    "walked_back": [],
    "contradicted": [],
    "insufficient_evidence": [],
    "unverified": []
  },
  "skill_assessments": [],
  "session_moments": [],
  "root_cause": "TECHNICAL_DEPTH",
  "trust_and_limitations": {
    "ai_assessments_can_make_mistakes": true,
    "candidate_may_dispute_assessments": true,
    "skills_may_have_insufficient_signal": true,
    "evaluates_this_interview_evidence": true,
    "outcome_validation_status": "NOT_VALIDATED"
  },
  "prescription": null
}
```

Outcome validation is explicitly reported as `NOT_VALIDATED` until the product has real outcome data; this endpoint makes no placement prediction.

