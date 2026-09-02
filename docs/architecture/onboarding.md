# Candidate onboarding

Candidate onboarding is stored on the authenticated `public.profiles` row. It is preference and preparation context only; it does not trigger resume processing, multilingual interview behavior, or AI-agent work.

## Domain

The profile stores `career_stage`, `career_intent`, `target_role`, `interview_timeline`, `preferred_language`, optional `college_id`, and `onboarding_completed`. PostgreSQL enums and matching Pydantic enums reject unsupported values. The database allows partial rows while onboarding is in progress but prevents `onboarding_completed = true` until every required field except optional `college_id` is present.

## API boundary

`GET /api/v1/onboarding` reads the verified user's progress. `PUT /api/v1/onboarding` applies a partial update, allowing one completed frontend step to be persisted at a time. Both routes obtain the profile ID exclusively from `get_current_user()` and reject extra payload fields such as `user_id`.

The backend service-role repository always filters by the verified subject UUID. RLS remains the database backstop, while browser clients have no direct update grant for onboarding columns.

## Frontend routing and resume behavior

After authentication, `/app` performs a server-side onboarding lookup. Incomplete profiles redirect to `/onboarding`; completed profiles render the minimal app page. `/onboarding` performs the inverse redirect when setup is already complete.

The six screens are welcome, career intent and career stage, target role, interview timeline, preferred language, and confirmation. Each data-bearing step calls the partial `PUT` endpoint. On refresh, the server returns saved state and the client resumes at the first incomplete step. The role input uses a small suggestion list but accepts free text.

Preferred language is metadata only in this milestone. Interview prompts, transcription, speech, and assessment remain unchanged.

