# Loops and protocols

## Engineering loop

`OBSERVE → UNDERSTAND → SELECT → PLAN → CHALLENGE → IMPLEMENT → TEST → REVIEW → BROWSER/REAL-WORLD VERIFY → REFLECT → UPDATE MEMORY → SELECT NEXT`

Every iteration has **one bounded objective** (one candidate-visible outcome or one enabling system, never several major systems), a loop id (`LR-NNNN`), and ends in a receipt in `RECEIPTS/`.

| Step | Owner | Exit criteria |
|---|---|---|
| OBSERVE | Orchestrator | `git status` clean or explained; baseline checks re-run (not trusted from last receipt); `KNOWN_ISSUES.md` read; last receipt's claims spot-checked |
| UNDERSTAND | Explorer (read-only) | Execution paths cited with file:line for the affected area |
| SELECT | CPO (CEO on conflict) | One objective chosen from `ROADMAP.md` with a stated candidate-value reason |
| PLAN | CPO + CTO | Plan has: problem, user impact, current/desired behaviour, requirements, affected systems, data implications, risks, acceptance criteria, test strategy, rollback |
| CHALLENGE | UX Lead, CTO, Head of II (as relevant), Journey Critic | One critique round recorded; decision record if significant |
| IMPLEMENT | Smallest capable engineering set; one writer per file set | Diff matches plan; no unrelated changes |
| TEST | QA Engineer (+ AI Eval for AI changes) | Gate evidence per `QUALITY_GATES.md`, labelled VERIFIED-EXECUTED or STATIC-ONLY |
| REVIEW | Architecture Reviewer, Security/Data Reviewer, Journey Critic (parallel) | No unresolved blocker; implementer is not a reviewer |
| REAL-WORLD VERIFY | QA / Orchestrator | Real browser or API run where possible; otherwise explicitly recorded as not done |
| REFLECT | Orchestrator | The receipt's reflection questions answered honestly |
| UPDATE MEMORY | Orchestrator | `CURRENT_SPRINT.md`, `KNOWN_ISSUES.md`, `ROADMAP.md`, status ledger, decisions updated |

### Failure handling and retry limits

`IMPLEMENT → VERIFY → FAILURE → DIAGNOSE → FIX → VERIFY`

- Diagnose before fixing (root cause, not symptom).
- Max **2 fix attempts** per failing check; then escalate to CTO (technical) or CPO (product) with the evidence.
- Max **1 re-plan** per objective; a second means the objective is mis-scoped → CPO re-selects.
- Never hide, skip, or `xfail` a failing check to keep the loop moving. A failure that is environmental (e.g. no TTY, stale generated files) is reported separately from a regression, per `AGENTS.md`.

### Continuation protocol (another session picks up)

1. Read `/AGENTS.md`, `CURRENT_SPRINT.md`, the newest `RECEIPTS/LR-*.md`, `KNOWN_ISSUES.md`.
2. Run `git status -sb` and `git log -5`; if the tree is dirty or the head moved since the receipt's recorded commit, stop and reconcile before anything else.
3. Re-run the baseline in `QUALITY_GATES.md` §Baseline. Compare to the receipt's numbers; a difference is the first finding.
4. Resume at the receipt's `NEXT RECOMMENDED WORK`, not at memory of what "should" be next.

### Task protocol (Orchestrator → org agent)

Brief (pass as `context`/`goal` to the subagent):

```
AGENT: <id>            CHARTER: docs/mirror-company/agents/<id>.md
OBJECTIVE: <one sentence>        LOOP: LR-NNNN
READ: <exact files>              DO NOT TOUCH: <paths>
MODE: read-only | write (files: …)
OUTPUT: <schema / file path>     DEADLINE: <time-box>
ACCEPTANCE: <testable criteria>
```

Result (what the agent must return): `STATUS (done|blocked|failed)`, `EVIDENCE` (commands run + outputs, file:line cites), `LABEL` per claim (`VERIFIED-EXECUTED` / `STATIC-ONLY`), `CHANGES` (files), `RISKS`, `OPEN QUESTIONS`. The Orchestrator re-checks anything it will rely on.

### Loop receipt

Stored as `RECEIPTS/LR-NNNN-<slug>.md` with: LOOP ID · OBJECTIVE · AGENTS USED · FILES CHANGED · DATABASE CHANGES · TESTS (command → result) · BROWSER VERIFICATION · RESEARCH ADDED · DECISIONS · FAILURES · KNOWN ISSUES · NEXT RECOMMENDED WORK · plus the git head at start/end.

## Research loop (Interview Intelligence)

`TARGET RESEARCH GAP → DISCOVER SOURCES → EXTRACT CLAIMS → NORMALIZE → CROSS-CHECK → ASSIGN CONFIDENCE → STORE PROVENANCE → UPDATE INTERVIEW MODEL → TEST GENERATED INTERVIEW → REVIEW`

| Step | Owner | Notes |
|---|---|---|
| Target gap | Head of II | One company×role×seniority×geography slice per loop; recorded in `RESEARCH_STATE.md` |
| Discover | Research Analyst | Source-policy check first (`RESEARCH_POLICY.md` §Scraping); official sources first |
| Extract | Research Analyst | Claims in the claim schema; no verbatim question banks |
| Normalize | Taxonomy Engineer | Map to taxonomy ids; keep unmapped terms as aliases |
| Cross-check | **Research Verifier** (separate invocation) | Verdict PASS / PASS-WITH-LIMITS / FAIL; independence of corroboration checked |
| Confidence | Deterministic rules (`INTERVIEW_INTELLIGENCE.md` §Confidence) | Not an LLM opinion |
| Store | Research/Data Pipeline Eng. (dormant until DR-0004) / interim: curated files | Version, never overwrite |
| Update model | Head of II | Only claims with Verifier PASS |
| Test | AI Evaluation Agent | A generated interview from the new slice; check provenance wording and no verbatim leakage |
| Review | Journey Critic + Security/Data Reviewer | Candidate-facing wording; no PII from sources |

Refresh: each claim class has a staleness window (`RESEARCH_POLICY.md`); `RESEARCH_STATE.md` lists slices past their window. Refresh produces a **new version**; history is kept.
