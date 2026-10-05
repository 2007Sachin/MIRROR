// Pure tests for the interview-target copy and view helpers (Node 24 strips TypeScript types).
// Run: node --test apps/web/tests/target-copy.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

const m = await import(new URL("../src/lib/copy-targets.ts", import.meta.url).href);

const target = (over = {}) => ({
  id: "t1", role_profile_id: "r1", company_label: "Amazon", company_key: "amazon",
  role_family_key: "software_development_engineering", level_key: "not_sure",
  geography_key: "in", geography_label: "India", interview_date: null, status: "ACTIVE",
  archived_at: null, created_at: "2026-10-04T00:00:00Z", ...over,
});

test("the target line names company, country and level, and never guesses a level", () => {
  assert.equal(m.targetLine(target()), "Amazon · India · Level not set yet");
  assert.equal(m.targetLine(target({ level_key: "sde_ii" })), "Amazon · India · SDE II");
  assert.equal(m.targetLine(target({ geography_key: null, geography_label: null })), "Amazon · Country not set yet · Level not set yet");
});

test("an India target is 'not yet researched'; an unknown company is 'no notes yet'", () => {
  const india = { availability: "AVAILABLE", target: target(), content_state: "SERVED", match_state: "NOT_RESEARCHED" };
  assert.equal(m.researchState(india), "NOT_YET_RESEARCHED");
  const other = { ...india, target: target({ company_key: null, company_label: "Acme" }) };
  assert.equal(m.researchState(other), "NO_NOTES_FOR_COMPANY");
  assert.equal(m.researchState({ ...india, match_state: "RESEARCHED" }), "RESEARCHED");
  assert.equal(m.researchState({ ...india, content_state: "PIN_MISMATCH", match_state: null }), "UNAVAILABLE");
  assert.equal(m.researchState({ availability: "DISABLED" }), "UNAVAILABLE");
  assert.equal(m.researchState({ availability: "UNAVAILABLE" }), "UNAVAILABLE");
});

test("other and missing geographies use where you're applying", () => {
  assert.equal(m.countryLabel(target({ geography_key: "other", geography_label: "Other" })), null);
  assert.equal(m.countryLabel(target({ geography_key: null, geography_label: null })), null);
  assert.match(m.targetCopy.section.notYetResearched("Amazon", null), /where you're applying/);
});

test("headings and priority reasons identify Mirror's practice scope", () => {
  assert.equal(m.targetCopy.section.title, "Your interview target");
  assert.match(m.targetCopy.section.loading, /interview target/i);
  assert.match(m.targetCopy.section.unavailable, /interview target/i);
  assert.match(m.targetCopy.round.coversTitle, /Mirror practice/i);
  assert.match(m.targetCopy.round.publishedGuidanceTitle, /published guidance/i);
  assert.match(m.reasonLabel("IN_MANY_ROUNDS"), /practice round in Mirror/i);
  assert.match(m.reasonLabel("IN_ONE_ROUND"), /practice round in Mirror/i);
});

test("practice round overview shows themes without exposing prompt wording", () => {
  assert.equal(m.targetCopy.round.themesTitle, "Practice themes");
  assert.match(m.targetCopy.round.themesLabel, /Exact wording appears only during that practice/);
  assert.equal("questionsTitle" in m.targetCopy.round, false);
});

test("practice focus explicitly labels the Mirror round", () => {
  assert.equal(m.targetCopy.practice.roundFocus("Coding conversation", "Amazon · India · SDE II"), "Mirror practice round: Coding conversation — for Amazon · India · SDE II");
});

test("404, 501 and 503 are treated as unavailable, anything else is an error", () => {
  for (const status of [404, 501, 503]) assert.equal(m.failureKind(status), "UNAVAILABLE");
  for (const status of [0, 500, 400]) assert.equal(m.failureKind(status), "ERROR");
});

test("every round, competency and reason code has words; unknown keys fall back quietly", () => {
  for (const key of ["coding_reasoning", "system_design", "behavioural"]) assert.ok(m.roundLabel(`round.${key}`).length > 3);
  assert.equal(m.roundLabel("round.unknown_thing"), null);
  for (const key of ["algorithmic_problem_solving", "coding_quality", "technical_communication", "system_design", "behavioural_examples"]) {
    assert.ok(m.competencyLabel(key));
  }
  for (const code of ["IN_MANY_ROUNDS", "IN_ONE_ROUND", "NO_CONFIRMED_EXAMPLE", "SOME_EXAMPLES", "NOT_LINKED_TO_YOUR_PLAN", "NOT_PRACTISED_YET", "PRACTISED_RECENTLY", "INTERVIEW_SOON"]) {
    assert.ok(m.reasonLabel(code), code);
  }
});

test("claims are renderable only when every published scope dimension matches the target", () => {
  const claim = { scope: { company: "amazon", role_family: "software_development_engineering", level: "sde_ii", geography: "global" } };
  const indiaTarget = target({ level_key: "sde_ii" });
  assert.equal(m.claimMatchesTargetScope(claim, indiaTarget), false, "global claims are not India guidance");
  assert.equal(m.claimMatchesTargetScope({ ...claim, scope: { ...claim.scope, geography: "in" } }, indiaTarget), true);
  assert.equal(m.claimMatchesTargetScope({ ...claim, scope: { ...claim.scope, company: "qa_company", geography: "qa_land" } }, target({ company_key: "qa_company", geography_key: "qa_land", level_key: "sde_ii" })), true);
  assert.equal(m.claimMatchesTargetScope({ ...claim, scope: { ...claim.scope, company: "other", geography: "in" } }, target()), false);
  assert.equal(m.claimMatchesTargetScope({ ...claim, scope: { ...claim.scope, level: "sde_iii", geography: "in" } }, target()), false);
});

 test("catalog claims render only through mapped copy, never raw catalog text", () => {
  assert.equal(m.claimCopy("amazon.sde.not_a_real_claim", 1), null);
  const oa = m.claimCopy("amazon.sde.sde_ii.oa_components", 1);
  assert.match(oa, /online coding round/);
  assert.doesNotMatch(oa, /assessment/i);
});

test("OA requirement quotes the supported eligibility wording and separates the window", () => {
  const copy = m.claimCopy("amazon.sde.sde_ii.oa_required", 1);
  assert.match(copy, /“everyone who wants to work as an SDE II at Amazon must complete an OA”/);
  assert.match(copy, /seven days/);
  assert.doesNotMatch(copy, /assessment|test/i);
});

test("coding guidance keeps the source meaning in banned-word-safe wording", () => {
  assert.match(m.claimCopy("amazon.sde.sde_ii.coding_expectations", 1), /carefully checked/);
  assert.doesNotMatch(m.claimCopy("amazon.sde.sde_ii.coding_expectations", 1), /well-tested/i);
});

test("current online coding round reports are explicitly unverified", () => {
  assert.match(m.unknownCopy("amazon.sde.sde_ii.current_oa_format"), /unverified/i);
});

test("claim copy binds both identifier and version", () => {
  assert.match(m.claimCopy("amazon.sde.sde_ii.oa_components", 1), /90-minute/);
  assert.equal(m.claimCopy("amazon.sde.sde_ii.oa_components", 2), null);
  assert.equal(m.claimCopy("amazon.sde.sde_ii.oa_components", 0), null);
});

test("C2 sequence has distinct overview and system-design copy contexts", () => {
  const id = "amazon.sde.sde_ii.process_sequence";
  assert.match(m.claimCopy(id, 1), /loop of four interviews/);
  assert.match(m.claimCopy(id, 1, "system_design"), /at least one software systems design question/);
  assert.doesNotMatch(m.claimCopy(id, 1, "system_design"), /loop of four interviews|outcome/);
  assert.equal(m.claimCopy(id, 2, "system_design"), null);
});

test("a source label is text: who published it, for where, for which level, and how it is dated", () => {
  const claim = {
    provenance_class: "FACT", scope: { geography: "in", level: "sde_ii" }, dating: "RETRIEVED_ONLY",
    retrieved_at: "2026-10-04", published_at: null,
  };
  assert.equal(m.sourceLabel(claim, "Amazon"), "From Amazon's published guidance for India · for SDE II · checked 4 Oct 2026 · publication date not shown");
  const allLevels = { ...claim, scope: { geography: "in", level: "all" }, published_at: "2026-09-01", dating: "PUBLISHED" };
  assert.equal(m.sourceLabel(allLevels, "Amazon"), "From Amazon's published guidance for India · for all levels · checked 4 Oct 2026");
});

test("round practice goes to the existing practice start with the round, target and role pinned", () => {
  const href = m.roundPracticeHref({ roleName: "Software Development Engineer", roleProfileId: "r1", targetId: "t1", roundKey: "coding_reasoning" });
  const url = new URL(href, "http://x");
  assert.equal(url.pathname, "/practice/start");
  assert.equal(url.searchParams.get("role_profile_id"), "r1");
  assert.equal(url.searchParams.get("target"), "t1");
  assert.equal(url.searchParams.get("round"), "coding_reasoning");
  assert.equal(url.searchParams.get("mode"), "FOCUSED_PRACTICE");
  assert.equal(url.searchParams.get("focus"), "role");
});

test("plan and round links always carry the role", () => {
  assert.equal(m.planHref("r 1"), "/plan?role=r%201");
  assert.equal(m.roundHref("r1", "system_design"), "/plan/rounds/system_design?role=r1");
});

test("the copy itself passes the banned-word list", () => {
  const banned = /\b(evidence|diagnostics?|assessments?|assessor|skeptic|scor(e|ed|es|ing)|weakness(es)?|gaps?|deficienc(y|ies)|fail(s|ed|ure|ing)?|incorrect|wrong|red flag|critical|candidates?|verdicts?|evaluat\w*|analys\w*|audit\w*|test(s|ed|ing)?|verif\w*|proof|performance|scrutiny|substantiat\w*|flag(s|ged)?)\b/i;
  const strings = [];
  const walk = (value) => {
    if (typeof value === "string") strings.push(value);
    else if (value && typeof value === "object") Object.values(value).forEach(walk);
  };
  walk(m.targetCopy);
  assert.ok(strings.length > 40);
  for (const text of strings) assert.doesNotMatch(text, banned, text);
});
