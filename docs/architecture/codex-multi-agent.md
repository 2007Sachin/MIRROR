# Codex multi-agent setup

Mirror uses Codex as an orchestrator over bounded project roles. The product architecture remains authoritative: deterministic backend services own identity, persistence, lifecycle, phases, timing, retries, authorization, and failures; product agents reason through typed contracts and do not own SQL or canonical workflow state.

## Installed layers

- ECC 2.2.2 is installed as the native `ecc@ecc` Codex marketplace plugin from `affaan-m/ECC`. The legacy sync installer is intentionally not used because native plugin installation is the current supported path and avoids copied global configuration.
- Ponytail 4.10.0 is installed as `ponytail@ponytail` from `DietrichGebert/ponytail`. Its default mode is `full`; `ultra` is opt-in only. Its three Codex lifecycle hooks must be reviewed and trusted in `/hooks` before they execute.
- Mirror-specific skills remain in `.agents/skills/` and project roles remain in `.codex/agents/`.

## Roles and delegation

`.codex/config.toml` defines `max_threads = 6` and `max_depth = 1`:

- `explorer`: read-only repository and execution-path evidence.
- `planner`: read-only stages, dependencies, risks, and acceptance criteria.
- `frontend-engineer`: Next.js, React, TypeScript, accessibility, and existing Mirror UI.
- `backend-engineer`: FastAPI, contracts, workers, retries, and idempotency.
- `supabase-engineer`: read-only-by-default schema, migrations, RLS, Auth, Storage, and indexes.
- `ai-orchestration-engineer`: bounded interview intelligence and deterministic aggregation.
- `qa-engineer`: focused tests, regression checks, and browser/user-flow verification.
- `security-reviewer`: read-only security and trust-boundary review.
- `code-reviewer`: read-only final correctness, regression, maintainability, and security review.
- `docs-researcher`: read-only primary-documentation verification.

Use read work in parallel when useful, but avoid concurrent writes to the same files. Typical flows are `explorer → frontend-engineer → qa-engineer → code-reviewer` for UI work and `explorer → planner → relevant implementation roles → qa-engineer → security-reviewer when needed → code-reviewer` for larger or data-sensitive work.

## MCP integrations

Existing user MCP configuration is preserved: `node_repl`, `21st`, and Playwright. Do not add duplicate definitions or commit credentials. ECC's retired/optional MCP definitions are not merged automatically. Use Playwright for actual UI journeys when it is available and authenticated.

## Maintenance

- Inspect the active setup with `codex plugin list --json`, `codex plugin marketplace list --json`, and `codex features list`.
- Update ECC with the native marketplace upgrade flow, then re-check the installed version and hooks. Do not combine native plugin installation with the legacy `sync-ecc-to-codex.sh` path.
- Update Ponytail with its marketplace upgrade and plugin add flow; review changed hooks in `/hooks` again.
- Temporarily disable a plugin with Codex's plugin management commands; do not edit product files or remove Mirror's `AGENTS.md`.
- If multi-agent behavior fails, validate TOML parsing, role config paths, `multi_agent`, `max_threads`, and `max_depth`, then run a read-only explorer audit before changing implementation.

## Safe audit prompt

Use: “Audit the Mirror authentication and onboarding flow. Do not modify anything.” Relevant roles are `explorer`, `frontend-engineer`, `backend-engineer`, `supabase-engineer`, and `security-reviewer`. The orchestrator must independently inspect the reports and verify that no files or database state changed.
