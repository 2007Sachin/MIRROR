# DR-0003 Organization agents vs runtime agents
Status: Accepted · 2026-10-04 · Owner: CTO role

## Problem
The directive mixes roles that *build* Mirror (CPO, QA…) with capabilities that *run inside* Mirror for candidates (Skeptic, Specialist Assessor, Adjudicator, Question Designer…).
## Evidence
`apps/api/app/agents/` already implements Interviewer, Skeptic, Planner, Resume, Role, Evidence, specialist assessors (TECHNICAL/BEHAVIOUR/CLAIMS), Adjudicator, Verdict, retry-comparison with versioned prompts; `AGENTS.md`: "No uncontrolled agent-to-agent workflow", "orchestration testable without an LLM".
## Options
(a) Create chat-persona org agents for each runtime role. (b) Treat runtime roles as product code owned by AI Systems Eng + reviewed by AI Evaluation Agent; create only new runtime agents the product lacks.
## Decision
(b).
## Reason
Duplicate personas would drift from the code; the code and its tests are the truth. Missing runtime capabilities (Communication assessor, Question Designer, Difficulty Controller) are product work items (`GAP_ANALYSIS.md`), each needing a prompt version, contract, tests and G4.
## Consequences
Org charters reference runtime modules as owned files. Runtime agents never run as org agents and vice versa.
## Revisit when
A runtime capability is better delivered as deterministic code (then no agent at all).
