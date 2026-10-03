# Redesign build brief (Product Redesign Blueprint, 30 Sep 2026 audit)

The shared contract for building the blueprint. Every workstream reads this first. The blueprint itself
is summarised here because it is not in the repository.

## North star

Mirror is a calm, private coach. It always knows what the person has already shown, what needs
strengthening, and the smallest useful next step. Never a readiness percentage, a selection prediction,
or raw resume text treated as evidence without the person's review.

Principles: earn trust before coaching (show extracted experience, let the person correct it, use only
approved items) · one source of truth (Home, My plan, Stories, Practice and Reflect read the same approved
Career Evidence) · one next step per state (one primary action, one safe alternative) · preparation is not
a test · every recommendation explains the role need and the evidence behind it · safe to pause (nothing
forces a voice session; save, leave and resume without penalty) · calm under uncertainty (errors say what
happened, keep work, offer recovery).

Every screen must answer: Where am I? What is the best next action? Why? What happens if I stop now?

## Visual system: no blue anywhere

| Token | Value | Use |
| --- | --- | --- |
| `--paper` | `#F7F5EE` | page background (warm) |
| `--paper-raised` | `#FFFFFF` | cards |
| `--paper-sunken` | `#EDEAE0` | wells, progress tracks |
| `--ink` | `#17160F` | text |
| `--slate` | `#4C493C` | secondary text |
| `--silver` | `#6F6A58` | tertiary text (must pass 4.5:1 on paper) |
| `--line` | `rgba(23,22,15,.12)` | borders |
| `--action` | `#1F1E19` | the one filled primary button |
| `--action-hover` | `#3A382F` | primary hover |
| `--action-soft` | `#ECE7DA` | selected nav item, badges, chips |
| `--success` | `#166534` | always with text |
| `--caution` | `#B45309` | cautionary only, never a competing CTA |
| `--danger` | `#B91C1C` | errors, always with text |
| focus ring | `2px solid var(--ink)`, `outline-offset: 2px` | every interactive element |

No blue, cobalt, indigo or teal hex values, and no CSS variable named after a blue colour. One filled
primary action per page; secondary actions are outline or text; destructive actions are separated and
named explicitly. Touch targets at least 44px. Respect `prefers-reduced-motion`.

## Information architecture

Primary navigation (sidebar on desktop, bottom bar on mobile):

| Label | Route | Job |
| --- | --- | --- |
| Home | `/dashboard` | the one best next move |
| My plan | `/plan` | role needs against approved examples (replaces Interview Map + role view) |
| My stories | `/stories` | turn evidence into reusable stories |
| Practice | `/practice` | rehearse one chosen outcome |
| Reflect | `/reflect` | reviews, retries, practice history, how practice is developing (the Progress pages) |

Profile menu (top right): My experience `/experience`, Roles `/roles`, Preferences `/settings`, Help
`/help`, Sign out (a labelled text item, never icon-only). Old routes keep working (redirect or alias).

**Active role.** One role is active at a time, persisted in `profiles.current_role_profile_id`.
`GET /api/v1/active-role` → `{ "role": {role_profile_id, target_role} | null, "roles": [...] }` (one entry
per role name, newest profile). `PUT /api/v1/active-role` body `{ "role_profile_id": uuid }`, owner-verified,
404 for a role that is not the person's. Switching never creates a practice session. "Add a role" lives
inside the switcher and goes to `/roles/new` (role setup without a session).

## Career Evidence spine

`GET /api/v1/career-evidence` → `{ state: "NO_RESUME" | "READING" | "UNREADABLE" | "READY", items: EvidenceItem[] }`.
On first read for a resume analysis, pending items are created from it (idempotent per source).

`EvidenceItem`: `id`, `kind` (`ACHIEVEMENT | PROJECT | RESPONSIBILITY | SKILL`), `title` (first person:
"You improved reporting time from two days to three hours"), `detail`, `outcome`, `metric`, `tools[]`,
`source_label` ("From your resume - Sales Analyst role", never "[Page 1]"), `status`
(`PENDING | APPROVED | REMOVED`), `edited`, `updated_at`.

`PATCH /api/v1/career-evidence/{id}` (status, title, detail, outcome, metric) · `POST /api/v1/career-evidence/approve`
`{ids}` · `POST /api/v1/career-evidence/{id}/merge` `{into}`.

Quality gate before anything is shown: drop email, phone, address, URLs, name-only lines, headings and
boilerplate; rank quantified outcomes and action verbs first. Only APPROVED items feed My plan, Home,
story guidance, Dig Deeper and practice. Coverage links cite why they exist (`TOOL | OUTCOME | DECISION |
CAPABILITY | CONFIRMED`); raw word overlap alone never creates a link.

## Session lifecycle

`DRAFT` = created/preparing/ready, not begun · `ACTIVE` · `COMPLETED` · `ABANDONED`. Database status
`ABANDONED` is added. `POST /api/v1/sessions/{id}/abandon` discards a draft or active practice: no review,
idempotent, owner-only. Abandoned practice never appears as "Previous practice" and never on Home.
Only completed attempts are "Previous practice"; drafts are "Continue".

## Reliability

Typed error mapping in the client: 401 (sign in again, keep the intended route), 404 (branded not found,
no Retry), 409, 422 (keep the typed input), 5xx and network (say what did not load, keep work, Retry,
safe Back route). CORS headers on error responses. Busy states disable conflicting controls.

## Language

Address the person as "you". Use "practice" consistently (noun and verb). Core nouns: story, example,
role plan, reflection. Never: pass, fail, score, prediction, weak, readiness percentage, raw page labels,
third-person model output, unexplained levels like "Intermediate". `scripts/copy_lint.py` bans more words
(evidence, assess, analysis, gap, test, candidate, ...) in visible copy: run it.

## Working rules for every workstream

- Read `AGENTS.md`. Smallest correct change; reuse what exists; no new dependencies.
- Own only the files listed for your workstream. New API calls go in a new `apps/web/src/lib/api-<area>.ts`
  built on `request` from `@/lib/api`. New copy goes in a new `apps/web/src/lib/copy-<area>.ts`.
  New backend routes go in `apps/api/app/routes_<area>.py` as an `APIRouter` named `router`, with their
  own dependency factories; the coordinator wires `include_router` in `main.py`.
- Migrations: add one new file in `supabase/migrations/` (do not edit old ones), with RLS owner policies
  and grants matching existing tables, plus a `tests/unit/test_*_migration_contract.py`. Hosted deployment
  is a separate, human step.
- Do not commit. Do not revert other people's changes.
- A PreToolUse "Fact-Forcing Gate" hook may deny the first Edit/Write of a file or the first Bash call:
  state the facts it asks for in one or two lines and retry the identical call.
- Verify: `python -m pytest -q -p no:warnings`, `npm --workspace @mirror/web run typecheck`,
  `python scripts/copy_lint.py`. Report exact results and the exact files you changed.
