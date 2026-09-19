import { redirect } from "next/navigation";
import { OnboardingFlow } from "@/components/onboarding-flow";
import { getServerOnboarding } from "@/lib/server-api";
import "@/styles/onboarding.css";

export const dynamic = "force-dynamic";

export default async function OnboardingPage() {
  const result = await getServerOnboarding();
  if (result.status === "unauthenticated") redirect("/login?reason=session_expired");
  if (result.status === "unavailable") {
    return (
      <main id="main-content" className="ob-workspace">
        <section className="ob-main">
          <div className="ob-restore">
            <p className="ob-eyebrow">Diagnostic unavailable</p>
            <h1>Mirror could not restore your saved context.</h1>
            <p role="alert">Your completed work has not been removed. Refresh the page to try the secure connection again.</p>
          </div>
        </section>
        <aside className="ob-diagnostic" aria-hidden="true"><div className="ob-diagnostic-body"><p className="ob-diagnostic-kicker">Mirror is building</p><h2>Your diagnostic</h2></div></aside>
      </main>
    );
  }

  const { onboarding } = result;
  if (onboarding.onboarding_completed) redirect("/dashboard");
  return <OnboardingFlow initialOnboarding={onboarding} />;
}

