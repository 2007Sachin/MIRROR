// Collects page errors, console errors and failed/bad network requests, then applies a documented allow-list.

/** Every entry says WHY it is tolerated. Anything not matched here fails the run. */
export const ALLOW = [
  {
    kind: "response", url: /\/auth\/v1\/token/, status: 400, steps: ["login-wrong-password"],
    reason: "intentional negative sign-in: the fake auth service answers invalid_credentials",
  },
  {
    kind: "console", text: /status of 400/, steps: ["login-wrong-password"],
    reason: "Chrome logs the intentional 400 above as a console error",
  },
  {
    kind: "failed", url: /[?&]_rsc=/, error: /ERR_ABORTED/,
    reason: "Next cancels in-flight RSC prefetch/refresh requests when a client navigation supersedes them",
  },
  // Loop 2 target journeys (tests/target-journeys.mjs): deliberate scenario answers, one step each.
  {
    kind: "response", url: /\/api\/v1\/targets\/[^/]+\/blueprint$/, status: 503, steps: ["t06-plan-section-unavailable"],
    reason: "scenario unavailable503: target tables missing on this host; the plan section must stay quiet",
  },
  {
    kind: "response", url: /\/api\/v1\/targets\/[^/]+\/blueprint$/, status: 500, steps: ["t07-plan-section-error-and-retry"],
    reason: "scenario error500: the section shows its own alert and recovers on retry",
  },
  {
    kind: "response", url: /\/api\/v1\/targets\/[^/]+\/rounds\/not_a_round$/, status: 404, steps: ["t11-round-unknown-key"],
    reason: "an unknown round key renders the not-found message",
  },
  {
    kind: "console", text: /status of (503|500|404)/,
    steps: ["t06-plan-section-unavailable", "t07-plan-section-error-and-retry", "t11-round-unknown-key"],
    reason: "Chrome logs the deliberate answers above as console errors",
  },
  {
    kind: "response", method: "PUT", url: /\/api\/v1\/targets\/[^/]+\/blueprint\/stages$/, status: 409,
    steps: ["t02b-stage-practice-review-and-stage-removal"],
    reason: "the stale_once scenario returns STAGE_PLAN_STALE so candidate draft reconciliation is verified",
    consoleText: /status of 409 \(Conflict\)/,
  },
  // Loop 3 journey B: a business-roles target has no engineering rounds; asking for one is a deliberate 404.
  {
    kind: "response", url: /\/api\/v1\/targets\/[^/]+\/rounds\/coding_reasoning$/, status: 404, steps: ["t18-business-roles-round-detail"],
    reason: "an engineering round key on a business-roles target renders the not-found message",
  },
  {
    kind: "console", text: /^Failed to load resource: the server responded with a status of 404 \(Not Found\)$/,
    steps: ["t18-business-roles-round-detail"],
    reason: "Chrome logs the deliberate T18 404 as a console error",
  },
  {
    kind: "response", url: /\/api\/v1\/targets$/, status: 503,
    steps: ["t16-onboarding-continues-with-general-plan-without-target"],
    reason: "target creation is deliberately unavailable in T16; the candidate continues with the general plan",
  },
  {
    kind: "console", text: /^Failed to load resource: the server responded with a status of 503 \(Service Unavailable\)$/,
    steps: ["t16-onboarding-continues-with-general-plan-without-target"],
    reason: "Chrome logs the intentional T16 target-create 503 as a console error",
  },
];

export function createCollector() {
  const bag = { step: "start", pageErrors: [], consoleErrors: [], consoleWarnings: [], failed: [], responses: [], counts: { requests: 0 } };
  const consoleTimes = new WeakMap();
  const responseTimes = new WeakMap();
  return {
    bag,
    setStep(name) {
      bag.step = name;
    },
    attach(page) {
      page.on("pageerror", (error) => bag.pageErrors.push({ step: bag.step, url: page.url(), text: String(error?.stack ?? error).slice(0, 400) }));
      page.on("console", (message) => {
        const entry = { step: bag.step, url: page.url(), text: message.text().slice(0, 300) };
        consoleTimes.set(entry, Date.now());
        if (message.type() === "error") bag.consoleErrors.push(entry);
        else if (message.type() === "warning") bag.consoleWarnings.push(entry);
      });
      page.on("request", () => {
        bag.counts.requests += 1;
      });
      page.on("requestfailed", (request) =>
        bag.failed.push({ step: bag.step, url: request.url(), method: request.method(), error: request.failure()?.errorText ?? "" }));
      page.on("response", (response) => {
        if (response.status() >= 400) {
          const request = response.request?.();
          const entry = { step: bag.step, url: response.url(), status: response.status(), method: request?.method?.() };
          responseTimes.set(entry, Date.now());
          bag.responses.push(entry);
        }
      });
    },
    /** Returns only what is NOT covered by the allow-list. */
    findings() {
      const matches = (rule, kind, fields) =>
        rule.kind === kind
        && (!rule.steps || rule.steps.includes(fields.step))
        && (!rule.url || rule.url.test(fields.url ?? ""))
        && (!rule.text || rule.text.test(fields.text ?? ""))
        && (!rule.status || rule.status === fields.status)
        && (!rule.method || rule.method === fields.method)
        && (!rule.error || rule.error.test(fields.error ?? ""));
      const allowed = (kind, fields) => ALLOW.some((rule) => matches(rule, kind, fields));
      const pairedResponses = new Set();
      const consoleMatchesAllowedResponse = (entry) => {
        const at = consoleTimes.get(entry) ?? 0;
        for (const rule of ALLOW) {
          if (rule.kind !== "response" || !rule.consoleText?.test(entry.text)
            || (rule.steps && !rule.steps.includes(entry.step))) continue;
          const response = bag.responses.find((candidate) => {
            const responseAt = responseTimes.get(candidate) ?? Number.NEGATIVE_INFINITY;
            return !pairedResponses.has(candidate) && matches(rule, "response", candidate)
              && Math.abs(at - responseAt) <= 2_000;
          });
          if (response) { pairedResponses.add(response); return true; }
        }
        return false;
      };
      return {
        pageErrors: bag.pageErrors,
        consoleErrors: bag.consoleErrors.filter((entry) => !allowed("console", entry) && !consoleMatchesAllowedResponse(entry)),
        failedRequests: bag.failed.filter((entry) => !allowed("failed", entry)),
        badResponses: bag.responses.filter((entry) => !allowed("response", entry)),
      };
    },
  };
}
