# Current MIRROR product state

## Current status — 2026-10-08

Loop 1–3 remain accepted only within their recorded bounded scopes. Loop 4 was separately authorized and is now **BLOCKED**: no candidate-facing India-scoped research claim passed the publication gate. Amazon SDE I/II, Deloitte BA/Consultant, Microsoft SWE, Google SWE, and Accenture BA/Technology Consulting remain HELD. The Accenture careers page supports general role-dependent guidance, but India applicability was not established, so it is not used for the India target. Amazon SDE II candidate sources are UNVERIFIED.

No product code, catalog v1, mappings, prompt/question contract, or candidate UI changed. There is no Loop 4 process version. Hosted migration/integration is NOT VERIFIED; production release/deployment is NOT APPROVED. No Loop 5 is authorized. See `RECEIPTS/LR-0004-verified-interview-intelligence-expansion.md` for evidence limits and gate dispositions.

## Historical Loop 2 bounded status — 2026-10-06

The local Loop 2 architecture/product slice was accepted at implementation HEAD `635209c43fe884c92ed62b0c03b449247354afc3`. **PROVEN locally:** optional company/role/seniority/geography target matching; scoped versioned research and round mapping; research-derived blueprint, round priority and practice basis; generated question origin remains separately `MIRROR_GENERATED`; immutable owner-scoped prompt manifest/recovery; isolated synthetic desktop/mobile journey.

**NOT PROVEN at that Loop 2 checkpoint:** Amazon India SDE I/SDE II research validity or release; hosted migration/PostgREST integration; production readiness. The browser used fictional/synthetic fixtures and fake Auth/API; local SQL used disposable PostgreSQL. Gatekeeper disposition then: A PASS, B HELD, C NOT VERIFIED. See `RECEIPTS/LR-0002-amazon-swe-india-local-slice.md`.

> The detailed journey/capability inventory below is the pre-Loop2 snapshot at `8e3193f`; its absence claims are historical, not current. `docs/architecture/IMPLEMENTATION_STATUS.md` is the current feature ledger.

Method: routes, redirects, middleware, services, migrations, tests and existing docs read at head `8e3193f` (2026-10-04), then fact-checked by an independent Product Critic (Loop 1). Evidence label for everything below unless stated: **STATIC-ONLY**. The only executed evidence is the test baseline in `QUALITY_GATES.md`. No signed-in click-through or live voice check was possible; hosted-database structure was inspected read-only (`HOSTED_SUPABASE_DRIFT.md`).

The feature-by-feature ledger already exists in `docs/architecture/IMPLEMENTATION_STATUS.md` and is **not repeated**. This file adds what that ledger doesn't: the real journey, classification, and what is disconnected.

## Identity at the Loop 1 baseline (historical)

An **evidence-backed readiness diagnostic for one candidate and one role**: claims from the resume are compared with what an interview actually evidences; the candidate then practises, improves stories, and retries answers (`AGENTS.md`, `READINESS_SYSTEM_PLAN.md`). It is role-aware and candidate-aware. It is **not** company-aware and **not** multi-round.

## The actual candidate journey

```
/ (landing) → /signup | /login   (Supabase auth; proxy.ts verifies claims, refreshes tokens)
  → /onboarding   five persisted stages: role (JD or pasted) + resume → role & resume intelligence
                  → evidence-map review → inquiry depth → prepared interview thesis
  → /dashboard    "Home": one dominant CTA, setup progress, ready/work lists, recent activity,
                  banner when a real interview is within 48h
      ├─ Roles      /roles, /roles/new → /plan?role=…  (Interview Map; /roles/[id] redirects here)
      │             /roles/[id]/pressure-test   (Resume Pressure Test → can save an answer as a Story)
      │             /roles/[id]/interviews[/event]  (record a real interview → night-before brief → debrief)
      │             WARNING, reachability (Product Critic, STATIC-ONLY, needs signed-in confirmation): /roles/[id] redirects to /plan, so the
      │               component that links to Pressure Test and the interview record/brief/debrief may be unmounted; those pages exist but
      │               may have no path from the UI.
      ├─ Stories    /stories, /stories/new (guided "Help me find a story"), /stories/[id]
      │             (versions, archive/restore, per-role framing, practice usage, improvement suggestions)
      ├─ Experience /experience  (evidence library: resume / work / projects / achievements; /evidence redirects)
      ├─ Practice   /practice (one recommended drill) → /practice/start (role → how → what: mode + focus)
      │             or straight to /sessions/new (setup; defaults to a full ~20-minute interview) from Home-no-role,
      │             Reflect/Progress/Roles empty states → /sessions/[id]/brief
      │             → /app/interview/[session_id]  (VoiceInterview: voice or text; pause/resume/recovery)
      │             → /app/report/[session_id]    (review: overview, what came through, ≤3 items needing work,
      │                                           answers + Try again, one "Practice next")
      ├─ Reflect    /reflect (/progress redirects here) → /progress/[roleProfileId]/… (dimension, answers)
      └─ /settings, /help
```

Three interview modes share one engine: full interview (Planner agent, ~20 minutes), focused practice (4 questions, ~9 minutes), quick drill (3 questions + one follow-up each, ~5 minutes). Primary nav: Home, My plan, My stories, Practice, Reflect; My experience, Roles, Settings, Help sit in the profile menu. Practice can be started from Home, Practice, My plan, Roles, Stories, Review, onboarding plan-ready and the Reflect/Progress empty states.

Interview runtime: deterministic state machine (`INTRO → BACKGROUND → PROJECTS → ROLE_CORE → DEEP_DIVE → BEHAVIOURAL → CLOSING → COMPLETE`, default 20 minutes) drives turns; the Interviewer agent words them; the Skeptic flags (shadow by default, activation delayed one turn); post-session a durable job runs specialist assessors → adjudication → verdict → report.

## Capability classes

**Working (implemented + backend-tested; behaviour in live conditions unverified).** Caveats: there are *no* frontend tests of any kind (`npm test` = copy lint + pytest + typecheck; the frontend is covered only by source-text contract tests); the live voice provider test is skipped unless `RUN_VOICE_PROVIDER_SMOKE=1`; no test file was found for `document_library_service` (evidence library): auth; onboarding; resume/JD ingestion; evidence library; role intelligence (LLM Role agent + 4 synthetic canonical profiles); claims graph; Planner v3; interview engine; text + voice interviewer; Skeptic; evidence extraction; specialist assessors (TECHNICAL, BEHAVIOUR, CLAIMS); adjudication; verdict; report; Interview Map (deterministic, derived on read); Pressure Test; Stories (full lifecycle); practice modes + recommendation; Try again; review loop; role-explicit practice; Home; interview events + brief + debrief; career evidence.

**Partial:**
- *Progress* — role-level only; attempt-aware Progress is "PLANNED / paused" in the ledger. No competency/round/company/question-family levels.
- *Voice* — turn-based record→STT→engine→TTS (Deepgram nova-3 / Sarvam), with pause/resume, liveness and recovery code and tests. No realtime streaming/barge-in (by design, `voice-pipeline.md`). Live reliability not verified here.
- *Adaptivity* — probes, `ladder_up`/`ladder_down` turn types and a `difficulty_start` per objective exist; there is **no per-competency difficulty state** carried across sessions.
- *Observability* — structured agent logs, session events, voice latency metrics; no dashboards/alerts. *Analytics* — none.
- *Planner personalisation* — consumes claims, role competencies, projects, skills, documents, existing evidence; stories only for story-focused practice. Does **not** consume Interview Map coverage, previous-session performance, or any company context.
- *Repeat practice* — focused practice and quick drills use fixed question templates in order with no history (`practice_modes.py:157-171`), so repeating a drill asks verbatim-identical questions (Product Critic, STATIC-ONLY).
- *Communication assessment* — there is no separate Communication assessor; clarity/structure is only partly covered inside the BEHAVIOUR assessor prompt.

**Dormant / dead (declared in schema, never read or written by `apps/api/app` or web source):** `question_bank`, `question_reports`, `rubrics` (+ `round_type` enum `screening|technical|managerial|hr`), `outcomes`, `calibration_runs`, `golden_cases`, `colleges` (still reachable via `profiles.college_id`, `onboarding_repository.py:29`), `profiles.role='tpo'` (a check-constraint value with only a contract test), `roles` (4 synthetic names), `skills`. They are mentioned by generated TypeScript types, the initial migration, three hardening/grant/index migrations (`202609070020`-`22`), `supabase/seed/personas.sql` (`golden_cases`) and migration-contract tests; no migration drops them. **Hosted database (read-only inspection, 2026-10-04): all of these tables exist and are empty (0 rows)**; see `HOSTED_SUPABASE_DRIFT.md`.

**Duplicate / legacy:** `users` was renamed to `profiles` by `202608310002` (one table, not two; initial-schema docs/types may still say `users`); `sessions.question_plan` (initial schema; still selected at `repository.py:25` and modelled at `schemas.py:405` but no writer found) vs `interview_plans` (the live planner store; several rows per session are possible, one `PROCESSING` at a time); specialist assessor "legacy V1 retained"; two STT providers (Deepgram, Sarvam) plus a streaming Sarvam variant; `docs/architecture.md` vs `docs/architecture/MIRROR_ARCHITECTURE.md`; per-route aliases (below). `IMPLEMENTATION_STATUS.md` cites `evidence-dashboard.tsx`, which is not in the tree (Home is `components/dashboard/home-page.tsx`).

**Not present at the Loop 1 baseline (historical; superseded in part by Loop 2):** company entity; geography; multi-round interview plan; interview intelligence of any kind; deliberate reassessment scheduling; question de-duplication across sessions. **Partly present:** a round vocabulary already exists for *recorded real interviews*: `RoundKind` (SCREENING, TECHNICAL, BEHAVIOURAL, HR, OTHER) in `interview_event_models.py:25-31`, driving only the Home banner and brief title. Interview Intelligence must reuse or map to it rather than create a second round vocabulary.

## Where "company" exists today (so nothing is overstated)

`profiles.target_company` (free text, written by onboarding, selected by `onboarding_repository.py:29`): `dashboard_repository.py:94-98` only copies it onto the onboarding session; no screen found displays it and the planner never reads it, so **a company typed at onboarding currently changes nothing**; `interview_events.company_label` (free text, max 120). `question_bank.company_id` and `outcomes.company_id` are bare `uuid` columns with no FK or target table. The interview brief states plainly: "Mirror has not researched the company." `INTERVIEW_EVENTS_CONTRACT.md` lists "no company research" as a non-goal.

## UX fragmentation observed in routing

- One concept, several names/paths: Interview Map at `/plan` (while `/roles/[id]` redirects to it), Progress at `/reflect` (while `/progress` redirects to it), Practice previously `/diagnostics`, Experience previously `/evidence`.
- Interview and report live under `/app/*` while every other authenticated page is unprefixed; `/sessions/[id]/interview` redirects into `/app/interview/[id]`.
- Entry points to "start practising" exist on Home, Practice, Roles, Stories, Review, and the interview brief.
- The existing UX audit and Home spec (`HOME_SPEC.md`, commit `1a7197d`) already addressed single-CTA Home; the Journey Critic should start from those, not redo them.

QA-only routes (`/home-qa`, `/interviews-qa`, `/progress-qa`) return 404 in production and without `MIRROR_HOME_QA=1` — correctly gated.

## What is worth preserving (do not rebuild)

Deterministic-backend / bounded-agent split; claims graph + evidence-first reasoning; Skeptic delayed-flag rule; the shadow-before-active posture; candidate-safe verdict language and `copy_guard`; Interview Map as deterministic derivation; Stories as candidate-owned content ("Mirror never writes story content"); append-only story/attempt history; role-explicit sessions with DB-level ownership triggers; the migration-contract test pattern; the copy guide and lint. These are the product's differentiators and its integrity guarantees.
