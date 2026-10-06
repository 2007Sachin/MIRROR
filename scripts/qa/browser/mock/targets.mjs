// Loop 2 (interview targets) part of the hermetic fake Mirror API, plus the few role/plan endpoints
// the target journeys need. Pure: no sockets, no timers. server.mjs registers `routes`; tests call
// `handle()` directly. Bodies come from ./fixtures/*.json, which tests/unit/test_qa_mock_contract.py
// validates against the real backend models (target/blueprint/round fixtures are generated from the
// real target service with synthetic text; see mock/make_target_fixtures.py).
//
// Scenario control (POST /__qa/scenario, token-guarded in server.mjs) makes error and unavailable
// states deliberate mocked answers rather than unmocked 404s:
//   blueprint: not_researched (default; the real India behaviour) | researched (synthetic fixture)
//              | no_notes (company Mirror has no notes for) | unavailable503 | error500 | slow
//   targets:   available (default) | disabled (flag off: list says DISABLED, writes 503) | none
//   pack:      full (default) | short (SHORT_PACK)

export const TARGET_IDS = {
  target: "00000000-0000-4000-8000-000000000301",
  newRole: "00000000-0000-4000-8000-000000000004",
};

export const QA_RESEARCHED_CODING_PROMPTS = [
  {
    text: "A status update is delayed in a fictional service. How would you trace it?",
    type: "PLANNED",
    answer: "QA-SYNTHETIC-ROUND-ANSWER-ONE: I would trace the update across each fictional service boundary.",
  },
  {
    text: "Which signals would help you narrow down where time is spent?",
    type: "DEPTH_PROBE",
    answer: "QA-SYNTHETIC-ROUND-ANSWER-TWO: I would compare timestamps and payload sizes at each step.",
  },
  {
    text: "What would you tell a teammate while the cause is still unclear?",
    type: "PLANNED",
    answer: "QA-SYNTHETIC-ROUND-ANSWER-THREE: I would share the current explanation and the next check, noting what remains unknown.",
  },
];

export const SCENARIO_VALUES = {
  blueprint: ["not_researched", "researched", "no_notes", "unavailable503", "error500", "slow"],
  targets: ["available", "disabled", "none"],
  pack: ["full", "short"],
};

const ROUND_THEMES = {
  coding_reasoning: "Talking through a coding approach",
  system_design: "Designing a system",
  behavioural: "Examples from your own work",
};
const NEW_ROLE_NAME = "Software Development Engineer (test role)";
const NOT_AVAILABLE = { code: "TARGETS_NOT_AVAILABLE", message: "Targets aren't available yet." };

export function createTargetsMock({ fixture, clock = () => new Date().toISOString(), createSession, roleId, roleName }) {
  const defaults = () => ({ blueprint: "not_researched", targets: "available", pack: "full" });
  const seed = () => ({ ...fixture("target.json"), id: TARGET_IDS.target, role_profile_id: roleId });
  const state = {
    scenario: defaults(),
    targets: new Map(),
    targetCreates: [],
    roundPracticeBodies: [],
    roundPracticeResponses: [],
    analyzeBodies: [],
    activeRolePuts: [],
    links: [],
    practiceKeys: new Map(),
  };

  function reset() {
    state.scenario = defaults();
    state.targets = new Map([[TARGET_IDS.target, seed()]]);
    for (const key of ["targetCreates", "roundPracticeBodies", "roundPracticeResponses", "analyzeBodies", "activeRolePuts", "links"]) state[key] = [];
    state.practiceKeys.clear();
  }
  reset();

  const err = (status, detail) => ({ status, body: { detail } });
  const disabled = () => state.scenario.targets === "disabled";
  const view = (target) => {
    if (state.scenario.blueprint === "researched") {
      const synthetic = fixture("blueprint_researched.json").target;
      return { ...target, company_label: synthetic.company_label, company_key: synthetic.company_key,
        geography_key: synthetic.geography_key, geography_label: synthetic.geography_label, level_key: synthetic.level_key };
    }
    return state.scenario.blueprint === "no_notes"
      ? { ...target, company_key: null, company_label: "QA Company (synthetic)" }
      : target;
  };
  const owned = (id) => {
    const target = state.targets.get(id);
    return target ? view(target) : null;
  };
  const nameFor = (id) => (id === TARGET_IDS.newRole ? NEW_ROLE_NAME : roleName);

  function setScenario(body) {
    if (!body || typeof body !== "object" || Array.isArray(body)) return err(422, "scenario must be an object");
    for (const [key, value] of Object.entries(body)) {
      if (!SCENARIO_VALUES[key]?.includes(value)) return err(422, `unknown scenario ${key}=${value}`);
    }
    Object.assign(state.scenario, body);
    if (body.targets === "none") state.targets.clear();
    if (body.targets === "available" && !state.targets.size) state.targets.set(TARGET_IDS.target, seed());
    return { body: state.scenario };
  }

  // ------------------------------------------------------------------ targets
  function list() {
    if (disabled()) return { body: { availability: "DISABLED", targets: [] } };
    return { body: { availability: "AVAILABLE", targets: [...state.targets.values()].map(view).reverse() } };
  }

  function create({ body }) {
    if (disabled()) return err(503, NOT_AVAILABLE);
    if (!body || typeof body.role_profile_id !== "string" || typeof body.company !== "string" || !body.company.trim()) {
      return err(422, "role_profile_id and company are required");
    }
    if (!["sde_i", "sde_ii", "sde_iii", "university", "not_sure", undefined].includes(body.level)) return err(422, "unknown level");
    if (body.geography === "global") return err(422, "a target is a real place; 'global' is not one");
    state.targetCreates.push(body);
    const clash = [...state.targets.values()].find((t) => t.role_profile_id === body.role_profile_id);
    if (clash) return err(409, { code: "TARGET_EXISTS", target_id: clash.id });
    const id = `00000000-0000-4000-8000-${String(310 + state.targets.size).padStart(12, "0")}`;
    const target = {
      ...fixture("target.json"),
      id,
      role_profile_id: body.role_profile_id,
      company_label: body.company.trim(),
      company_key: body.company.trim().toLowerCase() === "amazon" ? "amazon" : null,
      level_key: body.level ?? "not_sure",
      geography_key: body.geography ?? null,
      geography_label: body.geography_label ?? null,
      created_at: clock(),
    };
    state.targets.set(id, target);
    return { status: 201, body: { target, blueprint: { version: 1, catalog_version: 1, match_state: "NOT_RESEARCHED" } } };
  }

  function read({ match }) {
    if (disabled()) return { body: { availability: "DISABLED", target: null } };
    const target = owned(match[1]);
    return target ? { body: { availability: "AVAILABLE", target } } : err(404, "We couldn't find that target.");
  }

  function blueprint({ match }) {
    if (disabled()) return { body: { ...fixture("blueprint_not_researched.json"), availability: "DISABLED", target: null, blueprint: null, content_state: null, match_state: null, research_label_key: null, claims: [], conflicts: [], unknowns: [], rounds: [] } };
    const target = owned(match[1]);
    if (!target) return err(404, "We couldn't find that target.");
    const scenario = state.scenario.blueprint;
    if (scenario === "unavailable503") return err(503, "Targets aren't available right now. Please try again in a moment.");
    if (scenario === "error500") return err(500, "qa-mock: deliberate server error");
    const base = fixture(scenario === "researched" ? "blueprint_researched.json" : "blueprint_not_researched.json");
    if (scenario === "no_notes") Object.assign(base, { unknowns: [] });
    return { body: { ...base, target }, ...(scenario === "slow" ? { delayMs: 1500 } : {}) };
  }

  function history(targetId, roundKey) {
    const mine = state.links.filter((link) => link.candidate_target_id === targetId && link.round_key === roundKey);
    return { count: mine.length, sessions: mine.map((link) => ({ session_id: link.session_id, created_at: link.created_at })) };
  }

  function roundFixtureName(key) {
    return state.scenario.blueprint === "researched" && key === "coding_reasoning"
      ? "round_coding_reasoning_researched.json"
      : `round_${key}.json`;
  }

  function round({ match }) {
    if (disabled()) return { body: { availability: "DISABLED" } };
    const target = owned(match[1]);
    if (!target) return err(404, "We couldn't find that target.");
    const key = match[2];
    if (!ROUND_THEMES[key]) return err(404, "We couldn't find that round.");
    const detail = { ...fixture(roundFixtureName(key)), target, practice: history(target.id, key) };
    if (state.scenario.pack === "short" && detail.pack) detail.pack = { ...detail.pack, state: "SHORT_PACK", prompts: detail.pack.prompts.slice(0, 3) };
    return { body: detail };
  }

  function practice({ match, body }) {
    if (disabled()) return err(503, NOT_AVAILABLE);
    const target = owned(match[1]);
    if (!target) return err(404, "We couldn't find that target.");
    const key = match[2];
    if (!ROUND_THEMES[key]) return err(404, "We couldn't find that round.");
    if (!body || !["QUICK_DRILL", "FOCUSED_PRACTICE"].includes(body.mode) || typeof body.idempotency_key !== "string") {
      return err(422, "mode and idempotency_key are required");
    }
    state.roundPracticeBodies.push({ target_id: target.id, round_key: key, ...body });
    const replay = state.practiceKeys.get(body.idempotency_key);
    if (replay) {
      if (replay.round_key !== key) return err(409, { code: "SESSION_ALREADY_LINKED" });
      return { status: 201, body: replay.response };
    }
    if (state.scenario.pack === "short") return err(422, { code: "SHORT_PACK", available: 3 });
    const qaPromptSet = state.scenario.blueprint === "researched" && key === "coding_reasoning"
      ? "qa_researched_coding"
      : null;
    const session = createSession({
      target_role: nameFor(target.role_profile_id),
      role_profile_id: target.role_profile_id,
      practice_mode: body.mode,
      practice_focus: "role",
      practice_theme: ROUND_THEMES[key],
      idempotency_key: body.idempotency_key,
      ...(qaPromptSet ? { qa_prompt_set: qaPromptSet } : {}),
    });
    const link = { ...fixture("round_practice_link.json"), session_id: session.id, candidate_target_id: target.id, round_key: key, created_at: clock() };
    state.links.push(link);
    const count = body.mode === "QUICK_DRILL" ? 3 : 4;
    const packPrompts = fixture(roundFixtureName(key)).pack?.prompts ?? [];
    const prompts = Array.from({ length: count }, (_, i) => ({
      position: i + 1,
      rationale_code: packPrompts[i]?.rationale_code ?? "MIRROR_SUGGESTED",
    }));
    const response = { session, link, prompts };
    state.roundPracticeResponses.push({ target_id: target.id, round_key: key, session_id: session.id, prompts });
    state.practiceKeys.set(body.idempotency_key, { round_key: key, response });
    return { status: 201, body: response };
  }

  // ------------------------------------------------------------------ plan and role setup
  function plan({ url }) {
    const requested = url?.searchParams?.get("role_profile_id") || roleId;
    const value = fixture("plan.json");
    value.role = { role_profile_id: requested, target_role: nameFor(requested) };
    return { body: value };
  }

  function analyze({ body }) {
    if (!body || typeof body.target_role !== "string" || body.target_role.trim().length < 2) return err(422, "target_role is required");
    state.analyzeBodies.push(body);
    const value = fixture("role_analysis.json");
    value.target_role = body.target_role.trim();
    return { body: value };
  }

  function setActive({ body }) {
    if (typeof body?.role_profile_id !== "string") return err(422, "role_profile_id is required");
    state.activeRolePuts.push(body.role_profile_id);
    return { body: fixture("active_role.json") };
  }

  function interviewMap({ match }) {
    return { body: { ...fixture("interview_map.json"), role_profile_id: match[1], target_role: nameFor(match[1]) } };
  }

  const routes = [
    ["GET", "/api/v1/targets", list],
    ["POST", "/api/v1/targets", create],
    ["GET", "/api/v1/targets/([^/]+)", read],
    ["GET", "/api/v1/targets/([^/]+)/blueprint", blueprint],
    ["GET", "/api/v1/targets/([^/]+)/rounds/([^/]+)", round],
    ["POST", "/api/v1/targets/([^/]+)/rounds/([^/]+)/practice", practice],
    ["GET", "/api/v1/plan", plan],
    ["POST", "/api/v1/roles/analyze", analyze],
    ["PUT", "/api/v1/active-role", setActive],
    ["GET", "/api/v1/roles/([^/]+)/interview-map", interviewMap],
    ["GET", "/api/v1/career-evidence", () => ({ body: fixture("career_evidence.json") })],
  ];
  const compiled = routes.map(([method, pattern, handler]) => ({ method, pattern: new RegExp(`^${pattern}$`), handler }));

  /** Dispatch without a socket; null when no Loop 2 route matches. */
  function handle(method, pathname, { body = null, url = null } = {}) {
    for (const entry of compiled) {
      const match = entry.pattern.exec(pathname);
      if (entry.method === method && match) return entry.handler({ match, body, url });
    }
    return null;
  }

  return { routes, handle, state, setScenario, reset };
}
