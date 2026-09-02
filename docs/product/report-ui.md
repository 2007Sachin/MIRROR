# Mirror diagnostic report UI

The candidate report lives at `/app/report/{session_id}` and consumes only `GET /api/v1/sessions/{session_id}/report`. The browser does not reconstruct scoring or claim state.

## Component structure

- `ReportPage` owns loading, error, session-expiry redirect, and report data loading.
- `Readiness` renders role and interview readiness independently and hides numeric bounds when signal is insufficient.
- `ClaimEvidence` renders validated, candidate-safe evidence in native disclosure rows.
- Claims are grouped with held evidence first, followed by partial, walked-back, contradicted, insufficient, and unverified records.
- Skill evidence and session moments are rendered from stored specialist/evidence records only.
- The trust section explains limitations and displays outcome validation status without implying placement prediction.

The page uses the existing Bricolage Grotesque, Public Sans, and Geist Mono fonts and Mirror design tokens. Brass is reserved for readiness numerals and verdict/band labels. The layout is responsive from 360px upward, uses semantic headings and lists, native keyboard-accessible `<details>` disclosure, visible focus styles, status text alongside color, and reduced-motion fallbacks.

Loading uses structural skeletons. Assessment-in-progress, unauthorized, missing-report, and network failures receive concise professional copy. Audio replay controls are intentionally not fabricated; a future signed private-audio URL can be attached to session moments without changing this report contract.

