# Post-session assessment pipeline

Completing an interview is deliberately separate from assessing it. The session state machine records the completed interview first; `POST /api/v1/sessions/{session_id}/end` then idempotently queues one `POST_SESSION_ASSESSMENT` job in PostgreSQL. It never calls an LLM on the request path.

`workers/assessor/worker.py` claims jobs with `FOR UPDATE SKIP LOCKED`, so several worker processes can run safely. A claimed job runs the existing isolated Technical, Behaviour, and Claims assessors, invokes the adjudicator only when the deterministic disagreement detector requires it, aggregates readiness deterministically, generates only the candidate-safe verdict language, and writes the existing `session_results` record.

```
completed session -> jobs POST_SESSION_ASSESSMENT -> assessor worker
  -> specialist assessments -> conditional adjudication -> deterministic aggregation
  -> verdict language -> session_results -> candidate report
```

Specialist outputs and adjudications remain immutable. Worker retries reuse already-stored specialist results, and a result written before a worker acknowledgement is detected and acknowledged without repeating assessment. Any failed specialist, required adjudication, aggregation, verdict, or persistence step leaves the job pending for bounded retry; it becomes `FAILED` after the configured attempt limit. A report is available only after `session_results` has been persisted.

Candidate clients can poll `GET /api/v1/sessions/{session_id}/assessment` after ending an interview. The status is intentionally neutral (`PENDING`, `PROCESSING`, `COMPLETED`, or `FAILED`) and never reveals model prompts, hidden scores, reasoning, or raw provider errors. Access is scoped to the authenticated session owner.

Production requires the Supabase service-role environment only in the API/worker runtime. The browser uses the existing authenticated API boundary and never receives database or worker credentials. For local unit tests without Supabase, a small in-memory queue preserves the endpoint contract; it is not a production execution backend.
