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

test("creating a target records the body and a second target for the same role is a 409", () => {
  const { mock, get } = setup();
  const body = { role_profile_id: TARGET_IDS.newRole, company: "Amazon", level: "sde_ii", geography: "in", geography_label: "India" };
  const created = mock.handle("POST", "/api/v1/targets", { body });
  assert.equal(created.status, 201);
  assert.equal(created.body.target.company_key, "amazon");
  assert.equal(created.body.target.level_key, "sde_ii");
  assert.equal(mock.handle("POST", "/api/v1/targets", { body }).status, 409);
  assert.equal(mock.handle("POST", "/api/v1/targets", { body: { ...body, geography: "global" } }).status, 422);
  assert.deepEqual(mock.state.targetCreates[0], body);
  assert.equal(get("/api/v1/targets").body.targets.length, 2);
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
  assert.ok(steps.length >= 15, `journey steps: ${steps.length}`);
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
