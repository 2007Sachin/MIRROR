# Home runtime QA

`/home-qa` is a local-only, synthetic preview of the actual Home components. It is available only
when a non-production Next.js process is started with `MIRROR_HOME_QA=1`; it returns 404 in a
production build and when the flag is absent. It does not call the authenticated dashboard route,
Supabase, or the API, and does not change authentication, authorization, or RLS. `/progress-qa`
uses the same flag.

Run it locally with:

```powershell
$env:MIRROR_HOME_QA = "1"
npm run dev:web
```

Open `/home-qa?scenario=<id>` with one of: `active`, `review-ready`, `returning`, `new-role`,
`early`, `cross-role-active`, `upcoming-interview`. The data lives in `apps/web/src/lib/home-qa-fixtures.ts`, is
intentionally synthetic, and is drawn against a fixed clock so screenshots do not drift.

## One request, decided on the server

`GET /api/v1/home[?role_profile_id=<id>]` returns one `HomeResponse`. The page renders it and never
decides. It composes the canonical outputs that already exist and recalculates none of them:
role progress (`role_progress.summary_from`, the same analytics as the Progress pages), the practice
recommendation and interview map (`readiness.map_and_recommendation`), story readiness
(`story_completeness`), and the session lifecycle. The role is a view choice (`?role=` in the
address); an id that is not the signed-in person's is a 404. With no request, Home is about the
role of the newest practice, else the newest role.

## Dominant state precedence (selected role, first match wins)

Implemented once, in `home_service.decide()`:

1. `NO_ROLE`: no role set up. Action: add a role.
2. `ACTIVE_PRACTICE`: an unfinished practice for this role. Action: continue (or begin, if created
   but never begun and newer than any finished review). Wins over everything below.
3. `REVIEW_PROCESSING` / `REVIEW_FAILED`: the newest reviewed practice for this role is still being
   reviewed, or the review did not finish. Action: wait (Home polls) or try again.
4. `REVIEW_READY`: the newest practice's review exists and finished within 24 hours. Action: view review.
5. `FIRST_PRACTICE`: no finished practice for this role. Action: start the first practice. No trend or
   attention language is shown.
6. `EARLY_BASELINE`: exactly one. Action: practise again. Only what that practice showed is shown; no
   direction.
7. `RECOMMENDED_NEXT`: two or more, and a practice is recommended. Action: start the recommended drill;
   "see the answers behind this" deep-links into the role's Progress drill-down.
8. `RETURNING`: two or more and nothing to recommend. Action: start a practice.

An unfinished practice for **another role** is never hidden: it comes back as `other_active`, drawn
above whichever state the selected role is in, named for its own role. This is the one place two
actions from different role contexts coexist.

### Decisions worth knowing

- **Review freshness.** Mirror does not track whether a review was opened, so "review ready" is the
  headline for 24 hours after a practice finishes, then gives way to the next step.
- **Questions.** "Question 3 of 4" is shown only for a focused practice (4) and a quick drill (3),
  whose size is fixed. A full interview is time-based, so it says "N questions so far".
- **End this practice** uses the existing end endpoint after a confirmation. Ending always prepares a
  review, and the confirmation says so.
- **Recent activity** is this role's practice plus edits to stories (stories belong to the person, not
  to a role). Other roles' practice never appears there.
- **Practices from before roles were bound** can still show as unfinished, but never drive the review
  headline or the activity list, because Progress cannot count them.
- **A failed load** is an error with a retry, never an empty Home. Interview map and stories are
  summaries: if one is down it says so and the rest of Home stands.

## Review and answer retry boundary

Home orients a person and gives one next action. Review owns the full report, answer blocks and
answer-attempt history; the answer page under Progress owns "Try again". Home does not fetch per-answer
evidence.

## Interviews harness

`/interviews-qa?screen=list|brief-upcoming|brief-past|brief-past-debriefed` renders the real
`InterviewsPage` / `InterviewBriefPage` for a synthetic role, skipping only the server-side onboarding
guard. It has the same gate as `/home-qa`. The components still call `mirrorApi`; nothing in production
code is stubbed. Instead `scripts/qa/interviews_qa.mjs` intercepts the API base URL in Playwright and
answers with the fixtures served at `/interviews-qa/fixtures` (from `apps/web/src/lib/interviews-qa-fixtures.ts`,
fixed clock), including create, edit, remove and debrief writes. It checks both widths (1280 and 375),
horizontal scroll, console errors, one filled primary per screen, labels, status regions, and a keyboard
pass through adding, editing and debriefing.

```powershell
$env:MIRROR_HOME_QA = "1"; $env:PORT = "3107"; npm run dev:web   # separate terminal
$env:QA_BASE = "http://localhost:3107"; $env:PLAYWRIGHT_MODULE = "<path to an installed playwright>"
node scripts/qa/interviews_qa.mjs
```
