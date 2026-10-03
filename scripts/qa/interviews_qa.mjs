// Local-only browser QA for the Interviews screens (see docs/architecture/HOME_QA.md).
// Needs a dev server started with MIRROR_HOME_QA=1. The API is stubbed at the network
// layer with the fixtures from /interviews-qa/fixtures; no production code is hooked.
//
//   QA_BASE=http://localhost:3107 PLAYWRIGHT_MODULE=<path to playwright> QA_OUT=<dir> node scripts/qa/interviews_qa.mjs
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ?? "playwright");
const BASE = process.env.QA_BASE ?? "http://localhost:3000";
const API = (process.env.NEXT_PUBLIC_API_URL ?? readEnv("NEXT_PUBLIC_API_URL") ?? "http://localhost:8000").replace(/\/$/, "");
const OUT = process.env.QA_OUT ?? "qa-out";
fs.mkdirSync(OUT, { recursive: true });

function readEnv(key) {
  try {
    const line = fs.readFileSync(path.resolve(".env"), "utf8").split(/\r?\n/).find((l) => l.startsWith(`${key}=`));
    return line?.slice(key.length + 1).trim().replace(/^["']|["']$/g, "");
  } catch {
    return undefined;
  }
}

const failures = [];
const check = (ok, message) => {
  if (!ok) failures.push(message);
  console.log(`${ok ? "ok  " : "FAIL"} ${message}`);
};
const fixtures = await (await fetch(`${BASE}/interviews-qa/fixtures`)).json();
const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };

/** A stateful fake of the interview endpoints, one per page. */
async function stubApi(page, tag) {
  const state = structuredClone(fixtures);
  let next = 200;
  const json = (route, body, status = 200) => route.fulfill({ status, headers: cors, contentType: "application/json", body: JSON.stringify(body) });
  await page.route((url) => url.href.startsWith(API), async (route) => {
    const req = route.request();
    const method = req.method();
    const p = new URL(req.url()).pathname;
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    const body = req.postData() ? JSON.parse(req.postData()) : null;
    let m;
    if (p === "/api/v1/me") return json(route, state.profile);
    if ((m = p.match(/^\/api\/v1\/roles\/([^/]+)\/interviews$/))) {
      if (method === "GET") return json(route, state.events);
      const event = {
        id: `00000000-0000-4000-8000-${String(next++).padStart(12, "0")}`, role_profile_id: m[1], round_kind: "OTHER", company_label: null,
        ...body, has_debrief: false, timing: "UPCOMING", created_at: state.now, updated_at: state.now,
      };
      state.events.push(event);
      state.briefs[event.id] = { ...Object.values(state.briefs)[0], event };
      return json(route, event, 201);
    }
    if ((m = p.match(/^\/api\/v1\/interviews\/([^/]+)(\/brief|\/debrief)?$/))) {
      const [, id, sub] = m;
      const event = state.events.find((e) => e.id === id);
      if (!event) return json(route, { detail: "Not found" }, 404);
      if (!sub && method === "PATCH") {
        Object.assign(event, body, { updated_at: state.now });
        return json(route, event);
      }
      if (!sub && method === "DELETE") {
        state.events = state.events.filter((e) => e !== event);
        return route.fulfill({ status: 204, headers: cors });
      }
      if (sub === "/brief") return json(route, { ...state.briefs[id], event });
      if (sub === "/debrief" && method === "GET") return state.debriefs[id] ? json(route, state.debriefs[id]) : json(route, { detail: "Not found" }, 404);
      if (sub === "/debrief" && method === "PUT") {
        event.has_debrief = true;
        const view = {
          debrief: { id: "00000000-0000-4000-8000-000000000999", interview_event_id: id, created_at: state.now, updated_at: state.now, feeling: null, outcome: "WAITING", notes: null, ...body },
          follow_ups: body.questions_asked.map((question, i) =>
            i === 0
              ? { question, theme_key: "reconciliation", theme_label: "Reconciliation", coverage: "MENTIONED", action: "STRENGTHEN_STORY", action_href: "/stories?theme=Reconciliation" }
              : { question, theme_key: null, theme_label: null, coverage: null, action: "NONE", action_href: null },
          ),
        };
        state.debriefs[id] = view;
        return json(route, view);
      }
    }
    console.log(`[${tag}] unstubbed ${method} ${p}`);
    return json(route, { detail: "Not stubbed" }, 404);
  });
}

async function openScreen(browser, screen, width) {
  const context = await browser.newContext({ viewport: { width, height: 900 }, timezoneId: "UTC", locale: "en-GB", reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (msg) => {
    // A missing debrief is a 404 by contract (api.ts turns it into null); the browser still logs it.
    if (msg.type() === "error" && !/\/debrief$/.test(msg.location().url)) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(String(err)));
  page.on("dialog", (dialog) => void dialog.accept());
  await stubApi(page, `${screen}@${width}`);
  await page.goto(`${BASE}/interviews-qa?screen=${screen}`);
  await page.locator(".dh-section, .dh-empty").first().waitFor();
  await page.waitForLoadState("networkidle");
  return { context, page, errors };
}

const sec = (id) => `section[aria-labelledby="${id}-title"]`;
const PRIMARY = ".dh-primary-action, .button-primary, .workspace-primary-action";
const countPrimary = (page) => page.locator(PRIMARY).evaluateAll((els) => els.filter((el) => el.checkVisibility()).length);
const active = (page) =>
  page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body) return null;
    const s = getComputedStyle(el);
    const ring = (s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== "none";
    return { tag: el.tagName, text: (el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 50), ring, id: el.dataset.qaId };
  });
async function tabTo(page, predicate, max = 80) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const a = await active(page);
    if (a && predicate(a)) return a;
  }
  return null;
}
const resetFocus = (page) => page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });

/** Structural and keyboard checks shared by every screen. */
async function staticChecks(page, label, width, expectedPrimary) {
  if (width === 375) check(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), `${label}: no horizontal scroll`);
  const primaries = await countPrimary(page);
  check(primaries === expectedPrimary, `${label}: ${expectedPrimary} filled primary button(s) visible (found ${primaries})`);
  const unlabelled = await page.evaluate(() =>
    [...document.querySelectorAll("input, select, textarea")]
      .filter((el) => el.type !== "hidden" && !el.labels?.length && !el.getAttribute("aria-label") && !el.getAttribute("aria-labelledby"))
      .map((el) => el.outerHTML.slice(0, 80)),
  );
  check(!unlabelled.length, `${label}: every field has a label ${unlabelled.join(" ")}`);
  check((await page.locator('[role="status"]').count()) > 0, `${label}: a status region exists`);
  const raw = await page.evaluate(() => document.body.innerText.match(/\b[A-Z]{3,}(?:_[A-Z]+)+\b|\b(?:SOON|UPCOMING|PAST|READY|MISSING|MENTIONED|PREPARED|EXPERIENCE|WAITING)\b/g) ?? []);
  check(!raw.length, `${label}: no raw enum labels (${[...new Set(raw)].join(", ")})`);
  // Keyboard pass: tag every visible focusable, Tab through, compare.
  const total = await page.evaluate(() => {
    const els = [...document.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]")]
      .filter((el) => el.checkVisibility() && el.getAttribute("tabindex") !== "-1");
    els.forEach((el, i) => { el.dataset.qaId = String(i); });
    return els.length;
  });
  await resetFocus(page);
  const reached = new Set();
  const noRing = [];
  let last;
  for (let i = 0; i < total + 20; i++) {
    await page.keyboard.press("Tab");
    const a = await active(page);
    if (!a || a.id === undefined || a.id === last) continue; // date/time fields tab through their own segments
    if (reached.has(a.id)) break;
    last = a.id;
    reached.add(a.id);
    if (!a.ring) noRing.push(`${a.tag}"${a.text}"`);
  }
  const missed = await page.evaluate((ids) => [...document.querySelectorAll("[data-qa-id]")].filter((el) => !ids.includes(el.dataset.qaId)).map((el) => el.outerHTML.slice(0, 120)), [...reached]);
  check(!missed.length, `${label}: Tab reaches all ${total} interactive elements; missed: ${missed.join(" | ")}`);
  check(!noRing.length, `${label}: visible focus ring on every element ${noRing.join(", ")}`);
}

const browser = await chromium.launch();
const shots = [];
const shot = async (page, name) => {
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  shots.push(file);
};
// The upcoming brief has nothing to submit; Edit details is deliberately secondary.
const EXPECTED_PRIMARY = { list: 1, "brief-upcoming": 0, "brief-past": 1, "brief-past-debriefed": 1 };

for (const width of [1280, 375]) {
  for (const screen of Object.keys(EXPECTED_PRIMARY)) {
    const label = `${screen}@${width}`;
    const { context, page, errors } = await openScreen(browser, screen, width);
    await shot(page, label);
    await staticChecks(page, label, width, EXPECTED_PRIMARY[screen]);

    if (screen === "list") {
      await resetFocus(page);
      check(Boolean(await tabTo(page, (a) => a.tag === "INPUT")), `${label}: date field reachable by Tab`);
      await page.keyboard.type("01102026");
      await page.keyboard.press("ArrowRight");
      await page.keyboard.type("0930");
      const value = await page.locator('input[type="datetime-local"]').inputValue();
      check(value === "2026-10-01T09:30", `${label}: date typed by keyboard (${value})`);
      await tabTo(page, (a) => a.tag === "SELECT", 8); // round
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("Tab"); // company
      await page.keyboard.type("Keyboard Ltd");
      await page.keyboard.press("Enter");
      const added = page.locator(`${sec("interviews-upcoming")} li`, { hasText: "Keyboard Ltd" });
      await added.waitFor({ timeout: 5000 }).catch(() => undefined);
      check((await added.count()) === 1, `${label}: added interview appears under Coming up`);
      check((await page.locator('input[type="datetime-local"]').inputValue()) === "", `${label}: add form cleared`);
      const status = (await page.locator(`${sec("interviews-add")} [role=status]`).allInnerTexts()).join(" ");
      check(/added/i.test(status), `${label}: adding is announced (status: "${status}")`);
      await resetFocus(page);
      const before = await page.locator(".dh-row-list li").count();
      check(Boolean(await tabTo(page, (a) => a.text === "Remove")), `${label}: Remove reachable`);
      await page.keyboard.press("Enter");
      await page.waitForFunction((n) => document.querySelectorAll(".dh-row-list li").length === n - 1, before, { timeout: 5000 }).catch(() => undefined);
      check((await page.locator(".dh-row-list li").count()) === before - 1, `${label}: Remove by keyboard removes the row`);
      await shot(page, `${label}-after-add-remove`);
    }

    if (screen.startsWith("brief-past")) {
      await resetFocus(page);
      check(Boolean(await tabTo(page, (a) => a.text === "Edit details")), `${label}: Edit details reachable`);
      await page.keyboard.press("Enter");
      await page.locator(sec("interview-edit")).waitFor();
      const focused = await active(page);
      check(focused?.tag === "INPUT", `${label}: edit opens with focus in the date field (${focused?.tag})`);
      const editingPrimaries = await countPrimary(page);
      check(editingPrimaries === 1, `${label}: one filled primary while editing (found ${editingPrimaries})`);
      await shot(page, `${label}-editing`);
      await tabTo(page, (a) => a.tag === "SELECT", 8); // round
      await page.keyboard.press("ArrowUp");
      await page.keyboard.press("Tab"); // company
      await page.keyboard.press("Control+A");
      await page.keyboard.type("Edited Co");
      await tabTo(page, (a) => a.text === "Save details", 5);
      await page.keyboard.press("Enter");
      await page.locator(sec("interview-edit")).waitFor({ state: "detached", timeout: 5000 }).catch(() => undefined);
      await page.waitForTimeout(150);
      const back = await active(page);
      check(back?.text === "Edit details", `${label}: focus returns to Edit details (${back?.text})`);
      check((await page.locator('[role="status"]', { hasText: "Details saved." }).count()) === 1, `${label}: "Details saved." announced`);
      check((await page.locator(".dh-page-header").innerText()).includes("Edited Co"), `${label}: header shows edited company`);

      check(Boolean(await tabTo(page, (a) => a.tag === "TEXTAREA")), `${label}: debrief questions reachable`);
      await page.keyboard.press("Control+A");
      await page.keyboard.type("How do you reconcile?");
      await page.keyboard.press("Enter");
      await page.keyboard.type("Why this company?");
      check(Boolean(await tabTo(page, (a) => a.text === "Save how it went", 10)), `${label}: Save how it went reachable`);
      await page.keyboard.press("Enter");
      await page.locator(`${sec("debrief-follow-ups")} li`, { hasText: "How do you reconcile?" }).waitFor({ timeout: 5000 }).catch(() => undefined);
      check((await page.locator(`${sec("debrief-follow-ups")} li`).count()) === 2, `${label}: follow-ups appear for each question`);
      check((await page.locator(`${sec("debrief-follow-ups")} a`).count()) === 1, `${label}: follow-up action link shown`);
      check((await page.locator('[role="status"]', { hasText: /^Saved\.$/ }).count()) === 1, `${label}: "Saved." announced`);
      await shot(page, `${label}-after-debrief`);
    }

    if (screen === "brief-upcoming") check((await page.locator(sec("debrief")).count()) === 0, `${label}: no debrief form before the interview`);

    const real = errors.filter((e) => !/Download the React DevTools/.test(e));
    check(!real.length, `${label}: no console errors ${real.join(" | ").slice(0, 400)}`);
    await context.close();
  }
}
await browser.close();
console.log(`\nScreenshots:\n${shots.join("\n")}`);
console.log(failures.length ? `\n${failures.length} FAILED` : "\nAll checks passed");
process.exit(failures.length ? 1 : 0);
