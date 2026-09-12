import { redirect } from "next/navigation";
import { OnboardingFlow } from "@/components/onboarding-flow";
import { getServerOnboarding } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") {
    return (
      <main className="onboarding-workspace">
        <section className="onboarding-main">
          <div className="onboarding-restore">
            <p className="onboarding-eyebrow">Diagnostic unavailable</p>
            <h1>Mirror could not restore your saved context.</h1>
            <p role="alert">Your completed work has not been removed. Refresh the page to try the secure connection again.</p>
          </div>
        </section>
        <aside className="diagnostic-panel" aria-hidden="true"><div className="diagnostic-panel-body"><p className="diagnostic-kicker">Mirror is building</p><h2>Your diagnostic</h2></div></aside>
      </main>
    );
  }

  const { onboarding } = result;
  if (onboarding.onboarding_completed) redirect("/dashboard");
  return <OnboardingFlow initialOnboarding={onboarding} />;
}

