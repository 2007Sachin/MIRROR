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
    const nativeFetch = window.fetch.bind(window);
    window.__qaLoseNextTextTurnResponse = false;
    window.fetch = async (input, init) => {
      const requestUrl = typeof input === "string" ? input : input instanceof Request ? input.url : String(input);
      const requestMethod = init?.method ?? (input instanceof Request ? input.method : "GET");
      const response = await nativeFetch(input, init);
      if (window.__qaLoseNextTextTurnResponse && response.ok && requestMethod.toUpperCase() === "POST" && new URL(requestUrl, window.location.href).pathname.endsWith("/turn-text")) {
        window.__qaLoseNextTextTurnResponse = false;
        throw new TypeError("Synthetic client-side response loss after server commit");
      }
      return response;
    };
  });
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  collector.attach(page);

  let documentNavigations = 0;
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) documentNavigations += 1;
  });
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

  async function overflow(label, always = false) {
    const metrics = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    result.overflow[label] = metrics;
    if (always || viewport.name === "mobile") {
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

  // 1. Public Reading Room landing: real copy, CTA behavior and responsive layout.
  await step("landing", async () => {
    await page.goto(baseUrl);
    await heading("Find the words for your experience.", 1).waitFor();
    const signupLinks = page.getByRole("link", { name: "Start practicing" });
    assert.ok(await signupLinks.count() >= 1, "landing exposes a Start practicing link");
    assert.ok(await signupLinks.evaluateAll((links) => links.every((link) => link.getAttribute("href") === "/signup")), "every Start practicing link opens signup");
    await page.getByRole("link", { name: "See a sample reflection" }).click();
    await page.locator("#sample-reflection").waitFor();
    await page.getByRole("table", { name: "Mirror compared with a generic mock interview" }).waitFor();
    assert.equal(await page.getByRole("columnheader").count(), 3);
    await overflow("landing", true);
  });

  // 2. Unauthenticated visit is sent to /login by the middleware.
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

  // 3. Home: greeting, role/target context, one clear primary action.
  await step("home", async () => {
    await heading(/, QA$/, 1).waitFor();
    await page.locator(".hm-role-card .dh-section-label", { hasText: "Preparing for:" }).waitFor();
    await page.locator(".hm-role-card strong", { hasText: ROLE }).waitFor();
    await heading(`Start your first ${ROLE} practice`, 2).waitFor();
    await page.getByRole("link", { name: `Start ${ROLE} practice` }).waitFor();
    await page.getByText(QA_NAME).first().waitFor({ state: "attached" }); // profile loaded from /api/v1/me (name sits in a menu on narrow screens)
    await overflow("home");
    if (viewport.name === "desktop") {
      // The top bar is tightest just above the tab-bar breakpoint: every link stays visible, nothing scrolls sideways.
      for (const width of [1025, 1100, 1180]) {
        await page.setViewportSize({ width, height: viewport.height });
        await page.locator(".ws-nav-item", { hasText: "Reflect" }).waitFor();
        await overflow(`home-${width}`, true);
        await page.screenshot({ path: path.join(outDir, `${viewport.name}-05-home-${width}.png`) }).catch(() => undefined);
      }
      await page.setViewportSize({ width: 820, height: 1180 });
      await overflow("home-tablet", true);
      await page.screenshot({ path: path.join(outDir, "tablet-05-home.png"), fullPage: true });
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
    }
  });

  // 4. Start ONE quick drill.
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
    await page.waitForURL(/\/app\/interview\/[^/]+$/); // P7: a new practice opens on the pre-join
    const state = await getState();
    assert.equal(state.createBodies.length, 1, "exactly one session is created");
    assert.equal(state.createBodies[0].practice_mode, "QUICK_DRILL");
    assert.equal(state.createBodies[0].practice_focus, "project");
    assert.equal(state.createBodies[0].role_profile_id, IDS.role);
  });

  // P7: the brief now lives in the pre-join; the old brief URL still opens the same session.
  const sessionPath = new URL(page.url()).pathname;
  const startsSoFar = async () => (await getState()).requests.filter((request) => /\/sessions\/[^/]+\/(voice\/)?start /.test(request)).length;
  await step("session-brief", async () => {
    await heading("Ready when you are.", 1).waitFor();
    await page.getByText("5-minute drill · Explain a project").waitFor();
    await page.getByText(/recorded and saved privately to your account, with a transcript/).waitFor();
    await page.getByRole("button", { name: "Check microphone" }).waitFor();
    await page.getByRole("button", { name: "Continue with typing" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Start interview" }).count(), 0, "no start before the microphone is checked");
    await overflow("brief");
    if (viewport.name === "desktop") {
      await page.setViewportSize({ width: 820, height: 1180 });
      await overflow("prejoin-tablet", true);
      await page.screenshot({ path: path.join(outDir, "tablet-prejoin.png"), fullPage: true });
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
    }
  });

  await step("brief-deep-link-opens-prejoin", async () => {
    const sessionId = sessionPath.split("/").at(-1);
    await page.goto(`${baseUrl}/sessions/${sessionId}/brief`);
    await page.waitForURL((url) => url.pathname === sessionPath);
    await heading("Ready when you are.", 1).waitFor();
    assert.equal(await startsSoFar(), 0, "opening the pre-join never starts the interview");
  });

  await step("prejoin-microphone-allowed", async () => {
    // A synthetic, silent microphone for this page only; the next navigation restores the blocked one.
    await page.evaluate(() => {
      navigator.mediaDevices.getUserMedia = async () => new AudioContext().createMediaStreamDestination().stream;
    });
    await page.getByRole("button", { name: "Check microphone" }).click();
    await page.getByRole("status").filter({ hasText: "Microphone ready" }).waitFor();
    await page.getByRole("button", { name: "Start interview" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "Check microphone" }).count(), 0, "one primary action once the microphone is ready");
    await page.getByRole("button", { name: "Continue with typing" }).waitFor();
    assert.equal(await startsSoFar(), 0);
    await page.reload(); // back to the run's blocked microphone for the next steps
    await heading("Ready when you are.", 1).waitFor();
  });

  await step("home-shows-active-practice", async () => {
    await page.goto(`${baseUrl}/dashboard`);
    await heading(/, QA$/, 1).waitFor();
    const activePracticeLink = page.getByRole("link", { name: /(?:Begin|Continue) practice/ });
    await activePracticeLink.waitFor();
    await page.getByText("Not started yet").waitFor();
    await overflow("home-active-practice", true);
    if (viewport.name === "desktop") {
      await page.setViewportSize({ width: 820, height: 1180 });
      await overflow("home-active-practice-tablet", true);
      await page.screenshot({ path: path.join(outDir, "tablet-09-home-shows-active-practice.png"), fullPage: true });
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
    }
  });

  await step("resume-active-practice", async () => {
    await page.getByRole("link", { name: /(?:Begin|Continue) practice/ }).click();
    await page.waitForURL(/\/app\/interview\/[^/]+$/);
  });

  // 4. Interview, typed answers.
  await step("interview-prejoin-microphone-blocked-offers-typing", async () => {
    await heading("Ready when you are.", 1).waitFor();
    await page.getByRole("button", { name: "Try the microphone again" }).waitFor({ state: "hidden" });
    await overflow("interview-prejoin");
    await page.getByRole("button", { name: "Check microphone" }).click();
    await page.getByText("Microphone blocked").waitFor();
    await page.getByRole("button", { name: "Continue with typing" }).waitFor();
    await page.getByRole("button", { name: "Try the microphone again" }).waitFor();
    await page.getByText(/Microphone access is blocked/).waitFor();
  });

  await step("interview-join-with-typing", async () => {
    // A double click must start the interview once: the button is disabled while joining.
    await page.getByRole("button", { name: "Continue with typing" }).dblclick();
    await page.locator("#typed-answer").waitFor();
    await heading(QUESTIONS[0], 1).waitFor();
    await page.getByText("Hello, this is a short synthetic practice.").first().waitFor(); // spoken welcome shown as text
    const typedOnlyState = await getState();
    assert.equal(typedOnlyState.requests.filter((request) => request.includes("/voice/start")).length, 0, "microphone-denied typed-only join does not request voice prompts");
    assert.equal(await startsSoFar(), 1, "a double click starts the interview once");
    await overflow("interview-room");
    await page.getByRole("button", { name: "Mute microphone" }).waitFor({ state: "hidden" });
    await page.getByRole("button", { name: "Cancel", exact: true }).waitFor({ state: "hidden" });
    documentNavigations = 0;
  });

  for (let i = 0; i < ANSWERS.length; i += 1) {
    await step(`interview-answer-${i + 1}`, async () => {
      const navigationCount = documentNavigations;
      await page.locator("#typed-answer").fill(ANSWERS[i]);
      if (i === 0) {
        await page.evaluate(() => { window.__qaLoseNextTextTurnResponse = true; });
      }
      await page.getByRole("button", { name: "Send answer" }).click();
      if (i === 0) {
        await page.getByRole("alert").waitFor();
        assert.equal(await page.locator("#typed-answer").inputValue(), ANSWERS[i], "draft survives ambiguous failure");
        assert.equal(await page.locator("#typed-answer").isEditable(), false, "pending answer cannot be changed before idempotent retry");
        await page.getByRole("button", { name: "Retry answer" }).click();
        await heading(QUESTIONS[i + 1], 1).waitFor();
        const retried = await getState();
        assert.equal(retried.answers.filter((answer) => answer === ANSWERS[i]).length, 1, "server stores one answer");
        assert.equal(retried.textClientTurnIds[0], retried.textClientTurnIds[1], "retry reuses client_turn_id");
        const turnRequests = retried.requests.filter((request) => request.includes("/turn-text"));
        assert.equal(turnRequests.length, 2);
        assert.ok(turnRequests.every((request) => request.endsWith(" 200")), "both server responses are successful; the browser alone loses the first response");
      }
      if (i < ANSWERS.length - 1) {
        await heading(QUESTIONS[i + 1], 1).waitFor();
        await page.locator("#typed-answer").waitFor({ timeout: 2_500 });
      }
      assert.equal(documentNavigations, navigationCount, "typed progression does not reload or navigate the document");
    });
    if (i === 0) {
      // P7: refreshing mid-interview returns to the pre-join for the same session; nothing is lost.
      await step("interview-refresh-rejoin", async () => {
        const before = await startsSoFar();
        await page.reload();
        await heading("Your conversation is saved", 1).waitFor();
        await page.getByText("Pick up where you left off.").waitFor();
        await page.getByRole("button", { name: "Continue with typing" }).click();
        await page.locator("#typed-answer").waitFor();
        await heading(QUESTIONS[1], 1).waitFor();
        const rejoined = await getState();
        assert.equal(rejoined.answers.filter((answer) => answer === ANSWERS[0]).length, 1, "the saved answer is kept, not repeated");
        assert.equal(await startsSoFar(), before + 1, "rejoining starts once");
        await overflow("interview-rejoin");
      });
    }
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
    // P6: the backend's own summary, then what came through with where each item came from.
    await heading("Developing", 2).waitFor();
    await heading("What you shared, and how it came through", 2).waitFor();
    await page.getByText("QA-FIXTURE-QUOTE-HELD").first().waitFor(); // also attached to the answer it came from
    await page.getByText("1:14").waitFor();
    await page.getByText("Backs this up").first().waitFor();
    await page.getByText("Mirror's note").first().waitFor();
    await page.getByText("From your conversation").first().waitFor();
    await heading("Not enough to say yet", 3).waitFor();
    // A closed row opens from the keyboard and shows the line from the person's own documents.
    const resumeRow = page.locator("summary", { hasText: "Led the QA fixture migration (synthetic)" });
    await resumeRow.focus();
    await page.keyboard.press("Enter");
    await page.getByText("QA-FIXTURE-RESUME-LINE").waitFor();
    await page.getByText("From your resume or documents").first().waitFor();
    assert.equal(await page.locator(".dh-primary-action").count(), 1, "one primary action on the review");
  };
  const reviewScenario = async (review) => {
    const response = await fetch(`${mock.apiUrl}/__qa/scenario`, { method: "POST", headers: { ...controlHeaders, "content-type": "application/json" }, body: JSON.stringify({ review }), redirect: "error" });
    assert.equal(response.status, 200, `review scenario ${review}`);
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

  if (viewport.name === "desktop") {
    await step("review-tablet", async () => {
      await page.setViewportSize({ width: 820, height: viewport.height });
      await heading("What you shared, and how it came through", 2).waitFor();
      await overflow("review-tablet", true);
      await page.screenshot({ path: path.join(outDir, `${viewport.name}-review-820.png`), fullPage: true }).catch(() => undefined);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
    });
  }

  // P6 review states, served by the mock exactly as the backend answers them.
  const reviewAt = page.url();
  await step("review-practice-only", async () => {
    await reviewScenario("practice_only");
    await page.goto(reviewAt);
    await heading("Practice only", 2).waitFor();
    await page.getByText(/From a shorter conversation/).waitFor();
    assert.equal(await page.getByRole("heading", { name: "What you shared, and how it came through" }).count(), 0, "no empty ledger");
    await overflow("review-practice-only");
  });
  await step("review-processing", async () => {
    await reviewScenario("processing");
    await page.goto(reviewAt);
    await heading("Preparing your review", 1).waitFor();
    await page.getByRole("status").filter({ hasText: "Preparing." }).waitFor(); // the loader announces the state once
    await page.getByText(/is looking at what you shared and how it connects/).waitFor();
    await overflow("review-processing");
  });
  await step("review-failed", async () => {
    await reviewScenario("failed");
    await page.goto(reviewAt);
    await heading("We couldn't finish your review just now", 1).waitFor();
    await page.getByRole("button", { name: "Try again" }).waitFor();
    await page.getByRole("alert").filter({ hasText: /without repeating the conversation/ }).waitFor();
  });
  await step("review-unavailable", async () => {
    await reviewScenario("unavailable503");
    await page.goto(reviewAt);
    await heading("Your review isn't available right now", 1).waitFor();
    await page.getByRole("alert").filter({ hasText: /couldn't load your review/ }).waitFor(); // not Next's route announcer
  });
  await step("review-restored", async () => {
    await reviewScenario("ready");
    await page.goto(reviewAt);
    await assertReview();
  });

  await step("home-shows-completed-practice", async () => {
    await page.goto(`${baseUrl}/dashboard`);
    await heading(/, QA$/, 1).waitFor();
    await page.getByText("Your practice is complete.").waitFor();
    await page.getByRole("link", { name: /View (your )?review/i }).first().waitFor();
    await overflow("home-after-practice");
  });

  // 5b. Reading Room screens whose data the mock serves (the mock has no GET /api/v1/roles list): each renders a heading and never scrolls sideways.
  for (const route of ["/help", "/settings"]) {
    await step(`reading-room${route.replace("/", "-")}`, async () => {
      await page.goto(`${baseUrl}${route}`);
      await page.locator(".reading-room h1").first().waitFor();
      await page.waitForLoadState("networkidle");
      await overflow(`reading-room${route}`);
    });
  }

  // 6. Loop 2: interview target, plan, research-scoped round practice and no-target recovery (T1–T16, including T3b/T9b).
  await runTargetJourneys({ page, step, baseUrl, mock, viewport, overflow, getState, poll });

  // 7. Sign out; the session is really gone.
  await step("sign-out", async () => {
    await page.getByRole("button", { name: /^Your account/ }).click();
    await page.getByRole("button", { name: "Sign out" }).click();
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
