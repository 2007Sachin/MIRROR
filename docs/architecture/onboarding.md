# Diagnostic onboarding

Mirror onboarding begins the readiness diagnostic. It is not a profile-preference questionnaire. The five-stage flow establishes a role benchmark, ingests starting evidence, lets the candidate review Mirror's interpretation, records the requested depth of inquiry, and prepares a real interview plan before the candidate begins.

## Route and lifecycle

Authentication still lands on `/app`. The server reads `/api/v1/onboarding`; incomplete profiles redirect to `/onboarding`, and completed profiles continue to the authenticated workspace. `/app/setup` remains as a compatibility route and redirects to the appropriate destination instead of rendering the retired setup flow.

The onboarding route contains these persisted stages:

1. **Role benchmark** — target role, optional company, and an optional uploaded or pasted role brief.
2. **Starting evidence** — PDF/DOCX resume ingestion followed by Resume Intelligence.
3. **Evidence map** — real capability signals, claims, role expectations, candidate claim review, and an explicit account of what documents alone cannot establish.
4. **Depth of inquiry** — one complete-readiness default or one or more specific areas for greater scrutiny.
5. **Interview thesis** — a prepared session and versioned interview plan grounded in the selected documents and role profile.

The final action marks onboarding complete and opens the existing evidence interview. The deterministic interview state machine continues to own preparation, readiness, start, phases, probes, timing, and termination.

## Persistence

Candidate onboarding remains on the owner-scoped `public.profiles` row and retains the legacy career-preference columns for backward compatibility. The diagnostic flow adds:

- `target_company`
- `onboarding_step`
- `onboarding_resume_document_id`
- `onboarding_role_brief_document_id`
- `onboarding_role_brief_skipped`
- `onboarding_role_profile_id`
- `onboarding_session_id`
- `inquiry_depth`

Selected IDs are foreign-keyed to existing document, role-profile, and session tables. A database trigger verifies that each referenced record belongs to the profile owner. No required diagnostic state is stored only in localStorage.

Existing profiles completed under the original career-preference flow remain valid. New diagnostic onboarding can complete without collecting unrelated career stage, intent, timeline, or language fields.

## Existing intelligence reused

- Resume uploads use the private `private-resumes` storage bucket and `documents` rows.
- Resume Intelligence performs deterministic PDF/DOCX parsing, validated provider analysis, claim extraction, and Claims Graph construction.
- Role Intelligence uses either the supplied job-description document or the synthetic canonical role fallback and updates `current_role_profile_id`.
- Candidate claim corrections use versioned `resume_claim_corrections`; they are not cosmetic client state.
- The Interview Planner loads the selected session documents, current role profile, claims, projects, competencies, existing evidence counts, and the persisted inquiry-depth preference.
- Session preparation uses `InterviewStateMachine` and changes the session to `READY` only after a validated plan completes. The final thesis reads the public, owner-scoped plan so its unresolved objectives are planner output rather than client-side readiness scoring.

## Role-brief upload

`POST /api/v1/documents/job-description/upload` accepts genuine PDF or DOCX files under the configured document-size limit. The API validates the declared type against the file signature, extracts text with the existing deterministic parser, stores the private source file, and creates a processed `JOB_DESCRIPTION` document. Empty or unparseable documents return a candidate-safe 422 response.

Pasted role briefs continue to use `POST /api/v1/documents/job-description`. Proceeding without a role brief remains supported; Role Intelligence explicitly records the synthetic canonical source.

## Session document linking

`POST /api/v1/sessions/{session_id}/documents` attaches owner-verified resume and role-brief documents through the existing `session_document_links` table. The operation is idempotent. Interview planning uses these links to select the intended resume analysis instead of relying on a browser-only selection.

## Inquiry depth

`inquiry_depth` is a constrained enum array. `COMPLETE_READINESS` is exclusive; specific areas may be combined. Planner prompt `v2` receives the values in its typed candidate profile and may increase relative objective depth in those areas. It must retain broad coverage, cannot lower the evaluation standard, and cannot override the deterministic two-probe cap.

## Candidate-facing interpretation

The evidence map renders only real Resume and Role Intelligence output. "What documents cannot establish" lists the role's most important competencies as areas whose demonstrated depth still requires conversational evidence; it does not infer failure from a missing keyword. The final thesis then uses high-priority objectives from the validated interview plan. Before the interview, no claim is labelled supported by interview evidence because that evidence does not exist yet.

## Recovery and errors

Every material step writes through `PUT /api/v1/onboarding`. Refreshing restores the selected documents, analyses, role profile, inquiry depth, prepared session, and current stage. Unsupported files, parsing failures, provider failures, timeouts, empty extraction, session-planning failures, authentication expiry, and restore failures use candidate-safe messages and preserve completed work.

## Explicit limitations

- The onboarding UI does not claim backend percentages or granular provider progress. Its changing analysis labels describe the active operation while the blocking analysis request runs; completion is shown only after the API confirms it.
- Voice is not added to onboarding. Existing voice infrastructure remains scoped to the evidence interview.
- A role brief is optional, but the UI explains that the resulting role benchmark is inferred rather than employer-specific.
