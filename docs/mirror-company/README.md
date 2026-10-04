# Mirror company — operating layer

Status: bootstrap v0 · created 2026-10-04 · maintained by the Orchestrator (Hermes)

This folder holds **how Mirror is run**: the organization, the loops, the gates, the decisions, the roadmap and the research policy. It deliberately does **not** restate product or architecture facts that already have a home in this repo (see the map below). One fact, one file.

## Source-of-truth map

| Topic | Authoritative file | Notes |
|---|---|---|
| Product rules, engineering rules, verification commands | `/AGENTS.md` | Wins over everything in this folder |
| Feature-by-feature status ledger | `docs/architecture/IMPLEMENTATION_STATUS.md` | Not duplicated here. `PRODUCT_STATE.md` only adds the reconstructed journey + gaps |
| Architecture, topic designs | `docs/architecture/*.md`, `docs/architecture.md` | `ARCHITECTURE_STATE.md` records forensics findings and links back |
| Runtime agent contracts (Interviewer, Skeptic, Planner, assessors…) | `docs/ai/*.md`, `docs/architecture/agents.md`, `apps/api/app/prompts/` | These are **product code**, not org agents (DR-0003) |
| Candidate-facing copy | `docs/copy-guide.md` (+ `npm run lint:copy`) | |
| Codex tool config for roles | `.codex/config.toml`, `.codex/agents/*.toml` | Org charters link to these; they are not copied |
| Project skills | `.agents/skills/` | |
| Org, process, loop state, decisions, research policy | `docs/mirror-company/` | This folder |

## Files

- `CHARTER.md` — mission, authority, protocols, stop conditions
- `agents/` — one charter per organization agent + roster (`agents/README.md`)
- `LOOP.md` — engineering loop, research loop, task protocol, continuation protocol
- `QUALITY_GATES.md` — gates G0–G5 and the evidence-labelling rule
- `PRODUCT_STATE.md` — CURRENT MIRROR (journey, capability classes, fragmentation)
- `ARCHITECTURE_STATE.md` — forensics findings and technical debt
- `GAP_ANALYSIS.md` — CURRENT vs TARGET Mirror
- `INTERVIEW_INTELLIGENCE.md` — design proposal (data model, taxonomy, confidence, question architecture)
- `RESEARCH_POLICY.md` — provenance classes, verification, scraping safety, copyright
- `RESEARCH_STATE.md` — research gaps and coverage ledger
- `ROADMAP.md` — dependency-aware roadmap + prioritized backlog
- `CURRENT_SPRINT.md`, `KNOWN_ISSUES.md`, `RELEASES.md`
- `DECISIONS/` — decision records (`DR-NNNN-*.md`)
- `RECEIPTS/` — loop receipts (`LR-NNNN-*.md`)

## Read order for a fresh session

1. `/AGENTS.md`
2. `CURRENT_SPRINT.md` → latest file in `RECEIPTS/` → `KNOWN_ISSUES.md`
3. Only then the files named in the current task brief. Do **not** reread the whole repo.
