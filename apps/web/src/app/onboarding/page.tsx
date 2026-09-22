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
            <p className="ob-eyebrow">Session unavailable for now</p>
            <h1>We couldn't bring back your saved session just now.</h1>
            <p role="alert">Your completed work has not been removed. Please refresh the page to try again.</p>
          </div>
        </section>
        <aside className="ob-diagnostic" aria-hidden="true"><div className="ob-diagnostic-body"><p className="ob-diagnostic-kicker">Mirror is preparing</p><h2>Your session</h2></div></aside>
      </main>
    );
  }

  const { onboarding } = result;
  if (onboarding.onboarding_completed) redirect("/dashboard");
  return <OnboardingFlow initialOnboarding={onboarding} />;
}

