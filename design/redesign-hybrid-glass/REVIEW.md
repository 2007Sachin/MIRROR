# Reading Room redesign — critique, decisions, route plan, risks

Branch `redesign/hybrid-glass-prototypes` (from `main` @ 592aff6). Prototypes only; no file under `apps/`, `packages/`, `supabase/` or `tests/` was changed.

## 1. Review panel and verdicts

| Reviewer (role source) | Verdict |
|---|---|
| Visual design lead (`.agents/skills/mirror-visual-design`) | Consistent and distinctive, not template-like. Two High items fixed (plum used as a status colour; content legibility under the mobile tab bar). |
| UX lead + journey critic (`docs/mirror-company/agents/ux-lead.md`, `journey-critic.md`) | Journeys clear. No hidden evaluation leaks into the live room. Vocabulary drift and results length were the top issues; both fixed. |
| Frontend engineer (`docs/mirror-company/agents/frontend-engineer.md`) | Feasible. All `ReportResponse` fields used already exist in `lib/api.ts`, so **no backend change is needed**. Missing room states were found and have been added. |
| Accessibility architect (WCAG 2.2 AA) | All text pairs ≥ 4.5:1. One High (fixed chrome obscuring focus at high zoom) and nine Medium items, all fixed. |
| Ponytail over-engineering review | 4 cuts applied (about −22 lines). |

## 2. Resolved decisions and trade-offs

| # | Decision | Trade-off |
|---|---|---|
| D1 | **Glass only on nav, dock, toasts, sheet chrome.** Content is always solid. | Less "wow" than full glassmorphism, but readable, AA-safe and cheap to render. |
| D2 | **The interview room goes light** (the `--room-*` dark palette is retired). **Approved.** | Loses the "stage" feel; removes the biggest visual break and halves glass QA. |
| D3 | **Results render the readiness ranges and the "What came through" ledger** that the API already returns but the UI never showed. | A longer page, mitigated by the next action above the fold, a 5-item sticky index, jump links, and collapsed rows (only the first "clearly" and the "worth revisiting" item open). |
| D4 | The UX reviewer proposed merging single-item groups ("Refined", "Not enough to say yet") into "Other". **Rejected.** | Keeping uncertainty explicit is a product principle; "Not enough to say yet" must never be hidden. Length is handled by collapse instead. |
| D5 | The colour distribution bar was **removed** (visual: plum misuse; accessibility: colour-only, under 3:1). | Replaced by icon + count jump links: less glanceable, fully accessible. |
| D6 | Readiness bands are **graphite, not accent**. | The accent now means "you can act on this" everywhere. |
| D7 | Content passes under the mobile tab bar mid-scroll (visual reviewer asked that it never rest there). **Kept**, but the bar is now 90% opaque and the page pads 104px. | Standard floating-bar behaviour; the last item always clears the bar. |
| D8 | "Interview coming up" stays in the Home rail (UX reviewer suggested demoting it). | It links to the *real-interview* brief (`/roles/[id]/interviews/[event_id]`), not the session brief, so it is not a dead end. It is a quiet link, never a second primary. |
| D9 | "Practise" (verb) / "practice" (noun) kept. | Matches the existing en-GB/IN copy in `copy.ts`. |
| D10 | The separate `/sessions/[id]/brief` page is **folded into the room pre-join**. | One less screen before starting. Duration and parts must come from session data, and the route stays as a redirect until verified. |

### Owner decisions (approved 2026-10-11)

1. **"Review" is the canonical product term.** Prototypes now say "View review", "Your review", "Preparing your review", "End and get my review". Production already uses "review" on Home; implementation must migrate the `report.*` and `voiceRoom.*` strings in `apps/web/src/lib/copy.ts` that still say "reflection" (title, trust panel, processing and error states, step-away and end-confirm buttons). **Reflect** stays only as the history section name and `/reflect` route; renaming that section is out of scope unless asked.
2. **Light interview room: approved** (D2 settled).
3. **Recording disclosure: verified, rewritten.** Code: candidate audio is uploaded to storage and attached to the turn (`apps/api/app/voice_service.py` `store_candidate_audio`, `voice_repository.attach_candidate_audio`); turns are transcribed. `docs/privacy.md`: recordings and transcripts are private per-user records, RLS owner-only; retention/deletion controls and provider DPAs are *deployment gates*, not yet facts. Prototype copy is now limited to what is true today: "Your spoken answers are recorded and saved privately to your account, with a transcript, so Mirror can prepare your review." It makes **no** claim about retention periods, deletion, or model training.
4. **"teal" test: no change needed.** `test_onboarding_plan_frontend_contract.py:76-78` exists to keep onboarding CSS on tokens and free of blue-family hues. It matches the *word* "teal", so a token named `--teal-600` would fail it. Smallest change: **name tokens by role** (`--accent-*`, `--provenance-*`) — done in the prototypes — so the test stays untouched and its intent intact. Fallback only if a future CSS file must name the hue: narrow the regex to raw colour values, not token names. Not proposed now.

## 3. Implementation order (proposed — awaiting approval)

Re-ordered from the nine-step route plan: shared tokens and navigation first, then low-risk re-skins, then the screens with new structure, with the interview room last. Each phase is one reviewable commit on a fresh branch off `main`, ships its own contract-test updates, and must pass `python -m pytest`, `npm run lint`, `npm run test`, `npm run build` and `scripts/copy_lint.py` before the next starts. No API, schema, auth, interview-logic or assessment change in any phase.

| Phase | Was step | Scope | Main files | Contract tests touched | Risk |
|---|---|---|---|---|---|
| **P1 Tokens** | 1 | Add Reading Room tokens to `:root` additively with role names (`--accent-*`, `--provenance-*`, radii, elevation, glass + fallbacks); point existing `--ink`, `--action*`, `--pulse*`, `--brass*` aliases at the new values; theme-color to canvas. No class renames. | `app/globals.css`, `app/layout.tsx` | none expected (names kept, no hue words) | Low |
| **P2 Navigation shell** | 3 | Glass top nav + mobile tab bar replace the sidebar; profile menu, RoleSwitcher, skip link, `is-active`/`is-open` hooks unchanged. | `components/workspace/app-shell.tsx`, `styles/workspace.css` | shell/nav assertions if any; verify `test_dashboard_frontend_contract.py` | Med |
| **P3 Low-risk screens** | 6, 9 | Token + row re-skin only, no flow change: `/practice`, `/practice/start`, `/reflect`, `/progress/*`, `/plan`, `/stories/*`, `/roles`, `/settings`, `/help`, then `/`, `/login`, `/signup`, `/onboarding`. | feature CSS in `styles/*.css`, `landing.css`, `auth.css`, `onboarding*.css` | plan / stories-guided / practice-reflect / onboarding-plan contracts must stay green unchanged (var()-only, no hue words) | Low |
| **P4 Shared page chrome** | 2 | Solid surfaces, rows instead of card grids, alerts, empty/loading states for `PageHeader`, `Section`, `EmptyState`, `PageAlert`; keep `dh-*`/`hm-*` class names. | `components/workspace/page-shell.tsx`, `styles/dashboard.css` | `test_interviews_frontend_contract.py`, `test_dashboard_frontend_contract.py` (class counts) | Low–Med |
| **P5 Dashboard** | 4 | Focus slip + lifecycle track per backend `HomeState`; preparation to the rail; remove quick-action cards; "View review". | `components/dashboard/home-*.tsx` | `test_dashboard_frontend_contract.py` | Med |
| **P6 Results + Review vocabulary** | 5 | Summary + next action, readiness ranges, came-through ledger (group by `claims_audit` key; null fallbacks), growth area in "What next", attempt comparison, trust panel. Migrate `report.*` copy from "reflection" to "review". | `components/review/*`, `lib/copy.ts` | `apps/web/tests/report-scope-copy.test.mjs`, any review contract | Med–High |
| **P7 Brief → pre-join** | 7 | Render brief fields in the room pre-join from session data; keep `/sessions/[id]/brief` as a redirect. Add the verified recording disclosure. | `sessions/[id]/brief/page.tsx`, pre-join block of `voice-interview.tsx` | `test_interviews_frontend_contract.py`, `test_practice_frontend_contract.py` | Med |
| **P8 Interview room (last)** | 8 | Light room, glass dock + composer (in-flow below 560px height), solid question/caption, transcript sheet on mobile; migrate `voiceRoom.*` copy to "review". Markup only around existing state logic. | `components/voice-interview.tsx`, room block of `globals.css` | `test_voice_frontend_contract.py` | High |

Browser verification for every phase runs on the isolated CI browser job only (`scripts/qa/browser/SAFETY.md`); local product browser runs stay blocked.

## 4. Regression risks

1. **Source-reading contract tests** (`tests/unit/*_frontend_contract.py`) assert class names (`dh-primary-action` exactly once, `hm-stack`, `hm-upcoming`, `hm-text-action`, `dh-text-action`), forbid hex/rgb/"blue"/"teal" in specific CSS files, and require `min-height: 44px` and `prefers-reduced-motion`. Keep the class names; use `var()` only in feature CSS.
2. **Voice-room resilience** (`test_voice_frontend_contract.py`): typed-answer retry with a stable `clientTurnId`, pending voice-blob resend, `pagehide` pause, `offline` listener, open-elsewhere, welcome-back, server-driven timer. A markup rewrite must not move this logic.
3. **Stacking contexts:** no `transform`, `filter` or `will-change` on `.ws-content` or `.reveal` wrappers, or fixed glass children break (`globals.css:165-169`).
4. **Room layout lock:** `body:has(.interview-room){overflow:hidden}` plus the 3-row grid conflicts with a floating dock and composer; the in-flow fallback below 560px height must be kept (WCAG 2.4.11).
5. **Backdrop-filter cost:** up to 4 simultaneous blurs on the room; never place glass over an animated canvas (orb) or video; keep blur ≤ 16px.
6. **Results mapping:** group by `claims_audit` key, not the claim `status` string; handle null `low`/`high`/`quote`/`timecode_ms`; WEAKENS copy must stay non-judgemental.
7. **Copy lint and vocabulary:** every new string must pass `scripts/copy_lint.py`; moving "reflection" → "review" touches `copy.ts` and any test that asserts those strings (`test_voice_frontend_contract.py` reads `copy.ts`; `apps/web/tests/report-scope-copy.test.mjs`).
8. **Hidden-evaluation rule:** the room must never show scores, probe counts, suspicion signals or evaluative colour, and readiness stays backend-computed.
9. **Browser QA policy:** local browser execution of the product is blocked (`scripts/qa/browser/SAFETY.md`); redesign journeys must be verified on the isolated CI browser job.
10. **Focus-ring colour** changes from ink to `--accent-700`; recheck it on `--accent-50` selected states and in the room's former override (`globals.css:204-205`).

## 5. Verification done

- Copy guard (`app/copy_guard.find_banned`/`find_soft`) over every visible string, aria-label and tooltip: 0 banned, 0 soft.
- No duplicate IDs; every patch step asserted its target text existed.
- 28 screenshots (desktop 1440 and true 390px mobile via an iframe viewport) in `screenshots/`.
- Not done: a screen-reader pass, real-device Safari testing, or a performance profile. The prototypes are static, and the production app was not run.
