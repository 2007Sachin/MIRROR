import { Check } from "@phosphor-icons/react";

import type { DashboardDiagnostic } from "@/lib/api";

export function DiagnosticProgress({ diagnostic }: { diagnostic: DashboardDiagnostic }) {
  const captured = Boolean(
    diagnostic.diagnostic_available
      || diagnostic.assessment
      || diagnostic.completed_at
      || diagnostic.interview_status === "ASSESSING"
      || diagnostic.interview_status === "COMPLETED",
  );
  const evaluating = captured && !diagnostic.diagnostic_available && diagnostic.assessment?.status !== "FAILED";
  const ready = diagnostic.diagnostic_available;
  const stages = [
    { label: "Interview captured", complete: captured, current: false },
    { label: "Evidence being evaluated", complete: ready, current: evaluating },
    { label: "Findings being reconciled", complete: ready, current: false },
    { label: "Diagnostic ready", complete: ready, current: false },
  ];

  return (
    <ol className="diagnostic-progress" aria-label="Diagnostic lifecycle">
      {stages.map((stage, index) => (
        <li key={stage.label} className={stage.complete ? "is-complete" : stage.current ? "is-current" : ""}>
          <span aria-hidden="true">{stage.complete ? <Check size={12} weight="bold" /> : index + 1}</span>
          <p>{stage.label}</p>
        </li>
      ))}
    </ol>
  );
}
