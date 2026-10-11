# Mirror Review page UI

Updated for the Reading Room redesign (P6, branch `redesign/p6-review`). This replaces the earlier "diagnostic report UI" note, which described components, readiness numerals and brass styling that the page does not use.

The Review lives at `/app/report/{session_id}` and is rendered by `components/review/review-page.tsx`. It reads `GET /api/v1/sessions/{id}/report` and `GET /api/v1/sessions/{id}/review` together, then the conversation (`/turns`) and earlier attempts (`/attempts`) as optional extras. The browser never computes readiness, statuses or groupings of its own.

## What the page shows (ready state, in order)

1. Header: the role as the page heading and the completion date.
2. Summary panel: the backend's `verdict.label` and `verdict.summary`, the review counts (zero counts hidden), the shorter-conversation note when the backend sets it, and the single next-practice action ("Try this next", linked through `startPracticeHref`).
3. The practice-round scope note when `assessment_scope` is present.
4. "What landed well" and "One thing to strengthen" from the review, with Try again on the matching answer.
5. "What came through": `claims_audit` groups exactly as the backend grouped them (empty groups left out; "Not enough to say yet" is never merged away). Each item says where it came from (resume or documents, job description, or the conversation). Quotes are shown as said or written, with a timecode only when the backend recorded one ("Time not recorded" otherwise), and the backend's fixed explanation is labelled "Mirror's note".
6. "What would you like to do now?", story suggestions, "Your answers" (with attempt comparison) and the trust panel.

## Deliberately not shown

Readiness ranges are not drawn. The backend's `low`/`high` are an internal 0-100 band used to choose labels ("no numeric score is shown"), and a frontend contract test forbids readiness numbers on this page. Also never shown: the confidence value, raw growth-area codes, signal-strength strings, trust flags and `skill_assessments[].readiness` (always null).

## States

Loading (loader), preparing (409 from the report/review plus assessment polling every 5 s, up to 24 times, then a "taking a little longer" message), couldn't finish (assessment `FAILED`, with Try again), unavailable or not found, and sign-in expiry (redirect to login). Practice-only rounds show the backend's "Practice only" summary and no empty "What came through" section.

## Presentation

Reading Room tokens on solid surfaces (glass is reserved for navigation); source tags use the provenance tokens and always carry text. Rows use native `<details>`; the open/close marker is visual-only. Layout stacks below 900px. Copy uses "review" as the product term and passes the copy guard.
