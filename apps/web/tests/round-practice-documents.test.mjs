import test from "node:test";
import assert from "node:assert/strict";

const { documentsForRoundRole } = await import(new URL("../src/lib/round-practice-documents.ts", import.meta.url).href);

test("round practice only carries onboarding documents when target and onboarding roles match", () => {
  const onboarding = {
    onboarding_role_profile_id: "role-a",
    onboarding_resume_document_id: "resume-a",
    onboarding_role_brief_document_id: "brief-a",
  };

  assert.deepEqual(documentsForRoundRole("role-a", onboarding), ["resume-a", "brief-a"]);
  assert.deepEqual(documentsForRoundRole("role-b", onboarding), []);
  assert.deepEqual(documentsForRoundRole(null, onboarding), []);
});
