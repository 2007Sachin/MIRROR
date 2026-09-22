import "@/styles/workspace.css";

export function WorkspaceUnavailable() {
  return (
    <main id="main-content" className="app-shell ws-unavailable-page">
      <section className="fade-in-once">
        <p className="ws-eyebrow">Your space is unavailable for now</p>
        <h1 className="display">We couldn't bring back your space just now.</h1>
        <p>Your completed interviews remain saved. Please refresh this page to try again.</p>
      </section>
    </main>
  );
}
