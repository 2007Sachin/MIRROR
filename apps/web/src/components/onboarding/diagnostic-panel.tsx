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
      <p className="ob-diagnostic-kicker">Mirror is learning</p>
      <h2>Diagnostic context</h2>

      <dl className="ob-diagnostic-context">
        <div>
          <dt>Benchmark</dt>
          <dd>{targetRole || "Waiting for a target role"}</dd>
        </div>
        {targetCompany && (
          <div>
            <dt>Opportunity</dt>
            <dd>{targetCompany}</dd>
          </div>
        )}
        {resumeName && (
          <div>
            <dt>Starting evidence</dt>
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
          ? "The inquiry plan is ready."
          : "Each input changes what Mirror can investigate next.")}
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
      label: targetRole ? "Role identified" : "Role benchmark",
      state: roleReady ? "complete" : step === 1 ? "active" : "waiting",
    },
    {
      label: roleBriefSkipped ? "Role expectations inferred" : "Role brief analysed",
      state: roleReady ? "complete" : roleBriefReady ? "active" : "waiting",
    },
    {
      label: "Evidence mapping",
      state: evidenceReady ? "complete" : step === 2 && Boolean(resumeName) ? "active" : "waiting",
    },
    {
      label: "Evidence gaps",
      state: step >= 3 && evidenceReady ? "complete" : step === 3 ? "active" : "waiting",
    },
    {
      label: "Lines of inquiry",
      state: sessionReady ? "complete" : step === 4 ? "active" : "waiting",
    },
    {
      label: "Interview thesis",
      state: sessionReady ? "complete" : step === 5 ? "active" : "waiting",
    },
  ];

  return (
    <aside className="ob-diagnostic" aria-label="What Mirror is building">
      <div className="ob-diagnostic-desktop">
        <DiagnosticBody rows={rows} targetRole={targetRole} targetCompany={targetCompany} resumeName={resumeName} sessionReady={sessionReady} busyLabel={busyLabel} />
      </div>
      <details className="ob-diagnostic-mobile">
        <summary><span>Diagnostic context</span><span>{step} of 5</span></summary>
        <DiagnosticBody rows={rows} targetRole={targetRole} targetCompany={targetCompany} resumeName={resumeName} sessionReady={sessionReady} busyLabel={busyLabel} />
      </details>
    </aside>
  );
}
