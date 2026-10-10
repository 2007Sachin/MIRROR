// Loop 5A stage-to-practice mapping. Run: node --test apps/web/tests/candidate-stage-plan.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

const { candidateStageRoundKeys, candidateStageRoundGroups } = await import(new URL("../src/lib/copy-targets.ts", import.meta.url).href);

const engineering = "software_development_engineering";
const business = "business_analysis";

test("candidate-reported stage kinds map only to the approved existing role rounds", () => {
  const cases = [
    ["RECRUITER_SCREENING", [], []],
    ["TECHNICAL_INTERVIEW", ["coding_reasoning", "system_design"], ["requirements_and_stakeholders"]],
    ["CODING_EXERCISE", ["coding_reasoning"], []],
    ["CASE_INTERVIEW", [], ["business_problem_solving"]],
    ["BEHAVIORAL_INTERVIEW", ["behavioural"], ["behavioural"]],
    ["HIRING_MANAGER_DISCUSSION", ["behavioural"], ["requirements_and_stakeholders", "behavioural"]],
    ["PORTFOLIO_PROJECT_DISCUSSION", ["system_design", "behavioural"], ["requirements_and_stakeholders", "behavioural"]],
    ["OTHER", [], []],
  ];
  for (const [kind, engineeringRounds, businessRounds] of cases) {
    assert.deepEqual(candidateStageRoundKeys(engineering, kind), engineeringRounds, `engineering/${kind}`);
    assert.deepEqual(candidateStageRoundKeys(business, kind), businessRounds, `business/${kind}`);
  }
});

test("unsupported stage and role-family keys fail closed to general role practice", () => {
  assert.deepEqual(candidateStageRoundKeys("unmapped_family", "TECHNICAL_INTERVIEW"), []);
  assert.deepEqual(candidateStageRoundKeys(engineering, "UNRECOGNIZED_STAGE"), []);
  assert.deepEqual(candidateStageRoundKeys(null, "CASE_INTERVIEW"), []);
});

test("stages that share a round appear once and retain their own candidate labels", () => {
  const technical = { stage_id: "stage-technical", kind: "TECHNICAL_INTERVIEW", custom_label: null, certainty: "UNCERTAIN", sequence: 1 };
  const coding = { stage_id: "stage-coding", kind: "CODING_EXERCISE", custom_label: null, certainty: "SURE", sequence: 2 };
  const groups = candidateStageRoundGroups(engineering, [technical, coding], ["coding_reasoning", "system_design"]);
  assert.deepEqual(groups.map((group) => [group.roundKey, group.stages.map((stage) => stage.stage_id)]), [
    ["coding_reasoning", ["stage-technical", "stage-coding"]],
    ["system_design", ["stage-technical"]],
  ]);
});

test("a stage mapping fails closed as a whole when its pinned taxonomy lacks any mapped round", () => {
  const technical = { stage_id: "stage-technical", kind: "TECHNICAL_INTERVIEW", custom_label: null, certainty: "SURE", sequence: null };
  const coding = { stage_id: "stage-coding", kind: "CODING_EXERCISE", custom_label: null, certainty: "SURE", sequence: null };
  const groups = candidateStageRoundGroups(engineering, [technical, coding], ["coding_reasoning"]);
  assert.deepEqual(groups.map((group) => [group.roundKey, group.stages.map((stage) => stage.stage_id)]), [
    ["coding_reasoning", ["stage-coding"]],
  ]);
});
