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
];

export function createCollector() {
  const bag = { step: "start", pageErrors: [], consoleErrors: [], consoleWarnings: [], failed: [], responses: [], counts: { requests: 0 } };
  return {
    bag,
    setStep(name) {
      bag.step = name;
    },
    attach(page) {
      page.on("pageerror", (error) => bag.pageErrors.push({ step: bag.step, url: page.url(), text: String(error?.stack ?? error).slice(0, 400) }));
      page.on("console", (message) => {
        const entry = { step: bag.step, url: page.url(), text: message.text().slice(0, 300) };
        if (message.type() === "error") bag.consoleErrors.push(entry);
        else if (message.type() === "warning") bag.consoleWarnings.push(entry);
      });
      page.on("request", () => {
        bag.counts.requests += 1;
      });
      page.on("requestfailed", (request) =>
        bag.failed.push({ step: bag.step, url: request.url(), method: request.method(), error: request.failure()?.errorText ?? "" }));
      page.on("response", (response) => {
        if (response.status() >= 400) bag.responses.push({ step: bag.step, url: response.url(), status: response.status() });
      });
    },
    /** Returns only what is NOT covered by the allow-list. */
    findings() {
      const allowed = (kind, fields) => ALLOW.some((rule) =>
        rule.kind === kind
        && (!rule.steps || rule.steps.includes(fields.step))
        && (!rule.url || rule.url.test(fields.url ?? ""))
        && (!rule.text || rule.text.test(fields.text ?? ""))
        && (!rule.status || rule.status === fields.status)
        && (!rule.error || rule.error.test(fields.error ?? "")));
      return {
        pageErrors: bag.pageErrors,
        consoleErrors: bag.consoleErrors.filter((entry) => !allowed("console", entry)),
        failedRequests: bag.failed.filter((entry) => !allowed("failed", entry)),
        badResponses: bag.responses.filter((entry) => !allowed("response", entry)),
      };
    },
  };
}
