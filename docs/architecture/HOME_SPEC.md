# Home — state-aware specification (not yet implemented)

Produced 2026-09-24 against the actual capabilities that exist after Phases 0–6: Interview Map,
Dig Deeper, My Stories, practice modes, Review, Try again. This is a specification only — no
Home code has been changed to match it. It replaces the older "generic dashboard" framing with
one dominant action per visit, chosen by a state machine over real data.

Implementation note: the Home state machine now lives in `apps/web/src/lib/home-view.ts`.
The answer-level retry opportunity remains on the Review page until Home has a cheap
answer-level report/attempt contract.

## 0. Data sources this spec relies on

- `Onboarding.onboarding_resume_document_id`, `.onboarding_role_profile_id`, `.target_role`
- `InterviewMap` (`interview_map.py`): `state` (READY / ROLE_PREPARING / ROLE_UNREADABLE),
  `experience_state` (READY / MISSING / READING / UNREADABLE), `themes[].coverage` (PREPARED /
  EXPERIENCE / MENTIONED / MISSING), `preparation_areas[]` (max 3, each with an `action`)
- `PressureTest` (`pressure_test.py`): `state`, `items[].readiness` (null / CAN_EXPLAIN /
  NEEDS_PREPARATION — null means never marked)
- `StoryView.completeness` (`story_models.py`): READY / DEVELOPING / STARTED
- `PracticeRecommendation` (`practice_recommendation.py`) — one recommended quick drill, or null
- `DashboardSummaryResponse.latest_review` (`dashboard_summary.py`): `counts`, `root_cause`,
  `practice_focus`, `improvements[]`, `next_step`
- A **retry opportunity**: an answer block where `answerBlocks()` found `ReportEvidence` with
  `direction === "WEAKENS"` attached to that answer's turn (a "could be clearer" answer), and no
  `answer_attempts` row yet exists for that `original_turn_id`
- Session lifecycle: `sessionKind()` (review_ready / review_processing / review_failed /
  in_progress / ready / setup / failed)

## 1. Information architecture (priority order)

1. **Header** — greeting + first name, plus a persistent "Preparing for: {target_role}" line
   once a role exists. Always visible, answers "what role" in under a second.
2. **Primary panel** — exactly one dominant state block (§2–3). The only thing that answers
   "what should I do right now."
3. **What you're ready to discuss** — themes with `coverage ∈ {PREPARED, EXPERIENCE}`. Hidden
   until a map is READY.
4. **What still needs work** — merges `preparation_areas` and `latest_review.improvements` into
   one list, max 3 items, one action link each. Never duplicate a theme between sections 3 and 4.
5. **Recent activity** — one line (last completed review + role), collapsed. The full list moves
   to Progress / the role workspace, not Home.

No footer tiles repeating global nav (Practice, My Stories, My Experience, Roles) — they already
have a permanent home in the sidebar.

## 2. State-detection decision table (priority order, first match wins)

| # | State | Condition | Wins over |
|---|---|---|---|
| 1 | New user / no experience | `onboarding_resume_document_id is null` | everything |
| 2 | Experience, no role | resume present, `onboarding_role_profile_id is null` | 3–8 |
| 7 | Retry opportunity | role + review exist, and a retry-eligible answer has zero `answer_attempts` rows | 3, 4, 5, 6, 8 |
| 6 | Practice completed / review ready | `latest_review` exists, state 7 false | 3, 4, 5, 8 |
| 4 | Dig Deeper incomplete | `PressureTest.state == READY`, ≥1 item `readiness is null`, no review yet | 3, 5, 8 |
| 5 | Stories missing | map READY, ≥1 theme `MISSING`/`MENTIONED`, state 4 false, no review yet | 3, 8 |
| 3 | Role exists / map ready (fresh) | map READY, none of 4/5/6/7 apply | 8 |
| 8 | Well-prepared returning user | map READY, review exists, no pending retry, most themes PREPARED/EXPERIENCE | fallback |

Notes:
- State 7 outranks 6 deliberately: a named, specific, low-effort fix ("redo this one answer")
  beats a generic "here's your whole review" prompt.
- States 4 and 5 can both be true before any review exists; 4 wins because it's cheaper (one tap
  per item) and something Mirror already asked the candidate to do.
- If `InterviewMap.state != READY` while a role exists, show a lightweight "preparing your role"
  / "couldn't read this role" notice instead of any of states 3–8 — a transient sub-state, not
  one of the eight, and it must not block the header.
- State 8 is what state 6 decays into once the candidate has acted on the review and map
  coverage is broadly strong — it never resurfaces an `improvements` item from a review that is
  no longer the current one.

## 3. Per-state copy and CTA (following `copy.ts` tone; no banned words from `copy_guard.py`)

| State | Headline | Primary CTA | Must NOT show |
|---|---|---|---|
| 1 | "Let's start with what you've actually done." | "Add your experience" → `/experience` | theme lists, role picker, review, map, Dig Deeper, Stories |
| 2 | "You've told Mirror about your experience. Now pick a role to prepare for." | "Choose a role" → role setup | map, coverage, Dig Deeper, Stories, review |
| 3 | "Here's what {role} is likely to explore, and how you already measure up." | "See your Interview Map" → `/roles/{id}` | retry items, review counts, "well-prepared" framing |
| 4 | "A few resume statements are still open. Take a minute to mark whether you can explain them." | "Continue Dig Deeper" → `/roles/{id}/pressure-test` | story-missing framing for the same themes yet; review data |
| 5 | "A couple of things this role cares about don't have a story yet." | "Find a story for {theme}" → `/stories/new?theme={key}` (top-ranked area only) | review/retry content; MISSING/MENTIONED shown as jargon labels |
| 6 | reuse `latest_review.next_step.title`/`.body` verbatim | "Open your review" → `/app/report/{session_id}` | Dig Deeper/story nudges; stale map-only "ready to discuss" without review context |
| 7 | "One of your answers could be clearer. Want to try it again?" | "Try this answer again" → opens Try again inline on that answer | the full review as competing primary content; more than one retry CTA even if several exist |
| 8 | "You're in good shape for {role}." | "Do another practice" → recommended quick drill, else `/practice` | alarming language; resurfaced "needs work" framing when nothing meaningfully does |

Secondary actions appear only when genuinely different from the primary (e.g. state 6: "Practice
{focus}" alongside "Open review"; state 5: "See full map" alongside "Find a story"). States 1
and 2 get no secondary action — a second CTA would fragment onboarding.

## 4. CTA priority rules

- Exactly one visually dominant action per load, chosen by §2.
- A secondary action is a text link or ghost button, never a second filled button.
- The header's role-switch/"Start practice" control stays as global chrome — it must never
  visually compete with the state panel's own CTA.

## 5. Mobile behaviour

- Header collapses to greeting + role name; no icon-row stepper — a compact "2 of 3" text
  instead.
- Primary panel: one full-width CTA, stacked above supporting text.
- "Ready to discuss" / "needs work" stack vertically (never a side-by-side grid) below ~600px,
  collapsed to 2 items with "show more."
- Recent activity becomes one tappable row, not a table.
- Secondary CTAs move below the fold as text links, keeping one thumb-reachable primary action.

## 6. Empty / error states

- **Network failure on initial load**: one alert row + reload button, matching the existing
  pattern; no state-panel skeleton underneath implying stale data.
- **Partial load** (workspace loads, review summary fails): fall back one state tier — e.g. if
  `latest_review` fails to load, treat states 6/7/8 as unknown and show state 3, never a state 7
  CTA pointing at data that didn't load.
- **Interview Map fetch fails**: degrade to the previous known-good state derived from
  onboarding fields alone (state 2, or a generic "checking your prep" placeholder) — never a
  blank panel.
- **Dig Deeper / Stories fetch fails**: treat states 4/5 as false (skip to the next evaluable
  state), never assert them without data.

## 7. What to remove from the current Home

Current implementation: `evidence-dashboard.tsx`, `dashboard/sections.tsx`,
`dashboard/role-preparation.tsx`.

1. **`ContinuePreparing`** — near-duplicate of the primary `NextAction` panel; repeats the same
   role and a "Practice {role}" CTA a second time on the page. Remove; fold "Prepare for another
   role" into the header/global nav.
2. **`DevelopmentAreas`** ("Four parts of a clear interview answer") — a generic 4-dimension
   scorecard shown unconditionally whenever a review exists, duplicating `ReviewSummary`'s own
   columns on the same page. This is exactly the score-shaped UI the readiness plan moved away
   from ("no new scores… named states, each backed by an inspectable reason"). Fold into the
   single "what still needs work" list (§1.4).
3. **`ReviewSummary`'s two-column breakdown** shown as a separate section from
   `RolePreparation`'s columns — currently two different ready/not-ready breakdowns (one from
   review dimensions, one from map themes) stack on the same page with no indication which is
   authoritative. Merge into the single §1.3/§1.4 sections, reading from whichever is current
   (map pre-review, review post-review).
4. **`SetupProgress`** currently only renders inside the empty state's `NextAction.supporting`
   prop — move it to the header as a compact indicator across states 1–2 only, not tucked inside
   one state's card.
5. **Duplicate `PracticeLauncher` instances** — the header and `ContinuePreparing` each render
   their own; once `ContinuePreparing` is removed, one instance in the header is sufficient.
6. Do **not** remove the Interview Map fetch itself — keep the data source, but fold its
   rendering into the unified §1.3/§1.4 sections rather than a separate card with its own heading
   and CTA competing with the primary action.

## 8. Relationship to this round's UX audit

This spec's §1.3/§1.4 merge and its removal of `RolePreparation`'s independent card (§7.6)
directly address the P2 repetition findings from this round's UX audit
(`docs/architecture/READINESS_QA_STATUS.md`): the same Interview Map theme data currently
appears on Home, then twice more on the Interview Map page itself. Implementing this spec is the
intended fix — it is not implemented yet.
