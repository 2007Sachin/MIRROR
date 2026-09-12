export default function OnboardingLoading() {
  return (
    <main className="onboarding-workspace">
      <section className="onboarding-main">
        <div className="onboarding-progress" aria-hidden="true">
          <span>Diagnostic context</span><span>Restoring</span><div><span style={{ transform: "scaleX(.12)" }} /></div>
        </div>
        <div className="onboarding-restore" role="status">
          <p className="onboarding-eyebrow">Returning to your work</p>
          <h1>Restoring your diagnostic context.</h1>
          <p>Mirror is retrieving the role benchmark, starting evidence, and last completed stage.</p>
        </div>
      </section>
      <aside className="diagnostic-panel" aria-hidden="true">
        <div className="diagnostic-panel-body">
          <p className="diagnostic-kicker">Mirror is building</p>
          <h2>Your diagnostic</h2>
        </div>
      </aside>
    </main>
  );
}
