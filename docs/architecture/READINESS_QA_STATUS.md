# Readiness system — verification status

Last updated 2026-09-24, after the multi-agent hardening round (role-explicit practice,
follow-up policy confirmation, UX audit, Home spec). Phases 4–6 (practice modes, Try again,
review integration) were completed in the prior round.

## Automated verification

| Check | Result |
|---|---|
| `npm run lint:copy` | 0 banned-word hits (3 pre-existing soft warnings in prompts) |
| `npm run lint` / `typecheck` | clean |
| `python -m pytest` (from repo root) | 455 passed, 1 skipped, 0 failed |
| `npm run build` | passes |
| Runtime smoke | API and web boot; new endpoints return 401 when signed out; new pages redirect to sign-in |

Run `python -m pytest` from the **repository root**, not from `apps/api/`: the root run also
collects `tests/unit/*_frontend_contract.py`. Scoping to `apps/api/tests/` alone undercounts by
about 90 tests and was the source of two false "regression" scares during this round's review —
both resolved by re-running from root; there was never an actual regression.

The web app has no JavaScript unit-test runner, so frontend logic is covered by source
contract tests (`tests/unit/*_frontend_contract.py`) and by moving decisions to the backend
where they can be tested directly (practice recommendation, review → practice focus).

## Supabase migrations — NOT YET APPLIED

None of the readiness migrations has been applied to a real database from this workspace.
Apply them in order, **before** deploying the API that uses them:

1. `202609220001_candidate_stories.sql`
2. `202609220002_pressure_test_responses.sql`
3. `202609230001_practice_modes.sql` — required before deploy: every session read selects
   the new `practice_mode`, `practice_focus` and `practice_theme` columns
4. `202609230002_answer_attempts.sql`
5. `202609240001_session_role_profile.sql` — required before deploy: every session read now
   selects `role_profile_id` too. Adds a nullable `sessions.role_profile_id` column, an index,
   and an ownership-verification trigger (`sessions_verify_role_profile_ownership`) that rejects
   a `role_profile_id` not owned by the session's own `user_id`. Existing sessions get
   `role_profile_id = null` and keep resolving their role via the legacy
   `profiles.current_role_profile_id` lookup, unchanged.

These five have no foreign-key dependency on each other and can be applied in one batch, but
filename order should still be respected for consistency. None of the five contains a
destructive statement (drop/truncate/unscoped delete) — verified by direct grep across the
migration set, not just by reading each file's stated intent.

After applying, verify: RLS select-own policies on `stories`, `pressure_test_responses`,
`answer_attempts`; the ownership triggers reject cross-user references (including the new
`sessions_verify_role_profile_ownership` trigger — try inserting a session with another user's
`role_profile_id` directly and confirm it's rejected); the `answer_attempts_keep_history`
trigger rejects edits to an attempt's text; existing sessions read back as `FULL_INTERVIEW`
with `role_profile_id = null`.

**Still not independently confirmed against a live database.** The Supabase MCP connector was
not authorized in this workspace for either verification round; all migration safety checks
above are from static file review (schema, RLS, triggers, FK dependency ordering), not a live
apply-and-query. Before deploying, someone with connector or `supabase db` CLI access should
independently confirm actual applied state against the target project — do not assume "not
applied" from this doc alone; it reflects what this workspace could observe, not the live
database's actual state.

**No safe development QA-user mechanism exists.** `supabase/seed/` contains only synthetic
role-name and assessment-calibration fixtures, no `auth.users`/`profiles` rows, no credentials.
`.env.example` has infra config only. A recommended (not implemented) next step: a
`scripts/seed_dev_user.py` gated behind `ENVIRONMENT=development` that creates one clearly
synthetic `auth.users` + `profiles` row via the service-role key, documented in a new
`docs/DEV_LOGIN.md`. This was deliberately not built in this round since it touches
auth/credential handling.

## Signed-in flows still needing manual QA

No safe test account exists in this repository (the seed has synthetic assessment fixtures
only), so none of these has been clicked through while signed in:

- **Practice page:** recommendation card appears for a user with a role and preparation areas;
  "Choose something you'd like to practise." appears for a user without one; Start on the
  recommendation creates a quick drill and opens the brief.
- **Start flow:** role → how (three ways) → what (areas); a short practice cannot start without
  an area; a role other than the current one goes through setup and keeps the choice.
- **Quick drill end to end:** the brief shows "Quick drill · area · 3 questions · about 5 minutes";
  the interview asks three questions, allows at most one follow-up each, then closes; a review
  is generated; the drill appears in Previous practice labelled "Quick drill · area".
- **Focused practice end to end:** four questions, up to two follow-ups each.
- **Full interview regression:** unchanged length and flow, including the probe cap.
- **Review:** "What needs more work" shows at most three items; items tied to a marked answer
  offer Try again, others offer Practice this; every answer offers Try again; Practice next
  shows one quick drill (or "Choose a practice" when the review names no area).
- **Try again:** the first answer stays visible and unchanged; the comparison shows What changed,
  Still worth adding, the before/after columns and a suggestion; Try once more and Continue work;
  reopening the review shows "You've tried this N more times" with the comparison.
- **Try again with the model unavailable:** the attempt still saves and shows the presence-check
  comparison with its "not a grade" note.
- **Dig Deeper** wording on the role workspace tab, map CTA and story origin.
- Mobile (390px) for the practice page, start flow, review and Try again.
- **Role-explicit practice (new this round):** starting a quick drill or focused practice
  against a role other than the account's current one, and confirming the resulting session,
  review and any retry stay bound to that specific role through the whole flow.

## Known UX friction (documented this round, not yet fixed)

A full code-path UX audit (no live account available) found no P0s. Ranked findings:

- **P1** — `/sessions/new` always requires a fresh resume file upload, even when a resume
  already exists via My Experience. This creates two parallel resume records that can drift
  apart. Needs a product decision (default to the newest My Experience resume, with an explicit
  "replace" option) — not a mechanical fix, deliberately left undone.
- **P2** — the same Interview Map theme data is shown three times with different framing and no
  cross-reference: once as "you already have useful experience for" and again in the full theme
  list on the Interview Map page itself, and a third time in Home's `RolePreparation` snapshot.
  Review's "What needs more work" and "Your answers" similarly both surface the same growth
  items with duplicate Try-again entry points.
- **P3** — competing "what's next" CTAs across Home, Practice, and the Interview Map, with no
  cross-referencing between them; tracked as Phase 10 ("Home / role workspace refinement") in
  READINESS_SYSTEM_PLAN.md.
- **My Stories** manual creation shows 11 undifferentiated fields with no visual distinction
  between the 3 that determine completeness and the 6 that don't — reads as a form, not a
  guided flow. The guided "Help me find a story" flow is better (one question at a time) but
  never asks about 4 of 9 story parts, and never prompts for themes unless one was passed in via
  a link — a guided story with no theme can never count toward Interview Map coverage.
- **Dig Deeper** questions are fully deterministic and, except for one substitution (the exact
  ownership word quoted back to the candidate), identical fixed text regardless of the resume
  statement's actual content — two very different claims that both trigger the same question
  kind get word-for-word the same question. Credibility currently comes from the resume
  statement shown alongside the question, not the question's own wording.
- **Confirmed defect, not fixed:** no Dig Deeper question kind ever fills a story's `situation`
  part, so every story created via the "save as story" handoff is permanently missing one of the
  three parts required for `DEVELOPING`/`READY` completeness. A fix (add a `SITUATION` question
  kind) collides with two existing test invariants in `test_pressure_test.py` (`OWNERSHIP` must
  be `questions[0]`; `ALTERNATIVE` must always be present under the 5-question cap) and needs a
  product decision — raise the cap, or reorder priority — rather than a blind patch.

See the Home specification (`docs/architecture/HOME_SPEC.md`) for how several of these
repetition issues are meant to be resolved by the next Home implementation.
