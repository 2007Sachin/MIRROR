# DR-0002 Consolidated 21-role organization
Status: Accepted · 2026-10-04 · Owner: CEO role (Orchestrator acting) — revisit with human

## Problem
The directive lists ~34 named roles but says not to create agents to inflate count and to adjust after inspection.
## Evidence
No company/round/source data exists yet (`GAP_ANALYSIS.md`); Codex already defines 10 project roles (`.codex/config.toml`); Hermes subagents are ephemeral, ≤10 parallel, can't delegate.
## Options
(a) 34 separate agents. (b) Merge by shared tools/authority, keep independence where it matters. (c) Tiny team of ~8.
## Decision
(b): 21 org agents (20 active, 1 dormant). Merges: Company/Role/Round Research → one **Research Analyst** invoked per slice; Candidate Journey Critic + Product Critic → **Journey Critic**; Architecture Reviewer maps to Codex `code-reviewer`. Dormant: Research/Data Pipeline Engineer until DR-0004. Interview Architect, Question Designer, Resume Interrogator, Skeptic, Difficulty Controller, assessors, Adjudicator are **runtime** components (DR-0003). Independence kept for: Research Verifier, QA, Journey Critic, Architecture, Security/Data, AI Evaluation, Release Gatekeeper.
## Reason
Same-tools/same-authority roles add coordination cost without independent judgement. Independent checking is what the directive actually demands.
## Consequences
Fewer hand-offs; Research Analyst needs a slice parameter in its brief. Roster in `agents/README.md`.
## Revisit when
Research volume forces parallel specialists, or a merged role repeatedly fails review for being too broad.
