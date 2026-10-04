# DR-0001 Organization memory reuses existing docs
Status: Accepted · 2026-10-04 · Owner: Orchestrator

## Problem
The directive proposes ten new `/docs/mirror-company/*` files incl. `PRODUCT_STATE.md` and `ARCHITECTURE_STATE.md`, but the repo already has `AGENTS.md`, `docs/architecture/IMPLEMENTATION_STATUS.md`, `MIRROR_ARCHITECTURE.md`, `READINESS_SYSTEM_PLAN.md`, `docs/ai/*`, `.agents/skills/`, `.codex/`.
## Evidence
`git ls-files docs .codex .agents` (≈45 files); `IMPLEMENTATION_STATUS.md` is already a maintained per-feature ledger.
## Options
(a) New folder duplicating status/architecture. (b) Put nothing new, only edit existing docs. (c) New folder for *operating layer only*, pointing to existing files as source of truth.
## Decision
(c). `docs/mirror-company/` holds org/process/loop/decisions/research policy/roadmap; `PRODUCT_STATE.md`/`ARCHITECTURE_STATE.md` hold only reconstruction + findings and link to the ledger/architecture docs.
## Reason
Directive §15/§37: avoid duplicate sources of truth; use existing structure where better.
## Consequences
Two places to look; the README source-of-truth map is the guard. Status ledger changes still go in `IMPLEMENTATION_STATUS.md`.
## Revisit when
The operating layer grows files that restate ledger content.
