import "@/styles/workspace.css";

export function WorkspaceUnavailable() {
  return (
    <main id="main-content" className="app-shell ws-unavailable-page">
      <section className="fade-in-once">
        <p className="ws-eyebrow">Workspace unavailable</p>
        <h1 className="display">Mirror could not restore your evidence workspace.</h1>
        <p>Your completed interviews remain saved. Refresh this page to try the secure connection again.</p>
      </section>
    </main>
  );
}
