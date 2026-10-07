// Loop 2 browser journeys (T1–T16, with synthetic researched cases T3b and T9b, adapted to what was built),
// plus Loop 3 journey B (T17–T20): a synthetic business-roles target on the same product system.
// Runs inside critical-path.mjs's runViewport, after the Loop 1 path and before sign-out, against the
// fake Auth/API (mock/targets.mjs scenarios). Every step also checks: no banned word on screen, one
// <h1>, at most the expected number of filled primary actions, named controls, and (mobile) no horizontal scroll.
// Not built, so not tested here: the T5 level edit form, T14's "make this my current role" note, and the proposal's switcher-label scenario (there is no backend contract for it).
import assert from "node:assert/strict";

import { IDS } from "../mock/server.mjs";
import { QA_BUSINESS_CASE_PROMPTS, QA_RESEARCHED_CODING_PROMPTS, TARGET_IDS } from "../mock/targets.mjs";

// Same list as docs/copy-guide.md (whole word, case-insensitive, inflections).
const BANNED = /\b(evidence|diagnostics?|assessments?|assessor|skeptic|scor(e|ed|es|ing)|weakness(es)?|gaps?|deficienc(y|ies)|fail(s|ed|ure|ing)?|incorrect|wrong|red flag|critical|candidates?|verdicts?|evaluat\w*|analys\w*|audit\w*|test(s|ed|ing)?|verif\w*|proof|performance|scrutiny|substantiat\w*|flag(s|ged)?)\b/i;
// Fixture names that are deliberately marked as test data. The whole marked name goes, not just the
// marker: the Loop 1 fixture role "QA Analyst (test role)" is user data shown in the role switcher.
const FIXTURE_TEXT = [/QA Analyst \(test role\)/g, /QA Business Analyst \(test role\)/g, /\(test role\)/g, /\(test only\)/g, /QA fixture[^.]*\./g];

export async function runTargetJourneys({ page, step, baseUrl, mock, viewport, overflow, getState, poll }) {
  const control = { "x-qa-control-token": mock.controlToken, "content-type": "application/json" };
  const scenario = async (body) => {
    const response = await fetch(`${mock.apiUrl}/__qa/scenario`, { method: "POST", headers: control, body: JSON.stringify(body), redirect: "error" });
    assert.equal(response.status, 200, `scenario ${JSON.stringify(body)}`);
  };
  // Resets only the Loop 2 mock state, so unmocked calls and requests recorded earlier stay visible.
  const reset = async () => {
    const response = await fetch(`${mock.apiUrl}/__qa/targets/reset`, { method: "POST", headers: control, redirect: "error" });
    assert.equal(response.status, 200);
  };
  const heading = (name, level) => page.getByRole("heading", { name, ...(level ? { level } : {}) });
  const joinWithTyping = async () => {
    await page.getByRole("button", { name: "Check microphone" }).click();
    await page.getByText("Microphone blocked").waitFor();
    await page.getByRole("button", { name: "Continue with typing" }).click();
    await page.locator("#typed-answer").waitFor();
  };
  const planUrl = (role) => `${baseUrl}/plan?role=${role}`;
  // The target section's structure (headings and round count), to compare role families side by side.
  const planStructure = () => page.evaluate(() => {
    const run = document.querySelector(".pl-run");
    return {
      headings: [...(run?.querySelectorAll("h2, h3") ?? [])].map((el) => el.tagName),
      rounds: run?.querySelectorAll(".pl-rounds > li").length ?? 0,
      labels: [...(run?.querySelectorAll(".pl-rounds > li > a") ?? [])].map((el) => el.textContent.trim()),
    };
  });
  let engineeringPlan = null;

  /** Shared checks for every Loop 2 screen. */
  async function screen(label, { primaries = 1 } = {}) {
    const facts = await page.evaluate(() => {
      const visible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
      const filled = [...document.querySelectorAll(".dh-primary-action:not(.is-quiet), .button-primary")].filter(visible).length;
      const unnamed = [...document.querySelectorAll("main a, main button, .dh a, .dh button")]
        .filter(visible)
        .filter((el) => !(el.getAttribute("aria-label") || el.textContent || "").trim())
        .map((el) => el.outerHTML.slice(0, 80));
      return { text: document.body.innerText, h1: document.querySelectorAll("h1").length, filled, unnamed };
    });
    let text = facts.text;
    for (const pattern of FIXTURE_TEXT) text = text.replace(pattern, "");
    const hit = BANNED.exec(text);
    assert.equal(hit, null, `banned word on ${label}: "${hit?.[0]}" in …${text.slice(Math.max(0, (hit?.index ?? 0) - 40), (hit?.index ?? 0) + 40)}…`);
    assert.equal(facts.h1, 1, `${label}: exactly one h1`);
    assert.ok(facts.filled <= primaries, `${label}: ${facts.filled} filled primary actions (max ${primaries})`);
    if (primaries === 1) assert.equal(facts.filled, 1, `${label}: one filled primary action`);
    assert.deepEqual(facts.unnamed, [], `${label}: every link and button has a name`);
    await overflow(label);
  }

  // T1 Role step: optional where-and-what-level, keyboard level choice, target created after analysis.
  await step("t01-role-step-target-fields", async () => {
    await reset();
    await page.goto(`${baseUrl}/roles/new`);
    await heading("What role are you preparing for?", 1).waitFor();
    await page.getByLabel("Role", { exact: true }).fill("Software Development Engineer (test role)");
    const details = page.locator("details.ob-target");
    await details.waitFor();
    await page.waitForFunction(() => document.querySelector("details.ob-target")?.open === true);
    await page.getByLabel("Company").fill("Amazon");
    assert.equal(await page.getByRole("radio", { name: "Software development (SDE)" }).isChecked(), true, "the role title hints at the family");
    const notSure = page.getByRole("radio", { name: "Not sure yet" }).first();
    assert.equal(await notSure.isChecked(), true, "level defaults to Not sure yet");
    await notSure.focus();
    await page.keyboard.press("ArrowUp");
    await page.keyboard.press("ArrowUp");
    assert.equal(await page.getByRole("radio", { name: "SDE II", exact: true }).isChecked(), true, "keyboard reaches SDE II");
    await page.getByRole("radio", { name: "India" }).check();
    await page.getByRole("button", { name: "Skip for now" }).click();
    await screen("role-step-target", { primaries: 1 });
    await page.getByRole("button", { name: /Continue/ }).click();
    await heading(/preparation plan is ready/, 1).waitFor();
    const state = await getState();
    assert.deepEqual(state.targets.creates, [{
      role_profile_id: TARGET_IDS.newRole, company: "Amazon", role_family: "software_development_engineering",
      level: "sde_ii", geography: "in", geography_label: "India",
    }]);
    assert.equal(state.targets.analyze.length, 1);
  });

  // T2 Plan ready: one primary to the plan, a text link to practise, no "explore".
  await step("t02-plan-ready-exits-to-plan", async () => {
    await page.getByRole("button", { name: "See your plan" }).waitFor();
    await page.getByRole("button", { name: "Start a short practice instead" }).waitFor();
    assert.equal(await page.getByText("Explore my workspace").count(), 0);
    await screen("plan-ready", { primaries: 1 });
    await page.getByRole("button", { name: "See your plan" }).click();
    await page.waitForURL((url) => url.pathname === "/plan" && url.searchParams.get("role") === TARGET_IDS.newRole);
  });

  // T3 India target: not yet researched, Mirror's suggested rounds, no global guidance, one primary.
  await step("t03-plan-india-not-yet-researched", async () => {
    await heading("Your interview target", 2).waitFor();
    await page.getByText("Amazon · India · SDE II").waitFor();
    await page.getByText("Not yet researched", { exact: true }).waitFor();
    const order = await page.locator("h2").allInnerTexts();
    assert.ok(order.indexOf("Your interview target") < order.indexOf("What this role looks for"), "section A above the plan");
    assert.equal(await page.locator(".pl-rounds > li").count(), 3);
    assert.equal(await page.locator(".pl-rounds .pl-source", { hasText: "Mirror's suggestion" }).count(), 3);
    assert.equal(await page.locator(".pl-stages").count(), 0, "no published-guidance list for India");
    assert.equal(await page.getByText(/Amazon describes|published guidance for India/).count(), 0);
    await page.getByText(/won't borrow guidance written for other countries/).first().waitFor();
    await page.getByRole("link", { name: /Practise the coding conversation/ }).waitFor();
    await screen("plan-not-researched", { primaries: 1 });
  });

  // T3b Synthetic researched fixture: the target and claim scope are fictional, so no company claim copy is renderable.
  await step("t03b-plan-researched-fixture", async () => {
    await scenario({ blueprint: "researched" });
    await page.goto(planUrl(IDS.role));
    await page.getByText("QA Fictional Company · QA Fictional Country · SDE II").waitFor();
    await page.getByText("From published guidance for where you're applying.").waitFor();
    assert.equal(await page.locator(".pl-stages").count(), 0, "unmapped synthetic claim ids are not rendered as real company claims");
    assert.equal(await page.locator(".pl-conflict").count(), 0, "synthetic conflict ids do not resolve to company copy");
    assert.equal(await page.getByText(/Amazon|India/).count(), 0, "fictional researched fixture does not impersonate a real scope");
    await screen("plan-researched", { primaries: 1 });
    engineeringPlan = await planStructure();
  });

  // T4 Loading stays inside the section; the plan below is already there.
  await step("t04-plan-section-loading", async () => {
    await scenario({ blueprint: "slow" });
    await page.goto(planUrl(IDS.role));
    await page.locator(".pl-areas .pl-card").first().waitFor();
    await page.locator(".pl-run[aria-busy='true']").waitFor();
    await page.locator(".pl-rounds").waitFor({ timeout: 10_000 });
  });

  // T5 (adapted) Level not chosen: the target line says so; no level is guessed.
  await step("t05-plan-level-not-set", async () => {
    await scenario({ blueprint: "not_researched" });
    await page.goto(planUrl(IDS.role));
    await page.getByText("Amazon · India · Level not set yet").waitFor();
  });

  // T6 Unavailable (503): one quiet line and Try again; plan areas render; no alert.
  await step("t06-plan-section-unavailable", async () => {
    await scenario({ blueprint: "unavailable503" });
    await page.goto(planUrl(IDS.role));
    await page.getByText("Your interview target isn't available right now. Your plan below still works.").waitFor();
    await page.locator(".pl-run").getByRole("button", { name: "Try again" }).waitFor();
    await page.locator(".pl-areas .pl-card").first().waitFor();
    assert.equal(await page.locator(".dh").getByRole("alert").count(), 0, "no alert in the page content");
    await screen("plan-unavailable", { primaries: 1 });
  });

  // T7 Error (500): alert scoped to the section; retry recovers.
  await step("t07-plan-section-error-and-retry", async () => {
    await scenario({ blueprint: "error500" });
    await page.goto(planUrl(IDS.role));
    const alert = page.locator(".pl-run [role='alert']");
    await alert.getByText("This part didn't load. Nothing is lost.").waitFor();
    await page.locator(".pl-areas .pl-card").first().waitFor();
    await scenario({ blueprint: "not_researched" });
    await alert.getByRole("button", { name: "Try again" }).click();
    await page.locator(".pl-rounds").waitFor();
  });

  // T8 Company without notes / targets switched off: quiet line / no section; plan unchanged.
  await step("t08-plan-no-notes-and-disabled", async () => {
    await scenario({ blueprint: "no_notes" });
    await page.goto(planUrl(IDS.role));
    await page.getByText(/doesn't have interview notes for QA Company/).waitFor();
    await scenario({ blueprint: "not_researched", targets: "disabled" });
    await page.goto(planUrl(IDS.role));
    await page.locator(".pl-areas .pl-card").first().waitFor();
    await page.waitForLoadState("networkidle"); // the target list has answered; the section stays away
    assert.equal(await page.locator(".pl-run").count(), 0, "no target section when targets are off");
    await screen("plan-targets-off", { primaries: 1 });
    await scenario({ targets: "available" });
  });

  // T9 Round page: focus on h1, boundary note, Mirror-written label, priorities, My plan active.
  await step("t09-round-detail", async () => {
    await page.goto(planUrl(IDS.role));
    await page.locator(".pl-rounds").getByRole("link", { name: /Coding conversation/ }).click();
    await page.waitForURL((url) => url.pathname === "/plan/rounds/coding_reasoning" && url.searchParams.get("role") === IDS.role);
    await heading("Coding conversation", 1).waitFor();
    await page.waitForFunction(() => document.activeElement?.tagName === "H1");
    await heading("What Mirror can and can't do here", 2).waitFor();
    await page.getByRole("heading", { name: "Practice themes" }).waitFor();
    await page.getByText("Exact wording appears only during that practice.").waitFor();
    assert.equal(await page.getByText(/Status updates for parcels can arrive late/).count(), 0, "exact prompt text is withheld from the plan");
    assert.ok((await page.locator("[aria-labelledby='round-priorities'] li").count()) <= 3);
    if (viewport.name === "desktop") {
      await page.locator(".ws-nav-item[aria-current='page']", { hasText: "My plan" }).waitFor();
    }
    await screen("round-detail", { primaries: 1 });
  });

  // T9b The fictional researched round reaches practice metadata and the existing interview/review flow.
  await step("t09b-researched-round-to-review", async () => {
    await scenario({ blueprint: "researched", targets: "available", pack: "full" });
    const stateBefore = await getState();
    const answersBefore = stateBefore.answers.length;
    const genericStartsBefore = stateBefore.createBodies.length;

    await page.goto(`${baseUrl}/plan/rounds/coding_reasoning?role=${IDS.role}`);
    await heading("Coding conversation", 1).waitFor();
    await page.getByText("QA Fictional Company · QA Fictional Country · SDE II").waitFor();
    await page.getByText("Published guidance is linked to this practice round, but Mirror has no reviewed summary to show here. Mirror's practice questions are original.").waitFor();
    // Every competency of a researched round carries the research-derived reason (fixture generated by the real service).
    const researchedPriorities = page.locator("[aria-labelledby='round-priorities'] li");
    await researchedPriorities.first().waitFor();
    assert.equal(
      await researchedPriorities.filter({ hasText: "Part of one practice round in Mirror" }).count(),
      await researchedPriorities.count(),
    );
    await page.getByText("Mirror chooses original prompts when you start. Exact wording appears only during that practice.").waitFor();
    assert.equal(await page.getByText(/Amazon|India/).count(), 0, "fictional research does not borrow a real-company or India claim");
    for (const prompt of QA_RESEARCHED_CODING_PROMPTS) {
      assert.equal(await page.getByText(prompt.text, { exact: true }).count(), 0, "question wording stays hidden on the round page");
    }
    await screen("fictional-researched-round-detail", { primaries: 1 });

    await page.getByRole("link", { name: "Practise this round" }).click();
    await page.waitForURL((url) => url.pathname === "/practice/start" && url.searchParams.get("round") === "coding_reasoning");
    await page.locator(".pr-check").getByText("Mirror practice round: Coding conversation — for QA Fictional Company · QA Fictional Country · SDE II").waitFor();
    for (const prompt of QA_RESEARCHED_CODING_PROMPTS) {
      assert.equal(await page.getByText(prompt.text, { exact: true }).count(), 0, "question wording stays hidden before the session begins");
    }
    await screen("fictional-researched-practice-check", { primaries: 1 });
    await page.getByRole("button", { name: "Start practice" }).click();
    await page.waitForURL(/\/sessions\/[^/]+\/brief$/);
    await heading("Before we begin", 1).waitFor();

    const started = await getState();
    assert.equal(started.createBodies.length, genericStartsBefore, "round practice uses the target-linked session path");
    assert.equal(started.targets.roundPractice.length, 1);
    assert.equal(started.targets.roundPractice[0].target_id, TARGET_IDS.target);
    assert.equal(started.targets.roundPractice[0].round_key, "coding_reasoning");
    assert.equal(started.targets.roundPractice[0].mode, "FOCUSED_PRACTICE");
    assert.equal(started.targets.roundPracticeResponses.length, 1);
    const promptRefs = started.targets.roundPracticeResponses[0].prompts;
    assert.ok(promptRefs.some((prompt) => prompt.rationale_code === "PUBLISHED_GUIDANCE_AREA"));
    assert.ok(promptRefs.every((prompt) => !("text" in prompt)), "the start response exposes metadata, not wording");

    await page.getByRole("link", { name: /Begin the conversation/ }).click();
    await page.waitForURL(/\/app\/interview\/[^/]+$/);
    await heading("Ready when you are.", 1).waitFor();
    await joinWithTyping();
    await heading(QA_RESEARCHED_CODING_PROMPTS[0].text, 1).waitFor();
    await overflow("fictional-researched-first-question");

    for (let index = 0; index < QA_RESEARCHED_CODING_PROMPTS.length; index += 1) {
      const current = QA_RESEARCHED_CODING_PROMPTS[index];
      await page.locator("#typed-answer").fill(current.answer);
      await page.getByRole("button", { name: "Send answer" }).click();
      if (index < QA_RESEARCHED_CODING_PROMPTS.length - 1) {
        const next = QA_RESEARCHED_CODING_PROMPTS[index + 1];
        await heading(next.text, 1).waitFor();
        const composerBack = await page.locator("#typed-answer").waitFor({ timeout: 2_500 }).then(() => true, () => false);
        if (!composerBack) {
          // Existing typing-only-room recovery; the same issue is recorded in the main critical path.
          await page.reload();
          await heading("Ready when you are.", 1).waitFor();
          await joinWithTyping();
          await heading(next.text, 1).waitFor();
        }
      }
    }
    await heading("Interview complete", 1).waitFor();
    await poll(async () => (await getState()).ended, { message: "the researched practice to end" });
    const completed = await getState();
    const answersAfterStart = completed.answers.slice(answersBefore);
    assert.equal(completed.ended, true, `completion state: ${JSON.stringify({
      sessionStatus: completed.sessionStatus,
      genericStartsBefore,
      genericStartsAtEnd: completed.createBodies.length,
      answersAfterStart,
      endRequests: completed.requests.filter((request) => /\/sessions\/[^ ]+\/end /.test(request)),
      roundSessionIds: completed.targets.roundPracticeResponses.map((response) => response.session_id),
      targetStarts: completed.targets.roundPractice,
    })}`);
    assert.deepEqual(answersAfterStart, QA_RESEARCHED_CODING_PROMPTS.map((prompt) => prompt.answer));
    await page.getByRole("button", { name: "View review" }).click();
    await page.waitForURL(/\/app\/report\/[^/]+$/);
    await heading("QA Analyst (test role)", 1).waitFor();
    await heading("What landed well").waitFor();
    await heading("One thing to strengthen").waitFor();
    for (const prompt of QA_RESEARCHED_CODING_PROMPTS) await page.getByText(prompt.answer, { exact: true }).waitFor();
    await overflow("fictional-researched-round-review");
    await scenario({ blueprint: "not_researched" });
  });

  // T10 (adapted) Short pack: no practise action, an honest note instead.
  await step("t10-round-short-pack", async () => {
    await scenario({ pack: "short" });
    await page.goto(`${baseUrl}/plan/rounds/system_design?role=${IDS.role}`);
    await page.getByText(/seen every practice question Mirror has for this round in the last 30 days/).waitFor();
    assert.equal(await page.getByRole("link", { name: "Practise this round" }).count(), 0);
    await screen("round-short-pack", { primaries: 0 });
    await scenario({ pack: "full" });
  });

  // T11 Unknown round: plain message and a way back that keeps the role.
  await step("t11-round-unknown-key", async () => {
    await page.goto(`${baseUrl}/plan/rounds/not_a_round?role=${IDS.role}`);
    await heading("We couldn't find that round.", 1).waitFor();
    const back = page.getByRole("link", { name: /Back to My plan/ });
    assert.equal(await back.getAttribute("href"), `/plan?role=${IDS.role}`);
  });

  // T12 Practise this round through the existing practice start: one session, role/round pinned.
  await step("t12-round-practice-start", async () => {
    await reset();
    await page.goto(`${baseUrl}/plan/rounds/coding_reasoning?role=${IDS.role}`);
    const before = (await getState()).createBodies.length;
    await page.getByRole("link", { name: "Practise this round" }).click();
    await page.waitForURL((url) => url.pathname === "/practice/start" && url.searchParams.get("round") === "coding_reasoning");
    await page.locator(".pr-check").getByText("Mirror practice round: Coding conversation — for Amazon · India · Level not set yet").waitFor();
    await overflow("round-practice-check");
    await page.getByRole("button", { name: "Start practice" }).click();
    await page.waitForURL(/\/sessions\/[^/]+\/brief$/);
    const state = await getState();
    assert.equal(state.targets.roundPractice.length, 1);
    assert.equal(state.targets.roundPractice[0].round_key, "coding_reasoning");
    assert.equal(state.targets.roundPractice[0].mode, "FOCUSED_PRACTICE");
    assert.equal(state.targets.links.length, 1);
    assert.ok(state.requests.some((line) => /^POST \/api\/sessions\/[^/]+\/prepare 200$/.test(line)), "the session was prepared");
    assert.equal(state.createBodies.length, before, "no session through the generic path");
  });

  // T13 This round's practice history; other rounds unaffected.
  await step("t13-round-history", async () => {
    await page.goto(`${baseUrl}/plan/rounds/coding_reasoning?role=${IDS.role}`);
    await page.getByText("Practised once").waitFor();
    await page.getByRole("link", { name: "Read your reflection" }).waitFor();
    await page.goto(`${baseUrl}/plan/rounds/system_design?role=${IDS.role}`);
    await page.getByText("You haven't practised this round yet.").waitFor();
  });

  // T14 (adapted) The role is pinned: bare /plan rewrites to ?role=; Home links to the same role.
  await step("t14-plan-role-pinned", async () => {
    await page.goto(`${baseUrl}/plan`);
    await page.waitForURL((url) => url.pathname === "/plan" && url.searchParams.get("role") === IDS.role);
    await page.goto(`${baseUrl}/dashboard`);
    const link = page.getByRole("link", { name: /Open your plan/ });
    await link.waitFor();
    assert.equal(await link.getAttribute("href"), `/plan?role=${IDS.role}`);
  });

  // T15 The stale "Interview Map" label is gone from Home and the plan.
  await step("t15-no-interview-map-label", async () => {
    assert.equal(await page.getByText(/Interview map/i).count(), 0, "Home");
    await page.getByRole("heading", { name: "Your plan", level: 3 }).waitFor();
    await page.goto(planUrl(IDS.role));
    await page.locator(".pl-areas .pl-card").first().waitFor();
    assert.equal(await page.getByText(/Interview map/i).count(), 0, "plan");
    await reset();
  });

  // T16 A failed optional target setup can be skipped without repeating role analysis or showing a scope claim.
  await step("t16-onboarding-continues-with-general-plan-without-target", async () => {
    await reset();
    await page.goto(`${baseUrl}/roles/new`);
    await heading("What role are you preparing for?", 1).waitFor();
    await page.getByLabel("Role", { exact: true }).fill("Software Development Engineer (test role)");
    await page.locator("details.ob-target").waitFor();
    await page.waitForFunction(() => document.querySelector("details.ob-target")?.open === true);
    await page.getByLabel("Company").fill("Amazon");
    await page.getByRole("button", { name: "Skip for now" }).click();
    // The UI already learned targets are available; make the subsequent write/list fail deliberately.
    await scenario({ targets: "disabled" });
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    const alert = page.getByRole("alert");
    await alert.getByText(/Your role details are saved, but company setup didn't finish/).waitFor();
    await screen("target-setup-failed", { primaries: 0 });
    await alert.getByRole("button", { name: "Continue with general role plan" }).click();
    await page.getByRole("button", { name: "See your plan" }).waitFor();
    const state = await getState();
    assert.equal(state.targets.analyze.length, 1, "the saved role analysis is not repeated");
    assert.equal(state.targets.creates.length, 0, "failed target storage leaves no target");
    assert.deepEqual(state.targets.activeRolePuts, [TARGET_IDS.newRole]);
    await page.getByRole("button", { name: "See your plan" }).click();
    await page.waitForURL((url) => url.pathname === "/plan" && url.searchParams.get("role") === TARGET_IDS.newRole);
    await page.locator(".pl-areas .pl-card").first().waitFor();
    assert.equal(await page.locator(".pl-run").count(), 0, "no company target is shown");
    assert.equal(await page.getByText(/Amazon|India/).count(), 0, "no unsupported company or geography claim");
    await screen("general-plan-without-target", { primaries: 1 });
  });

  // ------------------------------------------------------------------ Loop 3 journey B: business roles

  // T17 Same plan section, different intelligence: business-roles rounds, conditional stage, no engineering words.
  await step("t17-business-roles-plan", async () => {
    await reset();
    await scenario({ slice: "business_roles", blueprint: "not_researched", targets: "available", pack: "full" });
    await page.goto(planUrl(IDS.role));
    await heading("Your interview target", 2).waitFor();
    await page.getByText("QA Consulting Co (synthetic) · QA Fictional Country · Consultant").waitFor();
    await page.getByText("From published guidance for where you're applying.").waitFor();
    const business = await planStructure();
    assert.ok(engineeringPlan, "the engineering structure was captured in T3b");
    assert.deepEqual(business.headings, engineeringPlan.headings, "same product structure for both role families");
    assert.equal(business.rounds, engineeringPlan.rounds);
    assert.deepEqual(business.labels, ["Business problem conversation", "Requirements and stakeholder situations", "Examples from your own work"]);
    assert.notDeepEqual(business.labels, engineeringPlan.labels, "the content is not just a renamed engineering plan");
    await page.locator("#round-requirements_and_stakeholders").getByText(/only some processes include this part/).waitFor();
    assert.equal(await page.getByText(/Coding conversation|System design|whiteboard|run your code/).count(), 0, "no engineering round leaks in");
    assert.equal(await page.getByText(/Amazon|Deloitte|India/).count(), 0, "a fictional company never borrows a real scope");
    await page.getByRole("link", { name: /Practise the business problem conversation/ }).waitFor();
    await screen("business-roles-plan", { primaries: 1 });
  });

  // T18 Round pages are the same page for a different format; another family's round does not exist here.
  await step("t18-business-roles-round-detail", async () => {
    await page.goto(`${baseUrl}/plan/rounds/business_problem_solving?role=${IDS.role}`);
    await heading("Business problem conversation", 1).waitFor();
    await page.waitForFunction(() => document.activeElement?.tagName === "H1");
    await heading("What Mirror can and can't do here", 2).waitFor();
    await page.getByText(/doesn't give you a spreadsheet or charts/).waitFor();
    await page.getByText("Published guidance is linked to this practice round, but Mirror has no reviewed summary to show here. Mirror's practice questions are original.").waitFor();
    const priorities = page.locator("[aria-labelledby='round-priorities'] li");
    assert.ok((await priorities.count()) >= 1 && (await priorities.count()) <= 3);
    await priorities.filter({ hasText: /Breaking a problem into clear parts|Working with numbers and data|Weighing business choices/ }).first().waitFor();
    for (const prompt of QA_BUSINESS_CASE_PROMPTS) {
      assert.equal(await page.getByText(prompt.text, { exact: true }).count(), 0, "question wording stays hidden on the round page");
    }
    await screen("business-roles-round-detail", { primaries: 1 });

    await page.goto(`${baseUrl}/plan/rounds/requirements_and_stakeholders?role=${IDS.role}`);
    await heading("Requirements and stakeholder situations", 1).waitFor();
    await page.getByText(/only some processes include this part/).first().waitFor();
    await page.locator("[aria-labelledby='round-priorities'] li").filter({ hasText: "only some processes include" }).first().waitFor();
    await screen("business-roles-conditional-round", { primaries: 1 });

    await page.goto(`${baseUrl}/plan/rounds/coding_reasoning?role=${IDS.role}`);
    await heading("We couldn't find that round.", 1).waitFor();
    // Keep the expected 404 assertion, then leave the browser at the valid BA route so the
    // step-end screenshot documents the working path rather than only its negative control.
    await page.goto(`${baseUrl}/plan/rounds/business_problem_solving?role=${IDS.role}`);
    await heading("Business problem conversation", 1).waitFor();
    await screen("business-roles-round-detail-after-negative-control", { primaries: 1 });
  });

  // T19 Practice start, the interview and the review run through the existing pipeline for a case-style round.
  await step("t19-business-roles-practice-to-review", async () => {
    const before = await getState();
    const answersBefore = before.answers.length;
    const genericStartsBefore = before.createBodies.length;
    await page.goto(`${baseUrl}/plan/rounds/business_problem_solving?role=${IDS.role}`);
    await page.getByRole("link", { name: "Practise this round" }).click();
    await page.waitForURL((url) => url.pathname === "/practice/start" && url.searchParams.get("round") === "business_problem_solving");
    await page.locator(".pr-check").getByText("Mirror practice round: Business problem conversation — for QA Consulting Co (synthetic) · QA Fictional Country · Consultant").waitFor();
    for (const prompt of QA_BUSINESS_CASE_PROMPTS) {
      assert.equal(await page.getByText(prompt.text, { exact: true }).count(), 0, "question wording stays hidden before the session begins");
    }
    await screen("business-roles-practice-check", { primaries: 1 });
    await page.getByRole("button", { name: "Start practice" }).click();
    await page.waitForURL(/\/sessions\/[^/]+\/brief$/);
    const started = await getState();
    assert.equal(started.createBodies.length, genericStartsBefore, "round practice uses the target-linked session path");
    const practice = started.targets.roundPractice.at(-1);
    assert.equal(practice.round_key, "business_problem_solving");
    const refs = started.targets.roundPracticeResponses.at(-1).prompts;
    assert.ok(refs.every((prompt) => !("text" in prompt)), "the start response exposes metadata, not wording");
    assert.ok(refs.some((prompt) => prompt.rationale_code === "PUBLISHED_GUIDANCE_AREA"));

    await page.getByRole("link", { name: /Begin the conversation/ }).click();
    await page.waitForURL(/\/app\/interview\/[^/]+$/);
    await heading("Ready when you are.", 1).waitFor();
    await joinWithTyping();
    await heading(QA_BUSINESS_CASE_PROMPTS[0].text, 1).waitFor();
    await overflow("business-roles-first-question");
    for (let index = 0; index < QA_BUSINESS_CASE_PROMPTS.length; index += 1) {
      await page.locator("#typed-answer").fill(QA_BUSINESS_CASE_PROMPTS[index].answer);
      await page.getByRole("button", { name: "Send answer" }).click();
      if (index < QA_BUSINESS_CASE_PROMPTS.length - 1) {
        const next = QA_BUSINESS_CASE_PROMPTS[index + 1];
        await heading(next.text, 1).waitFor();
        const composerBack = await page.locator("#typed-answer").waitFor({ timeout: 2_500 }).then(() => true, () => false);
        if (!composerBack) {
          // KI-020 typing-only-room recovery (known issue, reported by the main critical path too).
          await page.reload();
          await heading("Ready when you are.", 1).waitFor();
          await joinWithTyping();
          await heading(next.text, 1).waitFor();
        }
      }
    }
    await heading("Interview complete", 1).waitFor();
    await poll(async () => (await getState()).ended, { message: "the business-roles practice to end" });
    const completed = await getState();
    assert.deepEqual(completed.answers.slice(answersBefore), QA_BUSINESS_CASE_PROMPTS.map((prompt) => prompt.answer));
    await page.getByRole("button", { name: "View review" }).click();
    await page.waitForURL(/\/app\/report\/[^/]+$/);
    await heading("What landed well").waitFor();
    for (const prompt of QA_BUSINESS_CASE_PROMPTS) await page.getByText(prompt.answer, { exact: true }).waitFor();
    await overflow("business-roles-review");
  });

  // T20 Onboarding offers the family the role title hints at, with that family's own levels.
  await step("t20-business-roles-onboarding", async () => {
    await reset();
    await scenario({ slice: "business_roles" });
    await page.goto(`${baseUrl}/roles/new`);
    await heading("What role are you preparing for?", 1).waitFor();
    await page.getByLabel("Role", { exact: true }).fill("Business Analyst (test role)");
    await page.waitForFunction(() => document.querySelector("details.ob-target")?.open === true);
    await page.getByLabel("Company").fill("QA Consulting Co (synthetic)");
    assert.equal(await page.getByRole("radio", { name: "Business roles (BA)" }).isChecked(), true);
    assert.equal(await page.getByRole("radio", { name: "SDE II", exact: true }).count(), 0, "no engineering levels for this family");
    await page.getByRole("radio", { name: "Consultant", exact: true }).check();
    await page.getByRole("button", { name: "Skip for now" }).click();
    await screen("business-roles-role-step", { primaries: 1 });
    await page.getByRole("button", { name: /Continue/ }).click();
    await heading(/preparation plan is ready/, 1).waitFor();
    await heading("Your Business Analyst (test role) preparation plan is ready.").waitFor();
    await page.getByText("Clarifying business requirements", { exact: true }).waitFor();
    assert.equal(await page.getByText("Talking through a coding approach", { exact: true }).count(), 0,
      "business-roles onboarding preview must not inherit the engineering fixture");
    const state = await getState();
    assert.deepEqual(state.targets.creates, [{
      role_profile_id: TARGET_IDS.newRole, company: "QA Consulting Co (synthetic)", role_family: "business_analysis", level: "consultant",
    }]);
    await scenario({ slice: "engineering" });
    await reset();
  });
}
