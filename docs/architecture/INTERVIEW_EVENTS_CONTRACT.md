# Interview tomorrow + Debrief — contract (Phases 8–9)

Status: contract for implementation. Extends `READINESS_SYSTEM_PLAN.md` §3 phases 8–9.

Purpose: close the loop *after* practice. A candidate records a real interview for a role, gets a
one-page "night before" brief built only from their own material and the role brief, then reports
what actually happened. Debriefs are candidate-reported: Mirror never claims to know why an outcome
happened, and never researches the company.

## Principles

- Deterministic. No LLM, no retrieval, no company research. Every brief line says where it came from.
- Reuses what exists: Interview Map (`interview_map.py`), Dig Deeper / pressure test
  (`pressure_test.py`), stories, the latest review (`dashboard_summary.build_latest_review`) — via
  `ReadinessService`. The brief only selects and orders; it recomputes nothing.
- No scores, no percentages, no predictions ("you will pass"). Copy goes through `copy.ts` and must
  pass `copy_guard.py` / `scripts/copy_lint.py`.
- Owner-scoped everywhere: another user's role/event → 404. Writes only through backend
  `service_role`; RLS `select_own` for `authenticated`.
- Company name is optional free text the candidate typed; it is a label only, never looked up.

## Data model (migration `202609300001_interview_events.sql`, additive)

```
enum interview_round_kind: SCREENING | TECHNICAL | BEHAVIOURAL | HR | OTHER
enum interview_feeling:    WENT_WELL | MIXED | WENT_BADLY
enum interview_outcome:    WAITING | NEXT_ROUND | OFFER | NOT_SELECTED | WITHDREW

interview_events
  id uuid pk, user_id -> profiles(id) cascade, role_profile_id -> role_profiles(id) cascade,
  scheduled_for timestamptz not null, round_kind interview_round_kind not null default 'OTHER',
  company_label text null check (char_length <= 120),
  created_at, updated_at
  trigger: role_profile must belong to user_id; bumps updated_at

interview_debriefs
  id uuid pk, user_id -> profiles(id) cascade,
  interview_event_id -> interview_events(id) cascade, unique(interview_event_id),
  questions_asked text[] not null default '{}'  (each 1..500 chars, max 15 items; enforced in API + check)
  feeling interview_feeling null, outcome interview_outcome not null default 'WAITING',
  notes text null check (char_length <= 2000),
  created_at, updated_at
  trigger: event must belong to user_id; bumps updated_at
```

RLS enabled, `select_own` policies, revoke insert/update/delete from `authenticated`, revoke all from
`anon`, grant all to `service_role` (match `202609220002_pressure_test_responses.sql` and
`202609250001_revoke_anon_new_tables.sql`).

## API (all under `get_current_user`)

```
GET    /api/v1/roles/{role_profile_id}/interviews          -> InterviewEvent[] (scheduled_for asc)
POST   /api/v1/roles/{role_profile_id}/interviews          body InterviewEventCreate -> 201 InterviewEvent
PATCH  /api/v1/interviews/{event_id}                       body InterviewEventUpdate -> InterviewEvent
DELETE /api/v1/interviews/{event_id}                       -> 204 (cascades debrief)
GET    /api/v1/interviews/{event_id}/brief                 -> InterviewBrief
GET    /api/v1/interviews/{event_id}/debrief               -> InterviewDebriefView | 404 when none yet
PUT    /api/v1/interviews/{event_id}/debrief               body InterviewDebriefWrite -> InterviewDebriefView
```

### Shapes (JSON, snake_case, Pydantic models in `apps/api/app/interview_event_models.py`)

```
InterviewEventCreate  { scheduled_for: datetime (tz-aware, naive rejected), round_kind?: RoundKind="OTHER",
                        company_label?: str|null (<=120, stripped, "" -> null) }
InterviewEventUpdate  { all three optional }
InterviewEvent        { id, role_profile_id, scheduled_for, round_kind, company_label, has_debrief: bool,
                        timing: "UPCOMING" | "SOON" | "PAST",  # SOON = now <= scheduled_for <= now+48h; PAST = scheduled_for < now
                        created_at, updated_at }

InterviewBrief {
  event: InterviewEvent,
  role_title: str,
  state: "READY" | "ROLE_PREPARING" | "ROLE_UNREADABLE",   # mirrors InterviewMap.state; lists empty unless READY
  themes: BriefTheme[]          # max 3: highest-importance map themes
  recheck: BriefClaim[]         # max 3: NEEDS_PREPARATION first, then never-marked, in pressure-test order
  focus: BriefFocus | null      # latest review's practice focus / next step for this role; null when no review
  questions_to_ask: str[]       # 3–5, fixed templates keyed off role themes; never company facts
  limitations: str[]            # always includes: built only from the role brief and your own material; no company research
}
BriefTheme { key, label, coverage: "PREPARED"|"EXPERIENCE"|"MENTIONED"|"MISSING",
             support: str|null,   # story title or matched resume text; null when MISSING/MENTIONED
             story_id: uuid|null,
             prompt: str }        # one "worth preparing for" question from the map for that theme
BriefClaim { claim_id, statement: str, readiness: "CAN_EXPLAIN"|"NEEDS_PREPARATION"|null, question: str }
BriefFocus { title: str, body: str, session_id: uuid|null }

InterviewDebriefWrite { questions_asked: str[] (0..15; each stripped, blanks dropped, 1..500 chars,
                                                duplicates removed case-insensitively keeping first),
                        feeling?: Feeling|null, outcome?: Outcome="WAITING", notes?: str|null (<=2000) }
InterviewDebrief      { id, interview_event_id, questions_asked, feeling, outcome, notes, created_at, updated_at }
InterviewDebriefView  { debrief: InterviewDebrief, follow_ups: DebriefFollowUp[] }
DebriefFollowUp { question: str,                             # the reported question, verbatim
                  theme_key: str|null, theme_label: str|null, # best map theme by the same word overlap interview_map uses; null when none
                  coverage: Coverage|null,
                  action: "ADD_STORY" | "STRENGTHEN_STORY" | "NONE",
                  action_href: str|null }                    # ADD_STORY -> /stories/new?guided=1&role={role_id}&theme={theme name}, matching map-view findStoryHref; STRENGTHEN_STORY -> /stories/{id}
```

Follow-up rule (deterministic): MISSING/MENTIONED theme → ADD_STORY; PREPARED with a story whose
completeness is not READY → STRENGTHEN_STORY; otherwise NONE. Follow-ups describe what to prepare
next; they never state or imply why the outcome happened.

A debrief may be written before the event is PAST (people debrief early); the UI only *prompts* for
it once PAST.

Errors: 404 unknown/foreign role or event; 422 validation; 503 storage not configured (match the
existing `*Unavailable` pattern).

## UI

- Role workspace gains an "Interviews" tab (`role-tabs.tsx`): `/roles/[role_profile_id]/interviews`
  — list (upcoming first, then past) + "Add an interview" form (date/time, round, optional company label).
- `/roles/[role_profile_id]/interviews/[event_id]` — the brief; once PAST (or a debrief exists), the
  debrief form and follow-ups. The brief stays viewable afterwards.
- Copy: "Questions worth preparing for", "Questions you could ask them", "How it went". Never
  "you will be asked", never outcome causality, no scores.
- Mobile-first: single column, one primary button per screen, loading / error / empty states.
