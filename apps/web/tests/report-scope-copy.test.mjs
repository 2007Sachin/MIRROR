// Candidate-facing copy for a round-scoped practice report.
// Run: "C:/Program Files/nodejs/node" --experimental-strip-types --test apps/web/tests/report-scope-copy.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

const { report } = await import(new URL("../src/lib/copy.ts", import.meta.url).href);

test("scoped practice copy names the round boundary and truthful provenance", () => {
  assert.match(report.scope.body, /this round only/i);
  assert.match(report.scope.body, /not an overall role-readiness result/i);
  assert.match(report.scope.provenance, /Mirror-generated/i);
  assert.match(report.scope.provenance, /not an official employer rubric/i);
  assert.equal(
    report.scope.competencies(["Structured problem solving", "Quantitative reasoning"]),
    "This round looks at Structured problem solving · Quantitative reasoning.",
  );
});
