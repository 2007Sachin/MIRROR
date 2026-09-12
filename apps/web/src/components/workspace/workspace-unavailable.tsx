export function WorkspaceUnavailable() {
  return (
    <main className="workspace-unavailable-page">
      <section>
        <p className="app-kicker">Workspace unavailable</p>
        <h1 className="display">Mirror could not restore your evidence workspace.</h1>
        <p>Your completed interviews remain saved. Refresh this page to try the secure connection again.</p>
      </section>
    </main>
  );
}
