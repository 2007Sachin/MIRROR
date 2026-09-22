# Readiness system — verification status

Last updated 2026-09-23, after Phases 4–6 (practice modes, Try again, review integration).

## Automated verification

| Check | Result |
|---|---|
| `npm run lint:copy` | 0 banned-word hits (3 pre-existing soft warnings in prompts) |
| `npm run lint` / `typecheck` | clean |
| `python -m pytest` | 448 passed, 1 skipped, 0 failed |
| `npm run build` | passes |
| Runtime smoke | API and web boot; new endpoints return 401 when signed out; new pages redirect to sign-in |

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

After applying, verify: RLS select-own policies on `stories`, `pressure_test_responses`,
`answer_attempts`; the ownership triggers reject cross-user references; the
`answer_attempts_keep_history` trigger rejects edits to an attempt's text; existing sessions
read back as `FULL_INTERVIEW`.

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
