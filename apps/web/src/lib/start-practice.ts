/**
 * Starting a practice, in one place.
 *
 * A practice can only be created directly when the role that is already set up is
 * the role being practised: the planner works from the role profile the account
 * currently points at, so any other role goes through the full setup flow instead.
 * Nothing here plans or changes a conversation; it calls the same endpoints the
 * setup flow has always called, in the same order.
 */
import { mirrorApi, type Onboarding, type PracticeChoice } from "@/lib/api";

export function canStartDirectly(role: string, onboarding: Onboarding) {
  const wanted = role.trim().toLocaleLowerCase();
  if (!wanted || onboarding.target_role?.trim().toLocaleLowerCase() !== wanted) return false;
  return Boolean(onboarding.onboarding_resume_document_id && onboarding.onboarding_role_profile_id);
}

/**
 * Creates a prepared practice for the role that is already set up. A focused practice or
 * quick drill is planned on the server from fixed questions, so preparing it is quick.
 */
export async function createPractice(role: string, onboarding: Onboarding, choice?: PracticeChoice, roleProfileId?: string | null, idempotencyKey?: string, storyIds?: string[]): Promise<string> {
  const resumeId = onboarding.onboarding_resume_document_id;
  if (!resumeId) throw new Error("no resume is set up for this role");
  // Pass the role explicitly rather than relying on it matching the account's
  // current role: the session should stay bound to this specific role even if
  // the account's current role changes later.
  // Chosen stories are pinned by the server at their current version; the plan uses exactly those.
  const session = await mirrorApi.createSession(role, "", choice, roleProfileId ?? onboarding.onboarding_role_profile_id, idempotencyKey, storyIds);
  const documentIds = [resumeId, onboarding.onboarding_role_brief_document_id].filter(
    (value): value is string => Boolean(value),
  );
  await mirrorApi.linkSessionDocuments(session.id, documentIds);
  await mirrorApi.prepare(session.id);
  return session.id;
}
