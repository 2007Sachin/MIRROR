// Loop 2 mock routes, exercised without sockets or a browser (pure dispatch).
// Run: node --test scripts/qa/browser/tests/targets-mock.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

import { TARGET_IDS, createTargetsMock } from "../mock/targets.mjs";

const ROLE = "00000000-0000-4000-8000-000000000002";
const FIXTURES = new URL("../mock/fixtures/", import.meta.url);
const fixture = (name) => JSON.parse(fs.readFileSync(new URL(name, FIXTURES), "utf8"));

function setup() {
  const sessions = [];
  const mock = createTargetsMock({
    fixture,
    roleId: ROLE,
    roleName: "QA Analyst (test role)",
    createSession: (body) => {
      const session = { id: `00000000-0000-4000-8000-${String(700 + sessions.length).padStart(12, "0")}`, ...body };
      sessions.push(session);
      return session;
    },
  });
  return { mock, sessions, get: (path, url) => mock.handle("GET", path, { url: url ?? new URL(`http://x${path}`) }) };
}

test("blueprint exposes an independently initialized candidate stage plan", () => {
  const { mock, get } = setup();
  const view = get(`/api/v1/targets/${TARGET_IDS.target}/blueprint`).body;
  assert.deepEqual(view.candidate_stage_plan, {
    candidate_stage_state: "NOT_ASKED",
    candidate_stage_order_known: false,
    candidate_stages: [],
    candidate_stage_mapping_version: 0,
    candidate_stage_notes_revision: 0,
    notes: {},
  });
  assert.equal(view.blueprint.latest_version, view.blueprint.version);
  const newTarget = mock.handle("POST", "/api/v1/targets", { body: {
    role_profile_id: TARGET_IDS.newRole, company: "Amazon", role_family: "software_development_engineering", level: "sde_ii",
  } });
  assert.equal(newTarget.status, 201);
  const createdView = get(`/api/v1/targets/${newTarget.body.target.id}/blueprint`).body;
  assert.equal(createdView.candidate_stage_plan.candidate_stage_state, "NOT_ASKED");
  assert.notEqual(createdView.target.id, view.target.id);
});

test("stage save uses immutable blueprint versions, CAS, idempotency, and current-only notes", () => {
  const { mock, get } = setup();
  const path = `/api/v1/targets/${TARGET_IDS.target}/blueprint`;
  const stageId = "10000000-0000-4000-8000-000000000001";
  const desired = { expected_blueprint_version: 1, state: "KNOWN", order_known: true,
    stages: [{ stage_id: stageId, kind: "OTHER", custom_label: " Take-home ", certainty: "SURE", sequence: 1 }], notes: { [stageId]: " Prep notes " } };
  const saved = mock.handle("PUT", `${path}/stages`, { body: desired });
  assert.equal(saved.body.blueprint.version, 2);
  assert.equal(saved.body.blueprint.latest_version, 2);
  assert.equal(saved.body.candidate_stage_plan.candidate_stages[0].custom_label, "Take-home");
  assert.deepEqual(saved.body.candidate_stage_plan.notes, { [stageId]: "Prep notes" });
  assert.equal(mock.handle("PUT", `${path}/stages`, { body: desired }).body.blueprint.version, 2, "identical stale write is idempotent");
  const changed = { ...desired, expected_blueprint_version: 1, notes: { [stageId]: "Different" } };
  assert.deepEqual(mock.handle("PUT", `${path}/stages`, { body: changed }).body.detail, { code: "STAGE_PLAN_STALE" });
  assert.equal(mock.handle("GET", `/api/v1/targets/${TARGET_IDS.target}/rounds/coding_reasoning`).body.candidate_stage_plan, undefined);
  const cleared = mock.handle("PUT", `${path}/stages`, { body: { expected_blueprint_version: 2, state: "NOT_YET", order_known: false, stages: [], notes: {} } });
  assert.equal(cleared.body.blueprint.version, 3);
  assert.deepEqual(cleared.body.candidate_stage_plan.notes, {});
  assert.equal(mock.handle("PUT", `${path}/stages`, { body: { ...desired, expected_blueprint_version: 3, stages: [], notes: {} } }).status, 422);
  const tooMany = Array.from({ length: 13 }, (_, i) => ({ ...desired.stages[0], stage_id: `20000000-0000-4000-8000-${String(i + 1).padStart(12, "0")}`, custom_label: "Stage", sequence: i + 1 }));
  assert.equal(mock.handle("PUT", `${path}/stages`, { body: { ...desired, expected_blueprint_version: 3, stages: tooMany, notes: {} } }).status, 422);
  mock.reset();
  assert.equal(get(path).body.blueprint.version, 1);
  assert.deepEqual(get(path).body.candidate_stage_plan.notes, {});
});

test("a concurrent stage update returns a stale conflict without overwriting the other draft", () => {
  const { mock, get } = setup();
  const path = `/api/v1/targets/${TARGET_IDS.target}/blueprint`;
  const stageId = "10000000-0000-4000-8000-000000000004";
  const original = { expected_blueprint_version: 1, state: "KNOWN", order_known: false,
    stages: [{ stage_id: stageId, kind: "TECHNICAL_INTERVIEW", custom_label: null, certainty: "UNCERTAIN", sequence: null }],
    notes: { [stageId]: "Original note" } };
  assert.equal(mock.handle("PUT", `${path}/stages`, { body: original }).body.blueprint.version, 2);
  mock.setScenario({ stageSave: "stale_once" });
  const localDraft = { ...original, expected_blueprint_version: 2, notes: { [stageId]: "Local unsaved draft" } };
  const result = mock.handle("PUT", `${path}/stages`, { body: localDraft });
  assert.equal(result.status, 409);
  assert.deepEqual(result.body.detail, { code: "STAGE_PLAN_STALE" });
  const latest = get(path).body;
  assert.equal(latest.blueprint.version, 3);
  assert.deepEqual(latest.candidate_stage_plan.notes, { [stageId]: "QA-SYNTHETIC-REMOTE-NOTE" });
  assert.equal(latest.candidate_stage_plan.candidate_stages[0].stage_id, stageId);
});

test("a target-practice session stays pinned to the stage-plan version current at start", () => {
  const { mock } = setup();
  const planPath = `/api/v1/targets/${TARGET_IDS.target}/blueprint`;
  const stageId = "10000000-0000-4000-8000-000000000003";
  const saved = mock.handle("PUT", `${planPath}/stages`, { body: {
    expected_blueprint_version: 1, state: "KNOWN", order_known: false,
    stages: [{ stage_id: stageId, kind: "CODING_EXERCISE", custom_label: null, certainty: "SURE", sequence: null }],
    notes: {},
  } });
  assert.equal(saved.body.blueprint.version, 2);
  const pinned = mock.handle("POST", `/api/v1/targets/${TARGET_IDS.target}/rounds/coding_reasoning/practice`, {
    body: { mode: "FOCUSED_PRACTICE", idempotency_key: "qa-stage-session-v2" },
  });
  assert.equal(pinned.status, 201);
  const pinnedBlueprintId = pinned.body.link.blueprint_id;
  assert.equal(pinnedBlueprintId, mock.state.stagePlans.get(TARGET_IDS.target).blueprint_id);
  const cleared = mock.handle("PUT", `${planPath}/stages`, { body: {
    expected_blueprint_version: 2, state: "NOT_YET", order_known: false, stages: [], notes: {},
  } });
  assert.equal(cleared.body.blueprint.version, 3);
  assert.notEqual(mock.state.stagePlans.get(TARGET_IDS.target).blueprint_id, pinnedBlueprintId);
  assert.equal(mock.state.links.at(-1).blueprint_id, pinnedBlueprintId, "later edits do not rewrite the session's blueprint pin");
});

test("stage state is cleared when the mock target fixture is removed and recreated", () => {
  const { mock, get } = setup();
  const path = `/api/v1/targets/${TARGET_IDS.target}/blueprint`;
  const stageId = "10000000-0000-4000-8000-000000000002";
  const saved = mock.handle("PUT", `${path}/stages`, { body: {
    expected_blueprint_version: 1, state: "KNOWN", order_known: false,
    stages: [{ stage_id: stageId, kind: "CODING_EXERCISE", custom_label: null, certainty: "SURE", sequence: null }],
    notes: { [stageId]: "private note" },
  } });
  assert.equal(saved.body.blueprint.version, 2);
  mock.setScenario({ targets: "none" });
  mock.setScenario({ targets: "available" });
  const fresh = get(path).body;
  assert.equal(fresh.candidate_stage_plan.candidate_stage_state, "NOT_ASKED");
  assert.deepEqual(fresh.candidate_stage_plan.notes, {});
  assert.equal(fresh.blueprint.version, 1);
});

test("stage reads and writes follow the disabled target-service state", () => {
  const { mock, get } = setup();
  mock.setScenario({ targets: "disabled" });
  const path = `/api/v1/targets/${TARGET_IDS.target}/blueprint`;
  assert.equal(get(path).body.availability, "DISABLED");
  assert.equal(get(path).body.candidate_stage_plan, null);
  const result = mock.handle("PUT", `${path}/stages`, { body: {
    expected_blueprint_version: 1, state: "NOT_YET", order_known: false, stages: [], notes: {},
  } });
  assert.equal(result.status, 503);
});

test("default is the real India behaviour: one target, not yet researched, no claims", () => {
  const { get } = setup();
  const list = get("/api/v1/targets").body;
  assert.equal(list.availability, "AVAILABLE");
  assert.equal(list.targets[0].role_profile_id, ROLE);
  assert.equal(list.targets[0].geography_key, "in");
  const view = get(`/api/v1/targets/${TARGET_IDS.target}/blueprint`).body;
  assert.equal(view.match_state, "NOT_RESEARCHED");
  assert.deepEqual(view.claims, []);
  assert.ok(view.unknowns.some((u) => u.key === "amazon.sde.india_specific_process"));
  assert.deepEqual(view.rounds.map((r) => r.basis), ["MIRROR_SUGGESTED", "MIRROR_SUGGESTED", "MIRROR_SUGGESTED"]);
});

test("error and unavailable states are deliberate mocked answers, not unmocked 404s", () => {
  const { mock, get } = setup();
  const path = `/api/v1/targets/${TARGET_IDS.target}/blueprint`;
  assert.equal(mock.setScenario({ blueprint: "unavailable503" }).body.blueprint, "unavailable503");
  assert.equal(get(path).status, 503);
  mock.setScenario({ blueprint: "error500" });
  assert.equal(get(path).status, 500);
  mock.setScenario({ blueprint: "slow" });
  assert.equal(get(path).delayMs, 1500);
  mock.setScenario({ targets: "disabled" });
  assert.equal(get("/api/v1/targets").body.availability, "DISABLED");
  assert.equal(mock.handle("POST", "/api/v1/targets", { body: { role_profile_id: ROLE, company: "Amazon" } }).status, 503);
  assert.equal(mock.setScenario({ blueprint: "nope" }).status, 422);
  assert.equal(mock.setScenario({ unknown: "x" }).status, 422);
  mock.reset();
  assert.equal(get(path).status ?? 200, 200);
});

test("researched scenario carries a conflict side by side and a synthetic text only", () => {
  const { mock, get } = setup();
  mock.setScenario({ blueprint: "researched" });
  const target = get("/api/v1/targets").body.targets[0];
  assert.equal(target.company_label, "QA Fictional Company");
  assert.equal(target.geography_key, "qa_land");
  const view = get(`/api/v1/targets/${TARGET_IDS.target}/blueprint`).body;
  assert.equal(view.match_state, "RESEARCHED");
  assert.equal(view.conflicts[0].claims.length, 2);
  for (const claim of view.claims) {
    assert.match(claim.statement, /QA fixture/);
    for (const source of claim.sources) assert.match(source.url, /qa-fixture\.invalid/);
  }
});

test("synthetic research reaches its mapped round priority and prompt metadata without revealing text", () => {
  const { mock, get } = setup();
  mock.setScenario({ blueprint: "researched" });
  const blueprint = get(`/api/v1/targets/${TARGET_IDS.target}/blueprint`).body;
  assert.equal(blueprint.rounds[0].basis, "PUBLISHED_GUIDANCE");

  const path = `/api/v1/targets/${TARGET_IDS.target}/rounds/coding_reasoning`;
  const detail = get(path).body;
  assert.equal(detail.round.basis, "PUBLISHED_GUIDANCE");
  assert.ok(detail.priorities.some((priority) => priority.reason_codes.includes("IN_ONE_ROUND")));
  assert.ok(detail.pack.prompts.some((prompt) => prompt.rationale_code === "PUBLISHED_GUIDANCE_AREA"));
  assert.ok(detail.pack.prompts.every((prompt) => prompt.provenance_class === "MIRROR_GENERATED"));
  assert.ok(detail.pack.prompts.every((prompt) => !("text" in prompt)));

  const started = mock.handle("POST", `${path}/practice`, {
    body: { mode: "FOCUSED_PRACTICE", idempotency_key: "qa-researched-round" },
  });
  assert.equal(started.status, 201);
  assert.ok(started.body.prompts.some((prompt) => prompt.rationale_code === "PUBLISHED_GUIDANCE_AREA"));
  assert.ok(started.body.prompts.every((prompt) => !("text" in prompt)));
});

test("target uniqueness is scoped to the exact company, role family, level and place", () => {
  const { mock, get } = setup();
  const body = { role_profile_id: TARGET_IDS.newRole, company: "Amazon", role_family: "software_development_engineering", level: "sde_ii", geography: "in", geography_label: "India" };
  const created = mock.handle("POST", "/api/v1/targets", { body });
  assert.equal(created.status, 201);
  assert.equal(created.body.target.company_key, "amazon");
  assert.equal(created.body.target.level_key, "sde_ii");
  const otherCompany = mock.handle("POST", "/api/v1/targets", { body: { ...body, company: "Acme" } });
  assert.equal(otherCompany.status, 201, "one role may have multiple company targets");
  assert.notEqual(otherCompany.body.target.id, created.body.target.id);
  assert.equal(mock.handle("POST", "/api/v1/targets", { body }).status, 409, "the exact same target scope is unique");
  assert.equal(mock.handle("POST", "/api/v1/targets", { body: { ...body, geography: "global" } }).status, 422);
  assert.equal(mock.handle("POST", "/api/v1/targets", { body: { ...body, role_family: undefined } }).status, 422, "role family is required");
  assert.equal(mock.handle("POST", "/api/v1/targets", { body: { ...body, level: "consultant" } }).status, 422, "a level of another family is refused");
  assert.deepEqual(mock.state.targetCreates[0], body);
  assert.equal(get("/api/v1/targets").body.targets.length, 3);
});

test("business-roles slice: same routes and shapes, its own rounds, and no engineering round", () => {
  const { mock, sessions, get } = setup();
  mock.setScenario({ slice: "business_roles" });
  const target = get("/api/v1/targets").body.targets[0];
  assert.equal(target.role_family_key, "business_analysis");
  assert.equal(target.company_label, "QA Consulting Co (synthetic)");
  const engineering = fixture("blueprint_researched.json");
  const view = get(`/api/v1/targets/${TARGET_IDS.target}/blueprint`).body;
  assert.deepEqual(Object.keys(view).sort(), [...Object.keys(engineering), "candidate_stage_plan"].sort());
  assert.deepEqual(view.rounds.map((r) => r.key), ["business_problem_solving", "requirements_and_stakeholders", "behavioural"]);
  assert.equal(view.rounds[1].presence, "CONDITIONAL");
  assert.equal(get(`/api/v1/targets/${TARGET_IDS.target}/rounds/coding_reasoning`).status, 404);
  const plan = get("/api/v1/plan", new URL(`http://x/api/v1/plan?role_profile_id=${ROLE}`)).body;
  assert.equal(plan.role.target_role, "QA Business Analyst (test role)");
  assert.equal(plan.areas[0].theme, "Requirements gathering");
  assert.equal(plan.recommended_area_key, "qa_area_requirements");
  const map = get(`/api/v1/roles/${ROLE}/interview-map`).body;
  assert.equal(map.target_role, "QA Business Analyst (test role)");
  assert.deepEqual(map.preparation_areas.map((area) => area.title), ["Clarifying business requirements", "Working through a business problem"]);
  assert.ok(map.preparation_areas.every((area) => !/coding|system design/i.test(area.title)));
  const detail = get(`/api/v1/targets/${TARGET_IDS.target}/rounds/business_problem_solving`).body;
  assert.ok(detail.pack.prompts.every((p) => p.question_family === "case_discussion" && !("text" in p)));
  const started = mock.handle("POST", `/api/v1/targets/${TARGET_IDS.target}/rounds/business_problem_solving/practice`, {
    body: { mode: "FOCUSED_PRACTICE", idempotency_key: "qa-ba-1" },
  });
  assert.equal(started.status, 201);
  assert.equal(sessions[0].practice_theme, "Working through a business problem");
  assert.equal(sessions[0].qa_prompt_set, "qa_business_case");
  mock.setScenario({ slice: "engineering" });
  assert.equal(get("/api/v1/targets").body.targets[0].role_family_key, "software_development_engineering");
});

test("round practice creates one session per idempotency key, links it, and history counts it", () => {
  const { mock, sessions, get } = setup();
  const path = `/api/v1/targets/${TARGET_IDS.target}/rounds/coding_reasoning`;
  assert.equal(get(path).body.practice.count, 0);
  const body = { mode: "FOCUSED_PRACTICE", idempotency_key: "qa-key-1" };
  const first = mock.handle("POST", `${path}/practice`, { body });
  assert.equal(first.status, 201);
  assert.equal(first.body.prompts.length, 4);
  assert.ok(first.body.prompts.every((p) => !("text" in p)));
  assert.equal(sessions[0].role_profile_id, ROLE);
  assert.equal(sessions[0].practice_focus, "role");
  const replay = mock.handle("POST", `${path}/practice`, { body });
  assert.equal(replay.body.session.id, first.body.session.id);
  assert.equal(sessions.length, 1);
  assert.equal(mock.handle("POST", `/api/v1/targets/${TARGET_IDS.target}/rounds/system_design/practice`, { body }).status, 409);
  assert.equal(get(path).body.practice.count, 1);
  assert.equal(get(`/api/v1/targets/${TARGET_IDS.target}/rounds/system_design`).body.practice.count, 0);
});

test("short pack is reported on the round and refused at start, before any session", () => {
  const { mock, sessions, get } = setup();
  mock.setScenario({ pack: "short" });
  const path = `/api/v1/targets/${TARGET_IDS.target}/rounds/system_design`;
  assert.equal(get(path).body.pack.state, "SHORT_PACK");
  const refused = mock.handle("POST", `${path}/practice`, { body: { mode: "FOCUSED_PRACTICE", idempotency_key: "k" } });
  assert.equal(refused.status, 422);
  assert.equal(refused.body.detail.code, "SHORT_PACK");
  assert.equal(sessions.length, 0);
});

test("unknown rounds and targets are 404; plan follows the requested role", () => {
  const { get } = setup();
  assert.equal(get(`/api/v1/targets/${TARGET_IDS.target}/rounds/not_a_round`).status, 404);
  assert.equal(get("/api/v1/targets/00000000-0000-4000-8000-000000000999/blueprint").status, 404);
  const plan = get("/api/v1/plan", new URL(`http://x/api/v1/plan?role_profile_id=${TARGET_IDS.newRole}`)).body;
  assert.equal(plan.role.role_profile_id, TARGET_IDS.newRole);
  assert.equal(plan.state, "READY");
  assert.equal(get("/api/v1/plan").body.role.role_profile_id, ROLE);
});

test("the critical path runs the Loop 2 journeys before sign-out, and every allowed error names a real step", async () => {
  const path = fs.readFileSync(new URL("./critical-path.mjs", import.meta.url), "utf8");
  assert.ok(path.indexOf("runTargetJourneys({") > 0 && path.indexOf("runTargetJourneys({") < path.indexOf('step("sign-out"'));
  const journeys = fs.readFileSync(new URL("./target-journeys.mjs", import.meta.url), "utf8");
  const steps = [...journeys.matchAll(/step\("([a-z0-9-]+)"/g)].map((m) => m[1]);
  assert.ok(steps.length >= 18, `journey steps: ${steps.length}`);
  assert.ok(steps.includes("t16-onboarding-continues-with-general-plan-without-target"));
  assert.ok(steps.includes("t09b-researched-round-to-review"));
  assert.ok(steps.includes("t17-business-roles-plan"), "Loop 3 journey B runs on the same product system");
  assert.ok(steps.includes("t19-business-roles-practice-to-review"));
  assert.equal(new Set(steps).size, steps.length, "step names are unique");
  const { ALLOW } = await import("../lib/collector.mjs");
  for (const rule of ALLOW.filter((r) => r.steps?.some((s) => s.startsWith("t")))) {
    assert.ok(rule.reason && rule.steps.every((s) => steps.includes(s)), JSON.stringify(rule.steps));
  }
  assert.doesNotMatch(journeys, /__qa\/reset/, "journeys never wipe the Loop 1 evidence (unmocked calls, requests)");
});

test("server wires the Loop 2 routes, the scenario control and delayed answers", () => {
  const source = fs.readFileSync(new URL("../mock/server.mjs", import.meta.url), "utf8");
  assert.match(source, /createTargetsMock\(/);
  assert.match(source, /route\("POST", "\/__qa\/scenario"/);
  assert.match(source, /delayMs/);
  assert.match(source, /targets\.reset\(\)/);
  assert.match(source, /route\("POST", "\/__qa\/targets\/reset"/);
});
