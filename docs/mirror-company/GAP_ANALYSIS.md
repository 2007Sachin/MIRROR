# Gap analysis: CURRENT MIRROR → TARGET MIRROR

Target chain from the bootstrap directive: Candidate → Target Company → Target Role → Seniority → Geography → Resume → Interview Intelligence → Expected Process → Customized Plan → Multiple Rounds → Adaptive Interview → Assessment → Diagnosis → Practice → Progress → Reassessment.

Legend: ✅ exists · ◐ partial · ✗ absent. Size S/M/L/XL is a rough engineering estimate, not a commitment.

| Target element | State | Current reality | Gap | Size | Depends on |
|---|---|---|---|---|---|
| Candidate profile | ✅ | `profiles`, onboarding, evidence library | — | — | — |
| Target company | ✗ | Free text `profiles.target_company` (typed at onboarding; nothing downstream uses it) and `interview_events.company_label`; no entity | Company entity, alias mapping of both free-text fields, link from role target; make the onboarding company field actually do something | M | Taxonomy v1 |
| Target role | ◐ | `role_profiles` per user + LLM Role agent + 4 synthetic canonical profiles | Role family/normalised role registry; stop treating 4 synthetic roles as the vocabulary | M | Taxonomy v1 |
| Seniority | ◐ | `role_seniority` enum on `role_profiles` | Use as a research/process scope dimension | S | Taxonomy v1 |
| Geography | ✗ | Only `preferred_language` | Geography entity + candidate target field | S | Taxonomy v1 |
| Resume | ✅ | Resume agent, claims graph, evidence library | — | — | — |
| Interview Intelligence | ✗ | Nothing (`question_bank`/`rubrics` dormant; synthetic competency maps in code) | Entire layer: sources, claims, provenance, versions, confidence | XL | DR-0004/0005 approval |
| Expected interview process | ✗ | Fixed phases; brief says company not researched | Process + round model per company×role×seniority×geo, versioned | L | Intelligence layer |
| Customized interview plan | ◐ | Planner v3 per session from claims/competencies/docs | Blueprint over rounds; inputs: process, stories, Interview Map, past performance | L | Process model |
| Multiple rounds | ✗ | Single session per plan (`interview_plans` allows several rows per session, one `PROCESSING` at a time). A round vocabulary exists only for *recorded real interviews* (`RoundKind`, `interview_event_models.py:25-31`) | `interview_blueprints` → rounds → sessions; cross-round adjudication; **map to `RoundKind` instead of inventing a second vocabulary** | L | Blueprint |
| Adaptive interview | ◐ | Skeptic, probes, ladder up/down | Per-competency difficulty state; explicit "why this follow-up" reasons persisted; Resume Interrogator beyond deterministic Pressure Test | M | Blueprint (for round context) |
| Assessment | ◐ | TECHNICAL, BEHAVIOUR, CLAIMS assessors + adjudicator | Communication assessor (independent of correctness); round-scoped rubrics | M | Round rubrics |
| Diagnosis | ✅ | Verdict + candidate-safe report | Cross-round diagnosis | M | Multi-round |
| Practice | ✅ | Modes, recommendation, Try again, story loop | Recommendation driven by competency×round, not only role dimensions | M | Progress model |
| Progress | ◐ | Role-level; attempt-aware paused | Levels: company, round, competency, skill, question family, story, attempt, time | L | Taxonomy, blueprint |
| Reassessment | ◐ | Implicit via new sessions | Deliberate reassessment of weak competencies; question novelty tracking | M | Difficulty state, question history |
| Provenance & uncertainty UX | ✗ | Limitation text only | Plain-language provenance in brief/Interview Map; never raw confidence jargon | M | Intelligence layer, UX Lead |
| Org verification (CI, QA user, AI eval) | ✗ | Backend tests only | CI; synthetic QA user; executable AI eval harness | M | — (prerequisite) |

## Runtime-agent coverage vs directive (so we don't build what exists)

| Directive capability | In code today | Action |
|---|---|---|
| Interview Architect | Planner v3 (single session) | Evolve into blueprint builder (deterministic skeleton + bounded agent) |
| Question Designer | Planner emits `initial_question` per objective | Separate bounded Question Designer once rounds/intelligence exist |
| Resume Interrogator | `pressure_test.py` (deterministic) + Resume agent | Keep deterministic core; add bounded agent only if eval shows need |
| Skeptic / Follow-up | `agents/skeptic.py`, `skeptic_processor.py`, flag activation | Preserve; add persisted follow-up *reason* codes |
| Difficulty Controller | `ladder_up/down` turn types, `difficulty_start` | Build per-competency state (deterministic) |
| Specialist assessor | TECHNICAL | Preserve |
| Behavioral assessor | BEHAVIOUR | Preserve |
| Communication assessor | partly inside the BEHAVIOUR prompt | New, independent of correctness |
| Evidence/Claim assessor | CLAIMS + Evidence agent | Preserve |
| Adjudicator | `agents/adjudicator.py`, deterministic disagreement detection | Extend to cross-round |

## Preserved invariants the target must not break

Hidden evaluation never shown live; deterministic orchestration testable without an LLM; candidate-owned story content; versioned prompts; additive-only migrations; candidate-safe language with stated limitations.
