// The review's "what came through" grouping and quote times: backend values only, nothing invented.
import test from "node:test";
import assert from "node:assert/strict";

const { claimGroups, timecode } = await import(new URL("../src/lib/review-groups.ts", import.meta.url).href);

const empty = { held: [], partially_held: [], walked_back: [], contradicted: [], insufficient_evidence: [], unverified: [] };
const claim = (id) => ({ id, claim_text: id, source: "SPOKEN", status: "CORROBORATED", explanation: "", evidence: [], confidence: 0.5 });

test("groups keep the backend's order, drop empty groups and keep 'not enough to say yet'", () => {
  const report = { claims_audit: { ...empty, insufficient_evidence: [claim("c")], held: [claim("a")], contradicted: [claim("b")] } };
  assert.deepEqual(claimGroups(report).map((group) => group.key), ["held", "contradicted", "insufficient_evidence"]);
  assert.deepEqual(claimGroups({ claims_audit: empty }), []);
  assert.deepEqual(claimGroups(null), []);
});

test("timecodes format as m:ss and stay absent when the backend recorded none", () => {
  assert.equal(timecode(74000), "1:14");
  assert.equal(timecode(5000), "0:05");
  assert.equal(timecode(null), null);
  assert.equal(timecode(-1), null);
});
