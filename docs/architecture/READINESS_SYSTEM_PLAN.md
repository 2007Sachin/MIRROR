# Interview readiness system — implementation plan

Status: Phases 0–6 implemented. Practice is now role-explicit (see §11). Home is specified in HOME_SPEC.md but not implemented. Still paused before Phase 7 (Progress).

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
| StoryVersion | **New** `story_versions`: append-only content history per story; `stories` gains `archived_at` and `current_version` (see section 12) |
| StoryRoleFraming | **New** `story_role_framings (story_id, role_profile_id, themes, emphasis)`, unique per story and exact role; `stories.role_profile_id` is kept as provenance (see section 13) |
| PracticeStoryUsage | **New** `practice_story_usages (session_id, story_id, story_version_id, role_profile_id, position)`: a story the candidate chose for a practice, at the exact version practised (see section 14) |
| StoryImprovementSuggestion | **New** `story_improvement_suggestions`: a Review finding about one chosen story, pinned to the version practised; OPEN / ACCEPTED / DISMISSED (see section 15) |
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
- `GET/POST /api/v1/stories` (`?archived=true` lists archived stories), `GET/PATCH /api/v1/stories/{id}`
- `POST /api/v1/stories/{id}/archive`, `POST /api/v1/stories/{id}/restore` — hard delete was removed
- `GET /api/v1/stories/{id}/versions`, `GET .../versions/{version_id}`, `POST .../versions/{version_id}/restore`
- `GET /api/v1/stories/{id}/roles`, `PUT /api/v1/stories/{id}/roles/{role_profile_id}` (add or update), `DELETE` the same path (remove that role only)
- `POST /api/v1/sessions` accepts `story_ids` (story practice only); `GET /api/v1/sessions/{id}/stories`; `GET /api/v1/stories/{id}/practice`; `GET /api/v1/story-practice` (per-story counts)
- `GET /api/v1/sessions/{id}/story-suggestions`, `GET /api/v1/stories/{id}/suggestions`, `GET /api/v1/story-suggestions` (open only), `POST /api/v1/story-suggestions/{id}/dismiss`, `POST /api/v1/story-suggestions/{id}/accept` (`{saved_version}`)

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

## 11. Phases 4–6 as built

**Practice modes (Phase 4).** `sessions` gained `practice_mode`, `practice_focus`,
`practice_theme`. The engine sets shorter budgets for short modes; the planner builds a fixed
plan for them (`practice_modes.build_practice_plan`) instead of calling the Planner agent, so a
drill is ready immediately. The interviewer now enforces each objective's `max_probes`, which
is how a drill allows one follow-up. Full interviews are unchanged apart from honouring the
planner's own per-objective limits, which were previously advisory.

**Try again (Phase 5).** `answer_attempts` rows copy the question and original answer and add
the retry, numbered per answer and immutable. One `retry_comparison` agent call per attempt
returns PRESENT/ABSENT per aspect plus two screened sentences; everything shown as "what
changed" is derived from those pairs. On any failure the deterministic presence checks from
Dig Deeper are used instead and the attempt still saves.

**Review (Phase 6).** Up to three items need work; each is matched to an answer the review
itself marked "could be clearer" for Try again, otherwise it offers practice. The growth-area →
practice mapping lives once, in `dashboard_summary.PRACTICE_FOCUS_FOR_ROOT_CAUSE`.

## 12. My Stories: version history and archive

**Model.** `stories` stays the canonical story: stable id, owner, provenance (`origin`,
`source_text`, `source_claim_id`, `source_document_id`), the latest content, `current_version`
and `archived_at`. `story_versions` holds one read-only row per saved content state
(`title`, `themes` and the nine story parts), numbered per story with
`unique (story_id, version)`, plus `change_reason` (`CREATED`, `MANUAL_EDIT`, `RESTORED`) and
`restored_from_version`. Latest content was deliberately left on `stories` rather than read
through a version pointer: the Interview Map, Dig Deeper linking and the dashboard all read
story fields from `stories`, and none of them had to change.

**Invariants**

- A story's id never changes. Edits, restores and archiving all act on the same row.
- Versions are written by database triggers in the same transaction as the story change
  (`stories_track_version`, `stories_record_version`), so an edit cannot land without its
  version and application code never writes `story_versions` directly.
- A version is created only when content differs (`IS DISTINCT FROM` on the content columns).
  Saving unchanged content, archiving, restoring from the archive or changing the role does not
  add one. The API also skips the write when nothing changed.
- Versions are immutable: an `UPDATE` on `story_versions` raises. They are removed only when
  their story is (account deletion cascades).
- Restoring an earlier version never moves history backwards. `restore_story_version` (service
  role only) copies that version's content onto the story, which becomes a new version with
  `change_reason = RESTORED` and `restored_from_version` set. History stays v1, v2, v3, v4.
- Archive is reversible and non-destructive. Archived stories are excluded from
  `list_for_user`, so they stop counting toward Interview Map coverage and are no longer
  linked from Dig Deeper, but `GET /stories/{id}` and its versions still resolve. An archived
  story is read-only (edits and version restores return 409) until it is restored.
- Provenance is never versioned or rewritten; it lives once on `stories`.
- Ownership is checked on every read and write in the repository (`user_id` filter), by the
  version ownership trigger, inside the restore RPC (story owner, version belongs to that story,
  story active), and by RLS (`story_versions_select_own`).

**Backfill.** The migration gives every existing story a version 1 (`CREATED`) with its current
content, dated at its last `updated_at`. Edits made before this migration were not recorded and
cannot be reconstructed.

**Dig Deeper.** "Save as story" still calls `POST /api/v1/stories` with `origin = PRESSURE_TEST`;
the insert trigger writes version 1 automatically. Story creation has no idempotency key of its
own: once saved, the Dig Deeper item links to the story instead of offering Save again, which is
unchanged behaviour. Dig Deeper never edits an existing story.

**Historical stability, known limit.** Practice sessions, answer attempts and reviews do not
record a story id or version today, so there is nothing for them to lose when a story changes;
equally, a past practice cannot yet say which version of a story it used.

**Deferred (not built):** tracking which stories a practice used; Review-driven suggestions to
improve a story. Practice and Review never modify a story. (Multi-role framing: section 13.)

## 13. My Stories: one story, many roles

**Rule.** Role framing changes how a story is presented and where it counts. It never changes
the canonical facts of what happened.

    Canonical story (stories)  ->  versions (story_versions)  ->  archive / restore
                               ->  zero, one or many role framings (story_role_framings)

**What a framing stores.** `story_id`, the exact `role_profile_id`, `themes` (up to 12, extra
Interview Map areas this story helps with for that role) and an optional `emphasis` note (up to
500 characters, candidate-written: what to lead with for that role). It never holds the title,
situation, actions, outcome or any other story part. One framing per story and role
(`unique (story_id, role_profile_id)`); saving again updates it in place.

**Global stories and Interview Map semantics.** Framing adds, it never restricts:

- A story's own `themes` count toward every role's Interview Map, exactly as before this change.
  A story with no framing is "Useful across roles".
- A framing's `themes` count only for that exact `role_profile_id`, added to the story's own
  themes (duplicates folded). Two roles with the same name are different roles; nothing is ever
  matched by role name.
- Archived stories count for no role; their framings are kept and return with the story on
  restore. Coverage logic and scoring are unchanged: only the theme list each story offers for
  the requested role changed (`readiness_service.story_evidence`).

**Originating role.** `stories.role_profile_id` stays as provenance: the role a story was first
written for (Dig Deeper, "Help me find a story" from a role). It is set on create only and can no
longer be changed through `PATCH`. The migration backfills a framing for every story that has
one (archived included), and an `AFTER INSERT` trigger frames new stories for their originating
role in the same transaction. Removing that framing later leaves the provenance untouched.

**Independence from history and archive.** Adding, editing or removing a framing never creates a
story version and never touches `stories`. Editing the story or restoring an earlier version never
touches framings. Framings on an archived story are read-only (409) until it is restored.

**Roles going away.** Roles are not deleted in the app. If a role profile is ever removed (account
deletion), its framings cascade away; the story stays, and `stories.role_profile_id` becomes null
as it always has.

**Ownership.** The API checks that the story and the role both belong to the caller (404
otherwise); the `story_role_framings_verify_ownership` trigger checks the same in the database and
stops a framing moving to another story or role; RLS limits reads to the owner; only the service
role writes.

**Reuse over duplication.** Adding a role to an existing story is the only way to reuse it; there
is no copying. The new-story page, when opened for a role, points to My Stories to reuse a story.
No fuzzy duplicate detection or merging.

**Deferred:** Review story improvement suggestions. (Practice usage: section 14.)

## 14. Practice ↔ story usage

    Canonical story -> version -> role framing
                    -> practice usage (practice_story_usages) -> session (exact version, exact role)

**What "used" means.** A story is used by a practice only when the candidate chose it for that
practice ("Practise this story" on the story page) and the practice plan was built from it.
Existing, matching an Interview Map theme, being framed for the role or being shown anywhere
never creates a usage. Before this change no practice flow carried a story identity at all
(sessions, the planner input, focused practice, quick drills, full interviews and Try again
knew only role, focus, theme and resume claims), so this explicit choice is the only source.

**Session types.**

| Type | Uses stories? | Where the story comes from | When usage is written |
|---|---|---|---|
| Quick drill / focused practice, focus `story` | Yes, 1 to one-per-question (3 or 4) | `SessionCreate.story_ids`, chosen by the candidate | When the session is created |
| Quick drill / focused practice, other focus | No | — | — |
| Full interview | No (planned by the Planner agent from resume and role) | — | — |
| Try again (answer attempts) | No (retries a transcript answer, not a story) | — | — |

**Flow.** `POST /sessions` with `story_ids` → each story must be the caller's own and active →
its current version is pinned → the session is created → one usage row per story (exact
`story_version_id`, the session's exact `role_profile_id`, `position` in plan order). The
practice plan (`InterviewPlanningService._practice_plan`) then loads those pinned versions and
asks about each one (`practice_modes.chosen_story_questions`: objective *n* is about story
*((n − 1) mod count) + 1*). Because the plan is built from the pinned versions, an edit between
creating and planning a practice cannot make the plan and the usage disagree.

**Rules**

- Usage is actual practice usage, not relevance.
- Usage is immutable history (update trigger rejects changes; the role reference alone clears if
  that role profile is ever removed).
- Story edits never rewrite usage: an older practice keeps pointing at the version it used; a new
  practice pins the new version.
- Archived stories cannot be newly chosen (API 409 and the database trigger) but keep every
  earlier usage; restored stories can be chosen again.
- Exact `role_profile_id` only, and it must equal the session's own role; same-named roles stay
  apart.
- Replays are safe: the same idempotency key returns the same session, and usage is only written
  for a session that has none, with `unique (session_id, story_id)` and `unique (session_id,
  position)` as backstops. (This change also makes the Supabase session repository return the
  existing session on a replayed key instead of failing on the unique index.)
- Counts are not scores. "Practised N times" counts only practices that were started; nothing
  rates a story, and practices set up but never started are listed as such.
- Role framing is not used by the practice plan today (questions use the story's title from the
  pinned version), so usage does not record a framing.

**Review linkage.** `GET /api/v1/sessions/{id}/stories` gives Review, later, the exact stories and
versions a session used, with their plan positions; Review does not guess.

**Historical limitation.** Sessions before this change never recorded a story, so usage starts
from this migration; nothing is backfilled or inferred.

**Not planned here:** story scores, strength labels,
analytics, merging or duplicate detection.

## 15. Review → story improvement suggestions

    Canonical story -> version -> practice usage -> Review finding
                    -> improvement suggestion -> candidate's own edit -> new story version

**Source of truth.** Suggestions come only from `skeptic_observations`: typed findings the Skeptic
stores about one candidate answer (`source_turn_id`) with a confidence. Two types name exactly one
story part and are the only ones used (`story_suggestions.ISSUES`):

| Observation | Suggestion | Story part |
|---|---|---|
| `OWNERSHIP_DRIFT` | `OWNERSHIP_UNCLEAR` | `ownership` |
| `UNSUPPORTED_SCALE` | `RESULT_UNSUPPORTED` | `measurable_result` |

Vagueness, contradictions and other types do not say which part to work on, so they create
nothing. The confidence bar is `skeptic_live_probe_min_confidence`, the same bar the Skeptic must
clear to act live. The report's `OWNERSHIP_CLARIFICATION`/`UNSUPPORTED_SCALE` session moments are
not used: nothing in the code emits those events today.

**Attribution.** A chosen-story practice plan now gives each question the objective id
`story-<position>-<n>` (`practice_modes._objective_id`); the interviewer already stores the
objective id on every turn (`turns.primary_thread_id`). So: observation → answer turn → its
objective → the usage at that position → exact story, `story_version_id` and `role_profile_id`.
Generic plans keep `practice-<focus>-<n>`, so an answer to a question not about a chosen story
can never be attributed. Anything unresolvable creates nothing.

**When.** Derived when a finished practice's suggestions are read (`GET .../story-suggestions` from
Review, or a story's suggestions page, which also derives for that story's finished practices).
Keyed by `unique (session_id, source_turn_id, issue_type)`, so re-reading never duplicates and never
reopens a closed suggestion.

**AI boundary.** Deterministic. No model call is made for suggestions; the Skeptic's own summary is
never shown. Candidate-facing text is fixed copy per issue type, phrased as guidance ("Add what you
decided, did or changed yourself"), never replacement content.

**Rules**

- Review never changes a story. It only offers "Improve story" (opens the editor with the suggestion's
  context, focusing that part) and "Dismiss".
- A suggestion references the exact version practised and keeps it forever; if the story has moved on,
  the UI says the feedback is about the version practised.
- Accepting needs an intentional edit: after the candidate saves from the suggestion, the server
  accepts only when that save produced a newer version than the one practised and changed the
  suggestion's part; it records `resolved_by_story_version_id`. Saving nothing, or changing another part,
  leaves it open. Editing a story elsewhere never accepts anything.
- Dismissed suggestions stay as history; the story is untouched.
- Status moves once, from OPEN (database trigger). Sources never change.
- Archived stories keep their suggestions; Improve is hidden and acceptance refused until restored.
- Exact role: a suggestion carries its usage's role; another same-named role's review never shows it.
- Nothing is scored. My Stories shows only "N improvements to review".

**Historical limitation.** Older reviews cannot receive suggestions: before chosen-story plans used
`story-<p>-<n>` objective ids, no answer could be tied to a story. Nothing is backfilled.

## 16. My Stories: the user-facing model and UX consolidation

Sections 12–15 each added real capability (history, role reuse, practice usage, suggestions).
Built one at a time, they had started to read as separate features bolted onto a story rather
than one workspace. This section is a product/UX pass over the same capabilities: no schema,
API or versioning semantics changed.

**The model a candidate should recognise**, in their own words, not the implementation's:

    Experience (what happened)
      -> Dig Deeper (Mirror asks what's missing, one focused question at a time)
      -> Story (how you'll tell it — yours to edit, reused across roles)
      -> Practise (test how it comes across)
      -> Review (what came through, what didn't)
      -> Improve (an intentional edit, only if you choose to make one)
      -> Practise again

Experience is the record of what happened and stays factual. A Story is the candidate's own
retelling, written for interviews. Practice tests how a Story comes across out loud. Review
turns that into something concrete to act on. None of this is exposed by those names to the
candidate — "Dig Deeper", "usage" or "framing" are engineering shorthand, not copy.

**Story states shown to the candidate** (`storyState` in `story-view.ts`), most specific first:

| State | Shown when | Badge | The one action offered |
|---|---|---|---|
| Improvement suggested | an open Review suggestion exists | "Improvement suggested" | Improve story |
| Add detail | completeness is not READY | "Add detail" | Continue story |
| Ready to practise | READY, never practised | "Ready to practise" | Practise this story |
| Practised | READY, practised, nothing open | "Practised" | Practise again |

Each state carries exactly one action — never several equally-weighted buttons — because a
suggestion is the most specific, most actionable thing to do; otherwise whether the Story reads
as finished, and whether it has been said out loud yet, decide what's next. This is a pure
function, not a UI convention repeated per component, so My Stories and the story page cannot
disagree about what a story needs.

**Information hierarchy on a story's page**, most important first:

1. The story itself — the form, grouped as Context / What you did / What changed / Reflection
   instead of nine flat fields, still every field, still all visible.
2. Suggested improvements, if any — the most actionable thing here.
3. Useful for (roles) — compact, only shown when a role has actually been added.
4. Practice history, with "Practise this story" as its one action.
5. Version history — behind a closed disclosure ("See earlier versions"); still one click away,
   never in front of the story on an ordinary visit.
6. Archive — a single quiet control at the very bottom, never beside Save or Practise.

**My Stories list.** Each row is title, one line of context (themes or what's missing next),
role names only when the story has any, a state badge, a date, and the one action above — down
from up to four separate lines of always-visible metadata per story. Archived stories keep
their own compact section with Open/Restore; nothing about archive or restore semantics changed.

**Deliberately unchanged:** Dig Deeper already asks one focused question at a time, explains why
before each question, and offers presence-only notes rather than a score — it did not need this
pass. Home, Interview Map, Practice orchestration, Review, and every Story data/versioning
invariant in sections 12–15 are untouched.
