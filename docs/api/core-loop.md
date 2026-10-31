# Core practice loop API

Text Quick drill, from create through a labelled review. All routes need `Authorization: Bearer <access token>`. A missing or rejected token is **401**. Response bodies use `{"detail": "<sentence>"}` unless a **422** validation error returns FastAPI's `detail` list. There is no readiness percentage on the review. Report ranges, when present, are the existing low/high bounds, not a score.

Quick drill (`practice_mode: "QUICK_DRILL"` plus one `practice_focus`) builds a fixed plan of **3 questions, 1 follow-up each** (`max_probes: 1`, 300 seconds). Prepare does not call the Planner agent. Full interviews still do.

## Sequence

1. `POST /api/v1/sessions` → `201` `SessionRead` (`status: "CREATED"`, `practice_mode`, `practice_focus`, `total_time_budget_seconds`).
2. `POST /api/v1/sessions/{session_id}/prepare` → `200` `PrepareResponse`: `{session, claims_extracted, competencies_derived}`. `session.status` is `"READY"`.
3. `GET /api/v1/sessions/{session_id}/plan` → `200` `InterviewPlanResponse`. `plan.objectives` has length 3 and each `max_probes` is 1. `plan.planning_version` is `practice-plan-v1`.
4. `POST /api/v1/sessions/{session_id}/start` → `200` `InterviewStartResponse`: `session_id`, `interviewer_turn_index`, `question_text` (greeting plus the first planned question), `phase`, `turn_type: "PLANNED"`, `remaining_time_seconds`, `welcome_back`, `welcome_text`.
5. `POST /api/v1/sessions/{session_id}/turn-text` with `{"text": "...", "client_turn_id": "<uuid, optional>"}` → `200` `TextTurnResponse`: `session_id`, `candidate_turn_index`, `interviewer_turn_index`, `question_text`, `phase`, `turn_type`, `remaining_time_seconds`. One follow-up is `DEPTH_PROBE`; the next primary question is `RECOVERY`; the last turn is `CLOSING` and the session becomes `ASSESSING`. Repeating the same `client_turn_id` returns the same response.
6. `POST /api/v1/sessions/{session_id}/end` → `200` `SessionCompletionResponse` (`SessionRead` plus `assessment`). `status` is `"COMPLETED"`. `assessment.status` is `"PENDING"` until a worker runs. Ending again returns the same job.
7. `GET /api/v1/sessions/{session_id}/assessment` → `200` `AssessmentPipelineState`.
8. `GET /api/v1/sessions/{session_id}/report` and `GET /api/v1/sessions/{session_id}/review` stay **409** until a result exists, then **200**.

## Assessment states

`AssessmentPipelineState`: `session_id`, `status`, `retry_count`, `failure_code`, `queued_at`, `started_at`, `completed_at`.

`queued_at`, `started_at`, and `completed_at` are ISO-8601 timestamps or null, taken from the job row. `queued_at` is `jobs.created_at` (set when end first enqueues the job; retry does not rewrite it). `started_at` is `jobs.locked_at` (set when a worker claims the job; null while `PENDING`, including just after retry). `completed_at` is `jobs.completed_at`.

| `status` | Meaning | Report / review |
|---|---|---|
| `PENDING` | Queued. A live worker has not held it longer than the window below. Includes a backoff that is still in the future. | **409** |
| `PROCESSING` | A worker holds the lock, and `started_at` is inside the window. | **409** |
| `COMPLETED` | A result was stored. | **200** |
| `FAILED` | The worker finished in failure (`failure_code` is that error), or the job sat queued or locked too long (`failure_code: "assessment_stale"`). | **409** until a later attempt stores a result |

The window is not a separate setting. It is derived from `ASSESSMENT_JOB_MAX_ATTEMPTS` (default 3) and `ASSESSMENT_JOB_RETRY_BASE_SECONDS` (default 30): sum of the geometric backoff plus the last gap again, **330 seconds** at the defaults. A worker that is simply down leaves a fresh job `PENDING` (report/review **409**, not 500). After the window, reads return `FAILED` / `assessment_stale` instead of an endless `PENDING` or `PROCESSING`. A queued job can still be claimed if the worker returns; a lock that outlives the window is not claimed again until retry.

`POST /api/v1/sessions/{session_id}/assessment/retry` → `200` `AssessmentPipelineState`. From `FAILED` (including `assessment_stale`) it requeues one job and returns `PENDING` with `failure_code: null`. A second retry, a fresh `PENDING`, a live `PROCESSING`, or `COMPLETED` returns that state and does not add a job.

## Review

`200` `LatestReview`: `session_id`, `target_role`, `role_profile_id`, `completed_at`, `counts` (or `null`), `dimensions[]` (`key`, `label`, `state`, `note`), `improvements[]` (at most 3; `title`, `note`, `from_label`), `next_step` (`title`, `body`), `shorter_conversation`, `root_cause`, `practice_focus`.

`dimensions[].state` is one of: Strong, Clear, Developing, Could go further, Needs attention, Not enough to say yet. The object has no score and no readiness percentage.

`ReportResponse` is the body documented in `docs/api/report.md`. `verdict.label` is words. `role_readiness` and `interview_readiness` may include `low`/`high` bounds; they are not a single readiness percentage.

## Frontend assumptions

Checked against the handlers in `apps/api/app/main.py` and `report_service.py`, and against `LatestReview` in `dashboard_summary.py`. The web client calls the review body `SessionReview`; that is the same object as `LatestReview`.

1. **A 409 on report or review does not mean only "still preparing".** `GET /report` and `GET /review` return **409** when the review is not stored yet: the session is not `COMPLETED`, or it is `COMPLETED` but no result row exists. A `FAILED` job (worker error or `assessment_stale`) has no result, so it is also **409**. Read `GET /assessment` to tell `PENDING` or `PROCESSING` from `FAILED`. **404** means the session or review is missing. **503** means storage is unavailable, not that work is still running.
2. **Work items are `improvements` on that review body.** Each item is `title`, `note`, and `from_label` (`from_label` is null when the item is the growth area rather than a claim). The server already returns at most three. The report payload has no `improvements` list.
3. **Elapsed time uses the server timestamps, not when the page opened.** While `PENDING`, the wait is now minus `queued_at`. While `PROCESSING`, the worker's time is now minus `started_at`. The browser may tick from those values. A clock that starts at page load is not the source: a reload would show zero, and it would ignore time the job had already waited. Retry leaves `queued_at` where it was and clears `started_at`.

## Errors

| Status | When | Retry? |
|---|---|---|
| **401** | No bearer token, or the token is rejected. | After signing in. |
| **404** | Session, plan, or assessment job is missing, or it belongs to someone else. Review uses the same rule. | No, unless the id was wrong. |
| **409** | Prepare/start/turn/end is illegal for the current status; the plan is not ready; resume or role analysis is still required; the session changed concurrently. Report and review use **409** while the result is not stored (`PENDING`, `PROCESSING`, or `FAILED` with no result yet). | Yes for a stale read or a not-ready review. Refresh, or retry the assessment when `status` is `FAILED`. |
| **422** | Create body is inconsistent (quick drill without a focus, unknown mode) or `text` is blank. | Fix the body. |
| **502** | Prepare ran and the plan did not complete. | Yes. |
| **503** | Planning, turns, or assessment storage is unavailable. Assessment retry also returns **503** when the completed session cannot be loaded. | Yes. |

A down worker is **409** on report/review and `PENDING` or, after the window, `FAILED` on the assessment. It is not **500**.
