# Mirror design system — "Reading Room" (hybrid glass)

Status: **proposal, prototype-only.** Nothing here is wired into `apps/web`. Source of truth for values: [`tokens.css`](tokens.css).

**Rule: content is opaque, controls float.** Glass is allowed on exactly four things: top navigation (and the mobile tab bar), the interview control dock, toasts, and sheet/dialog chrome. Questions, answers, reviews, readiness and every list of results sit on solid surfaces.

## 1. Tokens

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--bg-canvas` | `#F4F1EA` | page background | — |
| `--bg-sunken` | `#EAE6DC` | rails, wells, placeholders | — |
| `--surface` | `#FFFDF8` | solid content panels | primary 15.9:1 |
| `--surface-fallback` | `#F7F4EE` | glass when blur is unavailable or transparency is reduced | primary 14.7:1 |
| `--text-primary` | `#1E2124` | graphite body and headings | 14.3 on canvas |
| `--text-secondary` | `#474C52` | supporting text; allowed on glass | 7.7 on canvas, 5.7 on glass worst case |
| `--text-muted` | `#62676D` | chevrons, metadata on solid only; **never on glass** | 5.1 on canvas |
| `--line` / `--line-strong` | graphite 12% / 24% | hairlines / dividers | decorative |
| `--border-control` | `#7E8387` | input and secondary-button borders | 3.4:1 (non-text ≥ 3:1) |
| `--accent-600` | `#25685F` | primary button fill | white 6.5:1 |
| `--accent-700` | `#1D5650` | links, selected nav, focus ring | 7.5 on canvas |
| `--accent-50` / `--accent-100` | `#E3EFEC` / `#CFE3DE` | selected backgrounds, status tag | accent-700 text 7.1 |
| `--accent-500` | `#3A8578` | progress fill, live audio meter (non-text only) | 3.9 |
| `--provenance-600` / `--provenance-50` | `#6E4462` / `#F2E9EF` | **provenance only** ("From your resume", "From your conversation") | 6.6 |
| `--success` `--warning` `--danger` `--info` (+ `-soft`) | muted, see tokens.css | alerts; always icon + text | ≥ 5.5 on soft |

Token names describe roles, never hues (`--accent-*`, `--provenance-*`): `test_onboarding_plan_frontend_contract.py` forbids hue words such as "teal" in feature CSS, and role names keep that guard intact without changing the test.

Colour roles: **accent (muted sea-green) = interaction** (and live audio state), **graphite = status/magnitude** (readiness ranges), **provenance (restrained plum) = where something came from**. No colour ever implies how well someone is doing during the interview.

## 2. Type, space, shape, elevation

- Families (already installed): Bricolage Grotesque (display), Public Sans (body), Geist Mono (labels, timer, timecodes).
- Scale: H1 `clamp(2rem,3.4vw,2.75rem)/1.05` · Interview question `clamp(1.5rem,2.4vw,2.5rem)/1.15`, max 34ch · H2 `1.75rem` (1.375rem inside a focus panel) · H3 `1.0625rem/600` · Body `.9375rem/1.6`, max 68ch · Small `.8125rem` · Label mono `.75rem` uppercase `+.1em`. Minimum 12px.
- Spacing: existing 4px scale; section rhythm 64px desktop / 48px mobile.
- Radii: controls 8 · panels 12 · glass 20 · pills 999. Content panels never exceed 12.
- Elevation: `e1` raised solid · `e2` glass · `e3` modal sheet.
- Glass recipe: `rgba(255,253,248,.80)` + `blur(16px) saturate(140%)` + inner highlight + 1px outer hairline. Tab bar uses `.90`. Toasts blur 12px. Modal scrim graphite 32% + 4px blur. Never blur above 20px; never glass on glass.
- Fallbacks (required, shipped in tokens.css): `@supports not (backdrop-filter)` → solid; `prefers-reduced-transparency` → solid, no filter; `forced-colors` → Canvas/CanvasText borders and status marks keep author colours.

## 3. Motion

Fast 140ms, base 220ms, sheet 320ms, ease `cubic-bezier(.16,.8,.24,1)`. Animate only: button colour/press (1px), sheets (24px slide), toasts (8px rise), new question (6px rise + fade), row expand chevron, route fade (200ms), audio meter (driven by the real audio level). No hover-lift, no looping decorative motion, no shimmer. `prefers-reduced-motion`: everything clamps to 1ms; the audio meter shows a static level and the state is always also written in text.

## 4. Components

| Component | Spec | Notes for porting |
|---|---|---|
| **Top nav** (glass, sticky, 56px) | brand · 5 primary links (Home, My plan, My stories, Practice, Reflect) · role pill · avatar | Replaces the `ws-sidebar`. `aria-current="page"` on the active link. |
| **Mobile tab bar** (glass, fixed) | same 5 destinations, 48px targets, safe-area aware | Page gets `padding-bottom: 104px` and `scroll-padding-bottom`. |
| **Focus slip** (solid panel) | eyebrow · status tag · H2 · meta · exactly one `.btn-primary` · optional quiet action · lifecycle track | One per Home state; maps 1:1 to backend `HomeState`. |
| **Lifecycle track** | Practise → Review → Next practice; `aria-current="step"`; sr-only "(done)/(current)" | Vertical on desktop, horizontal on mobile. |
| **Rows** (`.rows`, `.row-link`) | hairline-separated rows with title, meta, chevron | Replace card grids for preparation, insights, activity, next steps. |
| **Buttons** | primary (accent fill, max one per view) · secondary (outlined) · quiet (text) · all ≥ 44px | `aria-busy` never dims text; the busy label is announced via a live region. |
| **Tags** | status (accent-50), source (provenance-50), neutral (sunken), warning | Always text, optionally an icon. |
| **Alerts** | info / warning / danger: icon + title + body + optional action | `role="status"` for recoverable notices; `role="alert"` only for blocking errors. |
| **Interview strip** (glass) | role · 7-segment phase bar + human phase name ("Deep dive · 5 of 7") · server timer | No scores, no probe counts, no evaluative colour. |
| **Question panel** (solid) | mono label · question as `<h2>` · source line · Replay / Retry voice | The welcome-back line renders above the question on resume. |
| **Live caption** (solid sunken) | "You · Live" + caption + "guide only" note | Never the interview record. |
| **Control dock** (glass, floating) | Mute · Type · Captions · I'm done answering (primary) · Step away; `role="group"` | Tooltips equal the accessible name and dismiss with Esc. Becomes sticky in-flow below 560px viewport height. |
| **Composer** (glass frame, solid field) | label · textarea · Send / Retry answer | `textRetryPending` → "Retry answer". |
| **Transcript rail** (solid sunken) | recent turns, mono speaker + timecode; focusable scroller | Becomes a side sheet below 1024px. |
| **Sheet / dialog** | native `<dialog>` + `showModal()`; glass frame, solid body | Step away is two steps: menu → end confirm; "Save and continue later" has a saving state. |
| **Readiness range** | 5-step band (Not yet → Strong), `low..high` filled in graphite; signal-strength tag; null → "Not enough to say yet" | Renders `role_readiness` / `interview_readiness` from `ReportResponse`. Mobile shows "X to Y" as text. |
| **Came-through ledger** | jump-link counts → group heading (icon + label) → `<details>` rows: what was shared · source tag → quotes with timecode and direction · short note | Groups = `claims_audit` keys (map by key, not status string). Direction: SUPPORTS "Backs this up", WEAKENS "Raises a question", CONTEXT_ONLY "Adds context". Null timecode → "Time not recorded". |
| **Section index** (glass, sticky) | 5 anchors, scroll-spy `aria-current="location"` | Horizontal scroller with edge fade below 1080px; static below 560px height. |

## 5. Copy rules carried over

All candidate-facing strings come from `apps/web/src/lib/copy*.ts` or must pass `scripts/copy_lint.py` (`app/copy_guard.py`). The prototypes pass it with zero banned and zero soft-avoid hits. Canonical vocabulary (approved): **Review** is the product term for the post-interview result ("View review", "Your review"); **Reflect** remains only the name of the history section and its `/reflect` route; **practice** (noun) / **practise** (verb).
