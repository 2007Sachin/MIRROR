import { Loader } from "@/components/loader";
import { loading } from "@/lib/copy";

export default function OnboardingLoading() {
  return (
    <main className="onboarding-workspace">
      <section className="onboarding-main">
        <div className="onboarding-progress" aria-hidden="true">
          <span>Your session</span><span>Getting ready</span><div><span style={{ transform: "scaleX(.12)" }} /></div>
        </div>
        <div className="onboarding-restore">
          <p className="onboarding-eyebrow">Welcome back</p>
          <Loader label={loading.onboarding.label} note={loading.onboarding.note} />
          <p>Mirror is bringing back your target role, your resume, and where you left off.</p>
        </div>
      </section>
      <aside className="diagnostic-panel" aria-hidden="true">
        <div className="diagnostic-panel-body">
          <p className="diagnostic-kicker">Mirror is preparing</p>
          <h2>Your session</h2>
        </div>
      </aside>
    </main>
  );
}
