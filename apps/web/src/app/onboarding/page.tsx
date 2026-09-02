import { redirect } from "next/navigation";
import { OnboardingFlow } from "@/components/onboarding-flow";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") {
    return (
      <main className="shell py-20">
        <p role="alert" className="text-sm text-[var(--silver)]">Mirror could not load your saved setup. Refresh to try again.</p>
      </main>
    );
  }

  const { onboarding } = result;
  if (onboarding.onboarding_completed) redirect("/app");
  return <OnboardingFlow initialOnboarding={onboarding} />;
}

