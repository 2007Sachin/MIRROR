// Run: node --test apps/web/tests/target-recovery.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const { recoverTarget, activeTargetsForRole, selectTargetForRole, createRequestSequence } = await import(new URL("../src/lib/target-recovery.ts", import.meta.url).href);
const wanted = { role_profile_id: "r1", company: "Amazon", role_family: "software_development_engineering", level: "sde_ii", geography: "in", geography_label: "India" };
const view = (over = {}) => ({ id: "t1", role_profile_id: "r1", company_label: "Amazon", company_key: "amazon", role_family_key: "software_development_engineering", level_key: "sde_ii", geography_key: "in", geography_label: "India", status: "ACTIVE", ...over });

function api({ createError, listed = [], blueprintError, onCreate } = {}) {
  const calls = [];
  return { calls, create: async (body) => { calls.push(["create", body]); onCreate?.(); if (createError) throw createError; return { target: view() }; }, list: async () => { calls.push(["list"]); return { availability: "AVAILABLE", targets: listed }; }, blueprint: async (id) => { calls.push(["blueprint", id]); if (blueprintError) throw blueprintError; return { availability: "AVAILABLE" }; } };
}

test("a create failure recovers a persisted matching target by fetching its blueprint", async () => {
  const a = api({ createError: Error("409"), listed: [view()] });
  const result = await recoverTarget(wanted, a);
  assert.deepEqual(result, { kind: "READY", target: view() });
  assert.deepEqual(a.calls.map((x) => x[0]), ["create", "list", "blueprint"]);
});

test("does not recover an active target whose exact creation scope differs", async () => {
  const a = api({ createError: Error("offline"), listed: [view({ geography_key: "other" })] });
  assert.equal((await recoverTarget(wanted, a)).kind, "FAILED");
  assert.deepEqual(a.calls.map((x) => x[0]), ["create", "list"]);
});

test("does not recover a target of another role family for the same company and role", async () => {
  const a = api({ createError: Error("offline"), listed: [view({ role_family_key: "business_analysis" })] });
  assert.equal((await recoverTarget(wanted, a)).kind, "FAILED");
  const b = api({ createError: Error("offline"), listed: [view({ role_family_key: "business_analysis", level_key: "consultant" })] });
  assert.equal((await recoverTarget({ ...wanted, role_family: "business_analysis", level: "consultant" }, b)).kind, "READY");
});

test("create succeeds but blueprint pin failure is reported as retryable", async () => {
  const a = api({ blueprintError: Error("pin failed") });
  assert.equal((await recoverTarget(wanted, a)).kind, "FAILED");
  assert.deepEqual(a.calls.map((x) => x[0]), ["create", "blueprint", "list"]);
});

test("a create conflict followed by an unavailable list returns retryable failure", async () => {
  const a = api({ createError: Error("409") });
  a.list = async () => { a.calls.push(["list"]); throw Error("offline"); };
  assert.equal((await recoverTarget(wanted, a)).kind, "FAILED");
  assert.deepEqual(a.calls.map((x) => x[0]), ["create", "list"]);
});

test("matches a target only when geography and level both match", async () => {
  const a = api({ createError: Error("409"), listed: [view({ level_key: "sde_iii" }), view({ geography_key: "other" }), view()] });
  assert.equal((await recoverTarget(wanted, a)).kind, "READY");
  assert.deepEqual(a.calls.map((x) => x[0]), ["create", "list", "blueprint"]);
});

test("retry after persisted target and pin failure recovers with one idempotent conflict", async () => {
  const first = api({ createError: Error("409"), listed: [view()], blueprintError: Error("pin failed") });
  assert.equal((await recoverTarget(wanted, first)).kind, "FAILED");
  const retry = api({ createError: Error("409"), listed: [view()] });
  assert.equal((await recoverTarget(wanted, retry)).kind, "READY");
  assert.deepEqual(retry.calls.map((x) => x[0]), ["create", "list", "blueprint"]);
});

test("role step Retry button invokes target recovery without submitting role analysis", async () => {
  const source = await readFile(new URL("../src/components/onboarding/role-step.tsx", import.meta.url), "utf8");
  const retry = source.split("\n").find((line) => line.includes("{t.retryTarget}"));
  assert.ok(retry, "retry CTA should exist");
  assert.match(retry, /onClick=\{\(\)\s*=>\s*pending\s*&&\s*finishTargetSetup\(pending\)\}/,
    "Retry must call target recovery directly using saved pending state");
  assert.doesNotMatch(retry, /type="submit"/, "Retry must not submit the form and re-run role analysis");
});

test("continuing without a target explains the general plan and missing company rounds", async () => {
  const { onboardingCopy } = await import(new URL("../src/lib/copy-onboarding.ts", import.meta.url).href);
  const message = onboardingCopy.role.targetSetupError;
  assert.match(message, /general role plan/i);
  assert.match(message, /company-specific interview rounds/i);
  assert.match(message, /won't (be included|appear|include)|unavailable/i);
  assert.doesNotMatch(message, /add it later from this step/i);
  assert.match(onboardingCopy.role.continueWithoutTarget, /general role plan/i);
});

test("role target choices retain all active matches and exclude archived or other-role targets", () => {
  const first = view({ id: "t1" });
  const second = view({ id: "t2", company_label: "Acme" });
  const archived = view({ id: "t3", status: "ARCHIVED" });
  const otherRole = view({ id: "t4", role_profile_id: "r2" });
  assert.deepEqual(activeTargetsForRole([first, second, archived, otherRole], "r1"), [first, second]);
});

test("a requested target must be an active target for the exact role", () => {
  const first = view({ id: "t1" });
  const archived = view({ id: "t3", status: "ARCHIVED" });
  const otherRole = view({ id: "t4", role_profile_id: "r2" });
  assert.equal(selectTargetForRole([first, archived, otherRole], "r1", "t1"), first);
  assert.equal(selectTargetForRole([first, archived, otherRole], "r1", "t3"), null);
  assert.equal(selectTargetForRole([first, archived, otherRole], "r1", "t4"), null);
  assert.equal(selectTargetForRole([first], "r1", "stale-id"), null);
});

test("an invalid target query does not silently choose another company", () => {
  const first = view({ id: "t1" });
  const second = view({ id: "t2", company_label: "Acme" });
  assert.equal(selectTargetForRole([first], "r1"), first);
  assert.equal(selectTargetForRole([first, second], "r1"), null);
  assert.equal(selectTargetForRole([first, second], "r1", "old-target"), null);
});

test("a newer target load invalidates every older asynchronous response", () => {
  const requests = createRequestSequence();
  const targetB = requests.next();
  const targetC = requests.next();
  assert.equal(requests.isCurrent(targetB), false);
  assert.equal(requests.isCurrent(targetC), true);
});

test("target overview applies the latest-request guard to list and blueprint responses", async () => {
  const source = await readFile(new URL("../src/components/plan/target-overview.tsx", import.meta.url), "utf8");
  assert.match(source, /const requestId = requestSequence\.current\.next\(\)/);
  assert.match(source, /requestSequence\.current\.isCurrent\(requestId\) && isCurrent\(\)/);
  assert.match(source, /await loadTarget\(target, current\)/);
});

test("PlanReady hides the optional stage prompt when no active target exists", async () => {
  const source = await readFile(new URL("../src/components/onboarding/plan-ready-step.tsx", import.meta.url), "utf8");
  assert.match(source, /if \(listState === "none"\) return null;/);
  assert.doesNotMatch(source, /stageCopy\.noTarget/);
});

test("dirty stage drafts cancel history traversals before they leave the current entry when Navigation API is available", async () => {
  const source = await readFile(new URL("../src/components/plan/candidate-stage-plan-editor.tsx", import.meta.url), "utf8");
  assert.match(source, /if \(navigation\)/);
  assert.match(source, /navigation\?\.addEventListener\("navigate"/);
  assert.match(source, /navigationEvent\.navigationType === "traverse"/);
  assert.match(source, /event\.preventDefault\(\)/);
  assert.match(source, /addEventListener\("popstate"/);
});
