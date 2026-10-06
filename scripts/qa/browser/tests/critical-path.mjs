// Critical candidate path, driven by a real system Chrome/Edge against the real Next production build.
// sign in -> Home -> role context -> quick drill -> brief -> interview (typed answers) -> complete
// -> review -> reload (persisted) -> Home shows the review -> sign out -> /dashboard redirects to /login.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";

import { installBrowserRail } from '../lib/network.mjs';
import { requireSupportedIsolation, resultOk } from '../lib/safety.mjs';
import { resolveBrowser } from "../lib/browser.mjs";
import { createCollector } from "../lib/collector.mjs";
import { IDS, QA_NAME } from "../mock/server.mjs";
import { runTargetJourneys } from "./target-journeys.mjs";

export const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844, isMobile: true, hasTouch: true },
];

const ROLE = "QA Analyst (test role)";
const ANSWERS = [
  "QA-SYNTHETIC-ANSWER-ONE: I built a small reporting tool for a made-up team.",
  "QA-SYNTHETIC-ANSWER-TWO: I wrote the data model and the weekly export.",
  "QA-SYNTHETIC-ANSWER-THREE: Weekly reporting time dropped from two hours to ten minutes.",
];
const QUESTIONS = ["Tell me about one project you worked on.", "What was your own part in it?", "What changed because of that work?"];

/** Condition polling with a deadline (no fixed sleeps). */
async function poll(fn, { timeout = 10_000, interval = 100, message = "condition" } = {}) {
  const deadline = Date.now() + timeout;
  let last;
  for (;;) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (error) {
      last = error;
    }
    if (Date.now() > deadline) throw new Error(`timed out waiting for ${message}${last ? ` (${last.message})` : ""}`);
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
}

async function runViewport({ browser, viewport, baseUrl, mock, password, outDir }) {
  const collector = createCollector();
  const result = { viewport: viewport.name, size: `${viewport.width}x${viewport.height}`, steps: [], overflow: {}, knownIssues: [], notes: [] };
  const controlHeaders = { "x-qa-control-token": mock.controlToken };
  const getState = async () => {
    const response = await fetch(`${mock.apiUrl}/__qa/state`, { headers: controlHeaders, redirect: "error" });
    assert.equal(response.status, 200);
    return response.json();
  };
  const reset = await fetch(`${mock.apiUrl}/__qa/reset`, { method: "POST", headers: controlHeaders, redirect: "error" });
  assert.equal(reset.status, 200);

  const deniedRequests = [];
  const context = await browser.newContext({
    serviceWorkers: "block",
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: viewport.isMobile ?? false,
    hasTouch: viewport.hasTouch ?? false,
    deviceScaleFactor: 1,
    reducedMotion: "reduce", // stable screenshots; the login page animates continuously otherwise
    locale: "en-US",
    timezoneId: "UTC",
  });
  await installBrowserRail(context, [baseUrl, mock.authUrl, mock.apiUrl], deniedRequests);
  // Synthetic microphone: the room must take the "microphone blocked -> continue with typing" path.
  await context.addInitScript(() => {
    if (navigator.mediaDevices) {
      navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
    }
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  collector.attach(page);

  let index = 0;
  let failed = false;
  async function step(name, fn) {
    index += 1;
    const label = `${String(index).padStart(2, "0")}-${name}`;
    const entry = { name, ok: false, ms: 0, screenshot: null };
    result.steps.push(entry);
    if (failed) {
      entry.skipped = true;
      return;
    }
    collector.setStep(name);
    const started = Date.now();
    try {
      await fn();
      entry.ok = true;
    } catch (error) {
      failed = true;
      entry.error = String(error?.message ?? error).split("\n").slice(0, 6).join(" | ");
    }
    entry.ms = Date.now() - started;
    entry.screenshot = path.join(outDir, `${viewport.name}-${label}.png`);
    await page.screenshot({ path: entry.screenshot, fullPage: true }).catch(() => { entry.screenshot = null; });
    console.log(`  ${entry.ok ? "ok  " : entry.skipped ? "skip" : "FAIL"} [${viewport.name}] ${label}${entry.error ? `  -> ${entry.error}` : ""}`);
  }

  async function overflow(label) {
    const metrics = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    result.overflow[label] = metrics;
    if (viewport.name === "mobile") {
      assert.ok(metrics.scrollWidth <= metrics.clientWidth, `horizontal overflow on ${label}: scrollWidth ${metrics.scrollWidth} > clientWidth ${metrics.clientWidth}`);
    }
  }
  const heading = (name, level) => page.getByRole("heading", { name, ...(level ? { level } : {}) });
  const joinWithTyping = async () => {
    await page.getByRole("button", { name: "Check microphone" }).click();
    await page.getByText("Microphone blocked").waitFor();
    await page.getByRole("button", { name: "Continue with typing" }).click();
    await page.locator("#typed-answer").waitFor();
  };

  // 1. Unauthenticated visit is sent to /login by the middleware.
  await step("unauth-dashboard-redirects-to-login", async () => {
    await page.goto(`${baseUrl}/dashboard`);
    await page.waitForURL((url) => url.pathname === "/login");
    assert.equal(new URL(page.url()).searchParams.get("reason"), "session_expired");
    await heading("Sign in to Mirror", 1).waitFor();
  });

  await step("login-renders", async () => {
    await page.getByLabel("Email").waitFor();
    await page.getByLabel("Password").waitFor();
    await page.getByRole("button", { name: "Sign in" }).waitFor();
    await overflow("login");
  });

  await step("login-wrong-password", async () => {
    await page.getByLabel("Email").fill(mock.email);
    await page.getByLabel("Password").fill(`wrong-${Math.random().toString(36).slice(2)}`);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("alert").filter({ hasText: "didn't match" }).waitFor();
    assert.equal(new URL(page.url()).pathname, "/login");
  });

  await step("login", async () => {
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL((url) => url.pathname === "/dashboard");
  });

  // 2. Home: greeting, role/target context, one clear primary action.
  await step("home", async () => {
    await heading(/, QA$/, 1).waitFor();
    await page.getByText(`Preparing for: ${ROLE}`).waitFor();
    await page.locator(".hm-role strong", { hasText: ROLE }).waitFor();
    await heading(`Start your first ${ROLE} practice`, 2).waitFor();
    await page.getByRole("link", { name: `Start ${ROLE} practice` }).waitFor();
    await page.getByText(QA_NAME).first().waitFor({ state: "attached" }); // profile loaded from /api/v1/me (name sits in a menu on narrow screens)
    await overflow("home");
  });

  // 3. Start ONE quick drill.
  await step("start-practice-choose-quick-drill", async () => {
    await page.getByRole("link", { name: `Start ${ROLE} practice` }).click();
    await page.waitForURL((url) => url.pathname === "/practice/start");
    await heading("What would you like to work on?", 1).waitFor();
    await page.locator("label", { hasText: "5-minute drill" }).click();
    await page.locator("label", { hasText: "Explain a project" }).click();
    const check = page.locator(".pr-check");
    await check.getByText("5-minute drill", { exact: true }).waitFor();
    await check.getByText("Explain a project", { exact: true }).waitFor();
    await overflow("start-practice");
  });

  await step("start-practice-create-session", async () => {
    await page.getByRole("button", { name: "Start practice" }).click();
    await page.waitForURL(/\/sessions\/[^/]+\/brief$/);
    const state = await getState();
    assert.equal(state.createBodies.length, 1, "exactly one session is created");
    assert.equal(state.createBodies[0].practice_mode, "QUICK_DRILL");
    assert.equal(state.createBodies[0].practice_focus, "project");
    assert.equal(state.createBodies[0].role_profile_id, IDS.role);
  });

  await step("session-brief", async () => {
    await heading("Before we begin", 1).waitFor();
    await page.getByText("5-minute drill · Explain a project").waitFor();
    await page.getByRole("link", { name: /Begin the conversation/ }).waitFor();
    await overflow("brief");
    await page.getByRole("link", { name: /Begin the conversation/ }).click();
    await page.waitForURL(/\/app\/interview\/[^/]+$/);
  });

  // 4. Interview, typed answers.
  await step("interview-prejoin-microphone-blocked-offers-typing", async () => {
    await heading("Ready when you are.", 1).waitFor();
    await overflow("interview-prejoin");
    await page.getByRole("button", { name: "Check microphone" }).click();
    await page.getByText("Microphone blocked").waitFor();
    await page.getByRole("button", { name: "Continue with typing" }).waitFor();
  });

  await step("interview-join-with-typing", async () => {
    await page.getByRole("button", { name: "Continue with typing" }).click();
    await page.locator("#typed-answer").waitFor();
    await heading(QUESTIONS[0], 1).waitFor();
    await page.getByText("Hello, this is a short synthetic practice.").first().waitFor(); // spoken welcome shown as text
    await overflow("interview-room");
  });

  for (let i = 0; i < ANSWERS.length; i += 1) {
    await step(`interview-answer-${i + 1}`, async () => {
      if (i > 0 && !(await page.locator("#typed-answer").isVisible())) {
        // Reached only if the composer did not come back after the previous answer (see knownIssues).
        await joinAgain(QUESTIONS[i]);
      }
      await page.locator("#typed-answer").fill(ANSWERS[i]);
      await page.getByRole("button", { name: "Send answer" }).click();
      if (i < ANSWERS.length - 1) {
        await heading(QUESTIONS[i + 1], 1).waitFor();
        const composerBack = await page.locator("#typed-answer").waitFor({ timeout: 2_500 }).then(() => true, () => false);
        if (!composerBack) {
          const status = (await page.locator(".interview-call-status strong").innerText()).trim();
          const typeDisabled = await page.getByRole("button", { name: "Type" }).isDisabled();
          result.knownIssues.push({
            id: "typing-only-room-stuck-after-answer",
            where: "apps/web/src/components/voice-interview.tsx submitTextFallback()",
            observed: `after a typed answer with no microphone the room stays "${status}", the composer is closed and the Type button is ${typeDisabled ? "disabled" : "enabled"}`,
            workaround: "reload the room and re-join with typing",
          });
        }
      }
    });
  }
  async function joinAgain(question) {
    await page.reload();
    await heading("Ready when you are.", 1).waitFor();
    await joinWithTyping();
    await heading(question, 1).waitFor();
  }

  await step("interview-complete", async () => {
    await heading("Interview complete", 1).waitFor();
    await poll(async () => (await getState()).ended, { message: "the room to end the session" });
    const state = await getState();
    assert.deepEqual(state.answers, ANSWERS, "every typed answer reached the API");
    assert.ok(state.heartbeats >= 1, "lifecycle heartbeat ran");
    await overflow("interview-complete");
  });

  // 5. Review/report, and persistence across reload.
  const assertReview = async () => {
    await heading(ROLE, 1).waitFor();
    await heading("What landed well").waitFor();
    await heading("One thing to strengthen").waitFor();
    await heading("Try this next").or(page.getByText("Try this next")).first().waitFor();
    for (const answer of ANSWERS) await page.getByText(answer, { exact: true }).waitFor();
    await page.getByText("QA-FIXTURE-QUOTE-SUPPORTS").first().waitFor();
  };
  await step("review", async () => {
    await page.getByRole("button", { name: "View review" }).click();
    await page.waitForURL(/\/app\/report\/[^/]+$/);
    await assertReview();
    await overflow("review");
  });

  await step("review-persists-after-reload", async () => {
    await page.reload();
    await assertReview();
    const state = await getState();
    assert.equal(state.sessionStatus, "COMPLETED");
    assert.equal(state.ended, true);
    await overflow("review-reloaded");
  });

  await step("home-shows-completed-practice", async () => {
    await page.goto(`${baseUrl}/dashboard`);
    await heading(/, QA$/, 1).waitFor();
    await page.getByText("Your practice is complete.").waitFor();
    await page.getByRole("link", { name: /View (your )?review/i }).first().waitFor();
    await overflow("home-after-practice");
  });

  // 6. Loop 2: interview target, plan, research-scoped round practice and no-target recovery (T1–T16, including T3b/T9b).
  await runTargetJourneys({ page, step, baseUrl, mock, viewport, overflow, getState, poll });

  // 7. Sign out; the session is really gone.
  await step("sign-out", async () => {
    await page.getByRole("button", { name: /^Your account/ }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await page.waitForURL((url) => url.pathname === "/login");
    await heading("Sign in to Mirror", 1).waitFor();
    const state = await getState();
    assert.ok(state.authLog.includes("POST /auth/v1/logout"), "auth logout was called");
    await page.goto(`${baseUrl}/dashboard`);
    await page.waitForURL((url) => url.pathname === "/login");
  });

  const state = await getState();
  const findings = collector.findings();
  // Sign-out navigates away while the logout POST is in flight; the browser then reports ERR_ABORTED even though
  // the fake auth server received it (asserted above via authLog). That one abort is not a failed request.
  if (state.authLog.includes("POST /auth/v1/logout")) {
    findings.failedRequests = findings.failedRequests.filter((f) => !(f.step === "sign-out" && /\/auth\/v1\/logout/.test(f.url) && f.error === "net::ERR_ABORTED"));
  }
  findings.deniedRequests = deniedRequests;
  result.findings = findings;
  result.consoleWarnings = collector.bag.consoleWarnings.length;
  result.networkRequests = collector.bag.counts.requests;
  result.unmockedApiCalls = state.unmocked;
  result.apiRequests = state.requests.length;
  result.ok = resultOk([result]);
  await context.close();
  return result;
}

export async function runCriticalPath({ baseUrl, mock, password, outDir, viewports = VIEWPORTS }) {
  if (!Array.isArray(viewports) || viewports.length === 0) throw new Error('Invalid viewport selection: no execution');
  requireSupportedIsolation();
  fs.mkdirSync(outDir, { recursive: true });
  const launch = resolveBrowser();
  const browser = await chromium.launch({ headless: true, ...(launch.executablePath ? { executablePath: launch.executablePath } : { channel: launch.channel }) });
  const summary = { startedAt: new Date().toISOString(), browser: `${launch.describe} (${browser.version()})`, baseUrl, viewports: [] };
  try {
    for (const viewport of viewports) {
      console.log(`viewport ${viewport.name} ${viewport.width}x${viewport.height}`);
      summary.viewports.push(await runViewport({ browser, viewport, baseUrl, mock, password, outDir }));
    }
  } finally {
    await browser.close();
  }
  summary.executedViewports = summary.viewports.length;
  summary.executedSteps = summary.viewports.reduce((count, view) => count + view.steps.filter(step => !step.skipped).length, 0);
  summary.ok = resultOk(summary.viewports);
  return summary;
}
