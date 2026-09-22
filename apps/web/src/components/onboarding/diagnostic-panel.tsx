import { Check, Circle, SpinnerGap } from "@phosphor-icons/react";

type BuildState = "complete" | "active" | "waiting";

type DiagnosticPanelProps = {
  step: number;
  targetRole: string;
  targetCompany: string;
  roleBriefReady: boolean;
  roleBriefSkipped: boolean;
  resumeName: string;
  evidenceReady: boolean;
  roleReady: boolean;
  sessionReady: boolean;
  busyLabel?: string;
};

function BuildMark({ state }: { state: BuildState }) {
  if (state === "complete") return <Check size={15} weight="bold" aria-hidden="true" />;
  if (state === "active") return <SpinnerGap size={15} aria-hidden="true" />;
  return <Circle size={10} aria-hidden="true" />;
}

function DiagnosticBody({
  rows,
  targetRole,
  targetCompany,
  resumeName,
  sessionReady,
  busyLabel,
}: {
  rows: Array<{ label: string; state: BuildState }>;
  targetRole: string;
  targetCompany: string;
  resumeName: string;
  sessionReady: boolean;
  busyLabel?: string;
}) {
  return (
    <div className="ob-diagnostic-body">
      <p className="ob-diagnostic-kicker">Mirror is getting to know you</p>
      <h2>Your session so far</h2>

      <dl className="ob-diagnostic-context">
        <div>
          <dt>Target role</dt>
          <dd>{targetRole || "Waiting for your target role"}</dd>
        </div>
        {targetCompany && (
          <div>
            <dt>Opportunity</dt>
            <dd>{targetCompany}</dd>
          </div>
        )}
        {resumeName && (
          <div>
            <dt>Your resume</dt>
            <dd>{resumeName}</dd>
          </div>
        )}
      </dl>

      <ol className="ob-diagnostic-list">
        {rows.map((row) => (
          <li key={row.label} data-state={row.state}>
            <span className="ob-diagnostic-mark"><BuildMark state={row.state} /></span>
            <span>{row.label}</span>
            <span className="sr-only">{row.state}</span>
          </li>
        ))}
      </ol>

      <p className="ob-diagnostic-live" aria-live="polite">
        {busyLabel || (sessionReady
          ? "Your conversation plan is ready."
          : "Each thing you share helps shape your questions.")}
      </p>
    </div>
  );
}

export function DiagnosticPanel({
  step,
  targetRole,
  targetCompany,
  roleBriefReady,
  roleBriefSkipped,
  resumeName,
  evidenceReady,
  roleReady,
  sessionReady,
  busyLabel,
}: DiagnosticPanelProps) {
  const rows: Array<{ label: string; state: BuildState }> = [
    {
      label: targetRole ? "Role identified" : "Your target role",
      state: roleReady ? "complete" : step === 1 ? "active" : "waiting",
    },
    {
      label: roleBriefSkipped ? "Role expectations noted" : "Role brief read",
      state: roleReady ? "complete" : roleBriefReady ? "active" : "waiting",
    },
    {
      label: "Your experience at a glance",
      state: evidenceReady ? "complete" : step === 2 && Boolean(resumeName) ? "active" : "waiting",
    },
    {
      label: "What to explore",
      state: step >= 3 && evidenceReady ? "complete" : step === 3 ? "active" : "waiting",
    },
    {
      label: "Areas to explore",
      state: sessionReady ? "complete" : step === 4 ? "active" : "waiting",
    },
    {
      label: "Your conversation plan",
      state: sessionReady ? "complete" : step === 5 ? "active" : "waiting",
    },
  ];

  return (
    <aside className="ob-diagnostic" aria-label="What Mirror is building">
      <div className="ob-diagnostic-desktop">
        <DiagnosticBody rows={rows} targetRole={targetRole} targetCompany={targetCompany} resumeName={resumeName} sessionReady={sessionReady} busyLabel={busyLabel} />
      </div>
      <details className="ob-diagnostic-mobile">
        <summary><span>Your session so far</span><span>{step} of 5</span></summary>
        <DiagnosticBody rows={rows} targetRole={targetRole} targetCompany={targetCompany} resumeName={resumeName} sessionReady={sessionReady} busyLabel={busyLabel} />
      </details>
    </aside>
  );
}
