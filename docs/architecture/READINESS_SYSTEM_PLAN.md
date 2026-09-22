# Interview readiness system — implementation plan

Status: Phases 0–3 implemented on branch `ui-redesign` (uncommitted). Stopped before Phase 4 for a product decision (§8).

Mirror is moving from "resume + JD → mock interview → report" to a preparation system that answers
one question: *am I ready to defend my experience for this specific role?* The mock interview becomes
one component of a loop:

My Experience → Target role → Interview Map → Pressure test → My Stories → Practice → Review → Try again
→ Interview tomorrow → Debrief → Updated preparation.

This plan is grounded in the repository as audited on 2026-09-22. It extends existing systems; it does
not replace the interview engine, the assessment pipeline, or the agent runtime.

## 1. Current architecture (what exists)

| Capability | Where | Reuse in the readiness system |
|---|---|---|
| Resume Intelligence | `resume_service.py`, `resume_models.py`, table `resume_analyses` + `claims` | Skills, work, projects, achievements and **claims** (type, `verification_priority`, `metric_value`, `ownership_language`, `outcome`, `source_reference`) — the raw material for the Interview Map's candidate side and for pressure-test questions |
| Role Intelligence | `role_service.py`, tables `role_profiles`, `role_analysis_versions`, `role_competencies` | Competencies with `importance_weight`, category, expected level and a JD `source_reference`; interview themes, must/nice-to-have, behavioural and domain expectations — the role side of the map |
| Roles list | `GET /api/v1/roles` (added in the UI phase) | Role workspace index |
| Planner | `planner_service.py`, prompt `planner/v3` | Unchanged. Already accepts `inquiry_depth`; practice modes (Phase 4) will map onto it |
| Interview engine | `interview_engine.py` | Unchanged. Owns lifecycle, probes, timing |
| Skeptic | `skeptic_processor.py`, `skeptic_models.py` | Bound to live interview turns (`SkepticContext.current_turn`). It powers pressure *inside* a conversation (Phase 4 pressure mode); it is not reused for the pre-interview pressure test, which needs no LLM |
| Claims graph, evidence, resolution | `claims_*`, `evidence_*`, `claim_resolution_*` | Internal support model; stays hidden |
| Specialists, adjudication, verdict | `assessment_*`, `verdict_service.py` | Unchanged; feed the review |
| Report + candidate reading | `report_service.py`, `dashboard_summary.py`, `progress_summary.py` | `build_latest_review` is the single plain-language reading of a review; the map reads its dimensions |
| Documents / My Experience | `document_library_service.py`, `/experience` | Canonical factual source ("what happened") |
| Candidate language | `apps/web/src/lib/copy.ts`, `lib/*-view.ts`, `scripts/copy_lint.py` | Every new string goes through `copy.ts` and the banned-word lint |
| Background jobs | `assessment_worker.py` (Supabase job queue) | Available if a later phase needs async work; Phases 1–3 are synchronous and deterministic |
| Analytics | none | Not added (see §10) |
| Entitlements / billing | none | Not added (see §10) |

## 2. Product architecture decisions

**Navigation.** Global: Home, Practice, My Stories, My Experience, Roles, Progress. The Interview Map
and the Pressure Test are *per role*, so they live in the role workspace rather than the sidebar:

- `/roles/[id]` — Role workspace: overview, **Interview Map**, practice history
- `/roles/[id]/pressure-test` — Resume Pressure Test, ordered by what this role cares about
- `/stories`, `/stories/[id]` — My Stories (global: a story is reusable across roles)

**Experience vs Story.** Experience is what happened (documents, resume analysis). A Story is how the
candidate explains it in an interview. Stories reference experience but never overwrite it.

**No new scores.** Coverage, preparedness and story completeness are named states, each backed by
an inspectable reason. Review and progress keep the four review states; the map and stories use
their own preparation states (§6). No percentages.

**Derived before persisted.** The Interview Map is computed on read from role analysis + resume
analysis + stories + the latest review for that role. It has no table of its own: every input is
already versioned, so a persisted copy would only go stale.

## 3. Phase plan

| Phase | Deliverable | Persistence | Needs an LLM? |
|---|---|---|---|
| 0 | This plan | — | — |
| 1 | **Interview Map** — `interview_map.py`, `GET /api/v1/roles/{id}/interview-map`, role workspace UI, Home "next step" hook | none (derived) | No |
| 2 | **Resume Pressure Test** — deterministic question generation per resume claim, self-readiness, "prepare this answer" | `pressure_test_responses` | No |
| 3 | **My Stories** — CRUD, create from pressure test, "Help me find a story" guided prompts; stories count toward map coverage | `stories` | No |
| 4 | Practice modes (full / pressure / focused / quick drill) | session `practice_mode` column | Planner input only — **stop and confirm first** (§8) |
| 5 | Try again / answer attempts | `answer_attempts` | A single-answer reading agent (new, bounded) |
| 6 | Review integration (Try again per answer) | — | — |
| 7 | Progress integration (attempt history, pressure handling) | — | — |
| 8 | Interview tomorrow + questions to ask | `interview_events` | Questions derived from JD; **no company research** without a retrieval source |
| 9 | Debrief + outcomes | `interview_debriefs` | No (candidate-reported; causal claims forbidden) |
| 10 | Home / role workspace refinement | — | — |

## 4. Data model (additive migrations only)

Mapped against existing schema first:

| Concept | Decision |
|---|---|
| TargetRole | **Reuse** `role_profiles` |
| InterviewTheme / PreparationArea / CandidateCoverage / SuggestedQuestion | **Derived** in `interview_map.py`, not stored |
| PressureTestItem | **Derived** from `claims` rows of the latest resume analysis |
| ResumePressureTest (self-readiness) | **New** `pressure_test_responses (user_id, claim_id, readiness, updated_at)`, unique per claim |
| Story, StoryTheme, StoryRoleLink | **New** `stories` with `themes text[]` and nullable `role_profile_id`, `source_claim_id`, `source_document_id` (no join tables until a story needs many roles) |
| PracticeSession / PracticeMode | **Reuse** `sessions`; Phase 4 adds a `practice_mode` column |
| AnswerAttempt | Phase 5 `answer_attempts` referencing `turns` |
| InterviewEvent / InterviewDebrief | Phase 8–9. Legacy `public.outcomes` references the retired `users` table and a fixed result enum, so it is not reused |
| ProgressSnapshot | **Derived** (`progress_summary.py`) |

All new tables follow the existing convention: `user_id → profiles(id) on delete cascade`, RLS
`select_own` for `authenticated`, writes only through the backend `service_role`.

## 5. API changes (Phases 1–3)

- `GET  /api/v1/roles/{role_profile_id}/interview-map`
- `GET  /api/v1/roles/{role_profile_id}/pressure-test`
- `PUT  /api/v1/pressure-test/{claim_id}` — `{ readiness: CAN_EXPLAIN | NEEDS_PREPARATION }`
- `POST /api/v1/answer-checks` — presence-only notes on a practice answer; nothing stored
- `GET/POST /api/v1/stories`, `GET/PATCH/DELETE /api/v1/stories/{id}`

All owner-scoped through `get_current_user`; nothing accepts a client user id.

## 6. Interview Map logic (Phase 1)

Role side: competencies sorted by `importance_weight` (top 6 become *likely themes*), plus interview
themes and behavioural expectations from the validated role output.

Candidate side: resume skills, tools, work, projects and claims; the candidate's stories; the
latest review's dimensions for this role.

Coverage per theme, deterministic and explained (codes in `interview_map.Coverage`):

- **PREPARED** — "Story ready": a story the candidate wrote is tagged with, or names, the theme.
- **EXPERIENCE** — "Useful experience": a job, project or achievement on the resume uses it.
- **MENTIONED** — "Mentioned, not yet shown": the resume names it as a skill or tool, but no work shows it being used.
- **MISSING** — "No example yet": nothing in the candidate's material speaks to it.

These are deliberately *not* the review states (`Coming through clearly` … `Not explored yet`): before
an interview there is no interview evidence, so the map describes preparation, not performance. The
latest review for the role contributes a preparation area (e.g. measurable impact) rather than a
per-theme state.

Each coverage carries the matched resume text so the reason is inspectable. Suggested questions come
from fixed templates per competency category and are labelled "Questions worth preparing for", never
"the interviewer will ask". The map never invents experience: an empty resume yields an empty
candidate side and a single honest instruction.

## 7. Pressure test logic (Phase 2)

For each resume claim (highest `verification_priority` and most role-relevant first), questions are
chosen from what the claim itself leaves open:

- no `metric_value` on an OUTCOME/SCALE claim → "How did you measure that?"
- `ownership_language` like "supported"/"helped"/"part of" → "Which part did you personally own?"
- no `outcome` → "What changed because of this work?"
- TOOL/SKILL claim → "Walk me through a time you used this and why it was the right tool."
- always one decision question → "What alternative did you consider?"

Framing is "make sure you can explain this clearly when someone digs deeper", never "prove it".

## 8. Stop point before Phase 4

Practice modes change what the planner and engine receive (duration, probe intensity, focus).
`planner/v3` already accepts `inquiry_depth`, so a first version can map modes onto existing inputs
without a prompt change, but a real quick drill (three questions, immediate retry) needs a shorter
engine path. That extends the interview engine, so it is confirmed with the product owner before
implementation.

## 9. Testing plan

Pure functions for map, coverage, question generation and story completeness are unit-tested without
an LLM or database. Services are tested with in-memory repositories. Routes are tested for ownership
(404 for another user's role/story, 401 unauthenticated). Frontend contracts are asserted in
`tests/unit/*_frontend_contract.py`. Every phase runs `npm run lint`, `npm run test`, `npm run build`.

## 10. Risks and explicit non-goals

- **Word-overlap coverage is coarse.** It is labelled honestly and explained per item; a semantic
  matcher can replace `coverage_for` later without changing the contract.
- **No analytics pipeline exists.** Events listed in the brief are not instrumented; adding PostHog
  would be new infrastructure and needs a decision.
- **No entitlements exist.** New features are not gated; access checks should be introduced in one
  backend module when billing is designed.
- **Company research** is not available; Interview Tomorrow will use only the role brief and the
  candidate's own material, and say so.
- **Uncommitted working tree.** Phases 1–3 build on earlier uncommitted UI work, so commits are left
  to the product owner rather than mixing unrelated local changes into one commit.
