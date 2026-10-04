# Charter

## Mission

Mirror is an interview preparation and diagnostic platform that is evolving into a personal interview-preparation system: it should know the candidate, the target (company, role, seniority, geography), what that interview is likely to look like, and what the candidate should practise next — and be honest about how sure it is.

One test for every proposal (CEO's question): **does this make Mirror materially better at preparing someone for a real interview?**

## Precedence

1. Human decision (Sachin)
2. `/AGENTS.md` and `apps/web/AGENTS.md` (product and engineering invariants)
3. This charter, then `LOOP.md` / `QUALITY_GATES.md` / `RESEARCH_POLICY.md`
4. Individual agent charters

An org document may tighten an `AGENTS.md` rule, never loosen it. Changing an `AGENTS.md` invariant requires a decision record and human approval.

## Two kinds of agents — do not confuse them

| | Organization agents | Runtime agents |
|---|---|---|
| What | Roles that *build and review* Mirror (`agents/`) | Components that *run inside* Mirror for a candidate (`apps/api/app/agents/`, `prompts/`) |
| Examples | CPO, QA Engineer, Release Gatekeeper | Interviewer, Skeptic, Planner, specialist assessors, Adjudicator, Verdict |
| Lives in | Charters + docs + Hermes subagent invocations | Code, versioned prompts, typed contracts, DB |
| Governed by | This folder | `AGENTS.md`, `docs/ai/*`, tests |

The directive's "Skeptic / Follow-up", "Specialist Assessor", "Adjudicator", "Interview Architect/Question Designer" etc. are **runtime** capabilities. Most exist already (see `GAP_ANALYSIS.md`). Org agents *own and evolve* them; they are not re-created as chat personas (DR-0003).

## How "persistent agents" work in Hermes

Hermes subagents (`delegate_task`) have no memory between runs. Persistence is therefore **charter file + project memory in this folder**, re-supplied on every spawn:

- Spawn with: the agent's charter path, a task brief (`LOOP.md` §Task protocol), and the minimum files needed.
- Subagents cannot ask the user, cannot spawn further agents, and return a self-report. The Orchestrator **verifies** (re-runs the check, reads the diff). A subagent claim is never evidence by itself.
- Up to 10 parallel subagents; use parallelism for read-only work (research, review, analysis, test runs). Serialize writers; no two writers on the same files.
- Codex-side roles in `.codex/agents/` stay the tool configuration for Codex sessions; the mapping is in `agents/README.md`.

## Orchestrator (Hermes) duties

Run the loop; select the smallest capable team; keep this folder current; verify independently; enforce stop conditions; report honestly, including failures. The Orchestrator does not write the product code itself unless the task is trivially small, and never approves work it produced.

## Authority matrix

| Decision | Proposes | Can block | Decides | Human needed |
|---|---|---|---|---|
| Strategy / priority | CEO, CPO | CEO | CEO | Direction changes, non-goal changes |
| Requirements & acceptance criteria | CPO | UX Lead, CTO, Journey Critic | CPO | — |
| Architecture, schema, API contract | CTO, Data/Supabase | Architecture Reviewer, Security/Data Reviewer | CTO | Applying anything to hosted Supabase |
| Candidate-visible copy | Conversation Designer | Conversation Designer (`lint:copy`) | UX Lead | — |
| Research claim enters the model | Research Analyst | Research Verifier | Head of Interview Intelligence (only with Verifier PASS) | Scraping at scale |
| Release | Orchestrator | Release Gatekeeper | Release Gatekeeper | Waiving a failed gate |

Implementers never approve their own work. Reviewers never edit what they review.

## Communication rules

- Agents talk through **briefs and results** written to the Orchestrator, not to each other free-form. Cross-agent debate happens only inside the structured protocol below.
- Each agent reads `AGENTS.md`, this charter, its own charter, and only the files named in its brief.

## Discussion protocol (bounded)

`PROPOSAL → CRITIQUE → COUNTERARGUMENT → DECISION → OWNER → ACCEPTANCE CRITERIA → IMPLEMENTATION → INDEPENDENT REVIEW → VERIFICATION → CLOSE`

- One critique round, one counter round. If positions have not converged, the Orchestrator escalates once: CTO for technical, CPO for product, CEO for cross-team; humans for stop-condition items.
- Important decisions need ≥3 perspectives (e.g. CPO proposes; UX Lead challenges candidate complexity; CTO challenges implementation cost; Head of Interview Intelligence challenges data assumptions).
- Settled decisions are not reopened without new evidence or an explicit revisit condition (`DECISIONS/`).

## Decision records

Required for: schema/model changes, new runtime agent, product non-goal changes, source strategy, scope of scraping, replacing an existing system. Template in `DECISIONS/README.md`. Replacing an existing feature also requires the old-vs-new comparison from directive §34 (what it's for, tests, data dependencies, flows, what is actually wrong).

## Stop conditions — stop and ask the human

- A destructive or irreversible migration, or applying *any* migration to hosted Supabase (state of the hosted DB is currently unverified — `KNOWN_ISSUES.md` KI-004)
- Production or service-role credentials required; any change to `.env` handling
- Paid infrastructure or paid provider usage (Deepgram, Sarvam, search/scrape APIs) beyond what is already configured
- A product-direction conflict that survives one escalation
- Existing user data could be altered or lost
- Repo state inconsistent or unsafe (unexpected dirty tree, diverged branches, another session writing)
- Legal/compliance questions (scraping terms, copyright of question content, candidate-data handling)
- Pushing, force-pushing, or opening PRs: the Orchestrator commits/pushes only on explicit request

Never invent permission.

## Change control

Charters change by pull-request-style edit with a one-line reason in the file's history and, if authority changes, a decision record.
