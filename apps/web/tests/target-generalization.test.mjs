// Loop 3: one product system for every role family. Words are keyed by backend keys, never by company.
// Run: node --test apps/web/tests/target-generalization.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

const m = await import(new URL("../src/lib/copy-targets.ts", import.meta.url).href);

test("each role family Mirror offers has its own levels, always ending with Not sure yet", () => {
  const families = m.ROLE_FAMILIES;
  assert.deepEqual(families.map((family) => family.key), ["software_development_engineering", "business_analysis"]);
  for (const family of families) {
    assert.ok(m.familyLabel(family.key), family.key);
    assert.equal(family.levels.at(-1), "not_sure");
    for (const level of m.familyLevels(family.key)) assert.ok(level.label && level.label !== level.key, level.key);
  }
  assert.deepEqual(m.familyLevels("business_analysis").map((level) => level.key), ["analyst", "consultant", "senior_consultant", "manager", "not_sure"]);
  assert.deepEqual(m.familyLevels("unknown_family"), []);
});

test("a role title only hints at a family; anything else gets no family", () => {
  assert.equal(m.familyHint("Software Development Engineer II"), "software_development_engineering");
  assert.equal(m.familyHint("Business Analyst – Consulting"), "business_analysis");
  assert.equal(m.familyHint("Product Designer"), null);
});

test("business-analysis rounds and competencies have their own words, not engineering words", () => {
  for (const key of ["business_problem_solving", "requirements_and_stakeholders"]) {
    const words = `${m.roundLabel(key)} ${m.roundCovers(key)} ${m.cannotDo(key)}`;
    assert.ok(m.roundLabel(key) && m.roundCovers(key) && m.cannotDo(key), key);
    assert.doesNotMatch(words, /cod(e|ing)|system design|whiteboard|algorithm/i, key);
  }
  for (const key of ["structured_problem_solving", "quantitative_reasoning", "business_judgement", "requirements_analysis", "stakeholder_communication"]) {
    assert.ok(m.competencyLabel(key), key);
  }
});

test("what Mirror can't do is chosen by round key alone; no company changes it", () => {
  assert.equal(m.cannotDo.length, 1);
  assert.match(m.cannotDo("coding_reasoning"), /online coding round/);
  assert.equal(m.cannotDo("unknown_round"), null);
});

test("the target line uses the family's level words", () => {
  const target = {
    id: "t", role_profile_id: "r", company_label: "QA Consulting Co (synthetic)", company_key: "qa_consulting",
    role_family_key: "business_analysis", level_key: "consultant", geography_key: "qa_land",
    geography_label: "QA Fictional Country", interview_date: null, status: "ACTIVE", archived_at: null, created_at: "2026-10-07T00:00:00Z",
  };
  assert.equal(m.targetLine(target), "QA Consulting Co (synthetic) · QA Fictional Country · Consultant");
});
