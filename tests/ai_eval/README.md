# Mirror AI behavioural evaluation suite (`tests/ai_eval/`)

Deterministic, offline checks of how Mirror's **AI-facing system** behaves. No network, no secrets, no paid
model calls. A scripted fake provider stands in for the model; **production code runs unmodified**
(`AgentRunner`, `SkepticWorker`, `SkepticContextBuilder`, `SkepticResultProcessor`, `FlagEligibilityService`,
`InterviewState`, `AssessmentOrchestrator`, `AssessmentDisagreementDetector`, `AssessmentAdjudicator`,
`FinalAssessmentAggregator`, `VerdictLanguageService`, `InterviewPlanningService`) on in-memory repositories.

**What this proves and what it does not.** Deterministic runs exercise selected *pipeline guardrails*
(schema/reference/quote validation, contradiction retyping, delayed flags, plan normalisation,
deterministic disagreement detection) and test whether evaluation oracles detect adversarial artefacts.
They do **not** prove all guardrails hold: strict known-gap xfails below reproduce real production defects.
Typed failures are observed for the Skeptic and planner; verdict service returns **None** and exposes no
service-level typed error. No verdict persistence/flow result is inferred. Planner persistence checks
inspect the actual in-memory repository: a FAILED record is stored but contains no generated plan.
Only Skeptic failure tests exercise deterministic flow continuation. These runs do **not** measure model
quality: the reference provider replays scripted outputs. `live/` is optional, not verified by offline runs;
its assertions require nonempty results and **all** executions successful before behavioural checks.

## Layout

| Path | Purpose |
|---|---|
| `fixtures/scenarios.json` | Synthetic personas P1-P7 (ids match `packages/evaluation/personas.json`), claims, turns, ground-truth `category`, scripted reference Skeptic output. Variants (baseline / short-answer / transcription-noise / recovery) are generated deterministically by `apply_variant`. |
| `ai_eval_harness.py` | Fixture loader, in-memory repository, scripted providers (`reference`, `paranoid`, `accuser`, `generic`, `hallucinating`, `LeakyProvider`, `RaisingProvider`, `RawProvider`), `run_candidate()` pipeline. |
| `ai_eval_checks.py` | The 12 reusable check functions. Each returns `list[str]` of violations; `[]` = pass. |
| `test_eval_skeptic.py` | Behaviours 1-4, 6, 9, 11, 12 and the Skeptic half of 10. |
| `test_eval_assessment.py` | Behaviours 5, 7 and the verdict half of 10. |
| `test_eval_planner.py` | Behaviour 8 and the planner half of 10 (reuses `MemoryPlans`/`plan_output` from `apps/api/tests/test_interview_planner.py` via `importlib`). |
| `test_eval_meta.py` | Persona-manifest coverage, variant determinism, live gating, network rail. |
| `conftest.py` | Autouse rail: deterministic tests fail on any non-loopback `socket.connect`. |
| `live/test_eval_live_skeptic.py` | Optional live scaffold (2 scenarios). Skipped by default. |

Every test carries `@pytest.mark.ai_eval` (registered in `pyproject.toml`; `tests/ai_eval` is in `testpaths`).

## Behavioural spec

Rule: pair real-system contracts with deliberately broken negative controls. If production violates a
contract, reproduce it first and retain a **strict xfail** instead of rewarding the violation as a passing
negative control. A check that cannot fail is a bug in the suite. Numeric support requires COMPLETE
specialists with IDs (including domain IDs) and quotes validated against the supplied transcript;
legacy calls remain valid but cannot establish evidence support without a transcript.

| # | Behaviour | Check fn | Tests (`test_eval_*.py`) | Negative control | Fixtures |
|---|---|---|---|---|---|
| 1 | Skeptic does not challenge every answer; strong evidenced answers raise no flag; flag rate ≤ 0.5 | `check_flag_rate` | skeptic: `test_b1_*` | `paranoid` provider flags every turn | all P1-P7 (11 candidate turns, 4 flagged) |
| 2 | Flag detected at turn N is not eligible at N; only `active` mode probes; `shadow` never does; `InterviewState.eligible_flags` same gating | `check_delayed_flags`, `check_state_machine_flag_gating` | skeptic: `test_b2_*` | `EagerService` (ignores turn + mode), `BrokenState` | P1, P6 (flags that get probed) |
| 3 | Strong answers get no unsupported criticism, even when the model proposes CONTRADICTION/CONTRADICTED | `check_no_unsupported_criticism` | skeptic: `test_b3_*` | `NoGuardProcessor` (no conservative retyping) | P2, P4, P7 strong turns |
| 4 | Vague answer → surfaceable flag whose reason **and** probe share content with the answer/claim; VAGUENESS → DEPTH_PROBE | `check_vague_followup_justified` | skeptic: `test_b4_*` | `generic` provider (boilerplate reason); shadow mode never surfaces | P1/t2, P3/t1 |
| 5 | No invented evidence: cited turns/quotes exist in transcript; no confident number without evidence | `check_no_invented_evidence`, `check_no_numeric_publish_without_evidence` | assessment: `test_b5_*` | `NoQuoteCheckOrchestrator`; over-confident `AggregatedAssessment` | P7 transcript |
| 6 | Feedback/recommendations (flags, observations, claim updates, quotes) reference real fixture turns/claims | `feedback_items` + `check_feedback_references` | skeptic: `test_b6_*` | `NoRefCheckProcessor` + `hallucinating` provider | all personas |
| 7 | Adjudication respects specialist outputs, detects disagreement deterministically, only runs on disagreement, never mutates or rewrites positions | `check_adjudication` | assessment: `test_b7_*` | `FlakyDetector`, mutating repo, position-rewriting decision, adjudicating on agreement | synthetic specialist bundles (strong-vs-weak, agree) |
| 8 | Planner: total time ≤ budget, consumed phase order, `max_probes` ≤ 2, no COMPLETE objective, only supplied claim/competency/project ids | `check_plan_constraints` | planner: `test_b8_*` | `NoNormalizePlanner`; check itself fed COMPLETE/disordered plan | `test_interview_planner` context + hostile draft |
| 9 | Malformed / oversized / extra-field / bad-enum / null provider output rejected through typed error, nothing persisted | `check_structured_output_rejected` | skeptic: `test_b9_*` | lenient validator outcomes | 6 bad payloads on P7 |
| 10 | Failure → no fabricated content; Skeptic/planner expose typed errors; verdict exposes None only. Planner stores failure metadata but no plan; only Skeptic flow continuation is tested | `check_safe_degradation` | skeptic `test_b10_*`, assessment `test_b10_*`, planner `test_b10_*` | fabricating fallbacks (`FabricatingVerdict`, `Fabricating` planner) | P7 |
| 11 | No candidate data crosses candidates through shared repo/runner/provider (unique per-candidate `marker` tokens) | `check_no_cross_candidate_leak` | skeptic: `test_b11_*` | `LeakyProvider` (stateful) | P1, P5, P6, P7 markers |
| 12 | P5 honest beginner: never a CONTRADICTION/OWNERSHIP flag, CONTRADICTION_PROBE, CONTRADICTED/WALKED_BACK update or honesty-accusing wording, in all 4 variants | `check_p5_not_accused` | skeptic: `test_b12_*` | `NoGuardProcessor`; accusatory-wording provider | P5 × 4 variants |

### Known gaps found (strict xfail, not hidden)
* `test_b5_known_gap_quote_free_invented_ids_rejected_before_persistence` — `assessment_orchestrator.py:92-100` checks quotes only; quote-free IDs absent from the transcript are accepted and all 3 specialist rows persist.
* `test_b5_known_gap_invented_ids_do_not_publish_confident_readiness` — real orchestrator → aggregator publishes STRONG, confidence 1, readiness 82 (78–86) using only invented IDs. The transcript-aware checker rejects this support. Rejection or safe aggregation will strict-XPASS and require removing the marker.
* `test_b7_known_gap_real_service_rejects_rewritten_positions_without_persistence` — `assessment_adjudication_service.py:50-56` validates dimension/evidence but not equality of specialist positions; rewritten decision persists. `RewritingAdjudicator` is the separate broken negative-control double.
* `test_b12_known_gap_p5_phrase_i_never_bypasses_guard` — `skeptic_processor.py:40-43,225`: the regex early-return disables contradiction retyping when the answer contains "I never / I didn't / not me…", exactly how an honest beginner talks.
* `test_b12_known_gap_accusatory_probe_text_not_sanitised` — `skeptic_processor.py:222-262` retypes the flag but keeps the model's accusatory `reason`/`suggested_probe`, which `flag_activation.py:119-120` forwards to the interviewer.

## Running

```bash
# deterministic (default; what CI runs)
.venv/Scripts/python.exe -m pytest tests/ai_eval -p no:cacheprovider -q

# only this marker, across the repo
.venv/Scripts/python.exe -m pytest -m ai_eval -p no:cacheprovider -q

# live (optional, costs tokens, never in CI): needs ALL three env vars; key is never printed or read from .env
MIRROR_LIVE_EVAL=1 MIRROR_LIVE_MODEL=<model-id> SARVAM_API_KEY=... \
  .venv/Scripts/python.exe -m pytest tests/ai_eval/live -p no:cacheprovider -q
```

## Adding a scenario

1. Add a candidate (or a turn) to `fixtures/scenarios.json`: `claims[]`, `turns[]` with `q`, `text`, `category`
   (`strong | vague | inflated | ownership_drift | honest_beginner | collapse`) and the `skeptic` script (flags/observations the
   *well-behaved* model should emit). Use a unique `marker` word per candidate. Keep claim wording overlapping the answer so
   `SkepticContextBuilder` retrieves it. Synthetic data only.
2. If it should be covered by all four variants, nothing else is needed (`apply_variant`); add the id to `ALL` in the tests.
3. Pick the behaviour's check fn and add a test pair: real → `== []`, broken double → non-empty. New failure shape?
   Add a style to `ScriptedSkepticProvider` or a subclass double in the test file.
4. Never weaken a check to make a test pass; if production is wrong, record `file:line` and use
   `xfail(strict=True)` with the reason (see Known gaps).
