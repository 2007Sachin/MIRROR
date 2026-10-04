export type OnboardingRoundDocuments = {
  onboarding_role_profile_id: string | null;
  onboarding_resume_document_id: string | null;
  onboarding_role_brief_document_id: string | null;
};

export function documentsForRoundRole(
  targetRoleProfileId: string | null | undefined,
  onboarding: OnboardingRoundDocuments,
): string[] {
  if (!targetRoleProfileId || targetRoleProfileId !== onboarding.onboarding_role_profile_id) return [];
  return [onboarding.onboarding_resume_document_id, onboarding.onboarding_role_brief_document_id]
    .filter((value): value is string => Boolean(value));
}
