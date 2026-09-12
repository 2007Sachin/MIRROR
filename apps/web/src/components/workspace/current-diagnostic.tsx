"use client";

import { ArrowRight, Clock, WarningCircle } from "@phosphor-icons/react";
import dynamic from "next/dynamic";
import Link from "next/link";

import type { DashboardDiagnostic } from "@/lib/api";
import { DiagnosticProgress } from "@/components/workspace/diagnostic-progress";
import {
  diagnosticDestination,
  diagnosticStatus,
  diagnosticTone,
  formatWorkspaceDate,
} from "@/components/workspace/workspace-utils";

const CompactEnergyMesh = dynamic(
  () => import("@/components/auth/animated-energy-mesh").then((module) => module.AnimatedEnergyMesh),
  { ssr: false },
);

function stateCopy(diagnostic: DashboardDiagnostic) {
  if (diagnostic.diagnostic_available) {
    return {
      title: "Your diagnostic is ready",
      copy: "Mirror has finished evaluating your interview against your claims and the expectations of the role.",
      action: "Review findings",
    };
  }
  if (diagnostic.assessment?.status === "FAILED") {
    return {
      title: "We couldn't complete the diagnostic",
      copy: "Your interview has been saved. Mirror couldn't finish evaluating the evidence, so the assessment can be retried without repeating the interview.",
      action: "Retry evaluation",
    };
  }
  if (diagnostic.assessment || diagnostic.interview_status === "ASSESSING" || diagnostic.interview_status === "COMPLETED") {
    return {
      title: "Evaluating evidence",
      copy: "Mirror is analysing your answers, matching them with your claims and role expectations.",
      action: "",
    };
  }
  if (diagnostic.interview_status === "ACTIVE") {
    return {
      title: "Interview in progress",
      copy: "Your evidence interview is underway. Continue the conversation when you're ready.",
      action: "Continue interview",
    };
  }
  if (diagnostic.interview_status === "READY") {
    return {
      title: "Your evidence interview is ready",
      copy: "Mirror has prepared the interview thesis for this role and your available evidence.",
      action: "Begin interview",
    };
  }
  return {
    title: "Continue building your evidence case",
    copy: "Finish the role and evidence setup before starting your evidence interview.",
    action: "Continue setup",
  };
}
export function CurrentDiagnostic({
  diagnostic,
  retrying,
  onRetry,
}: {
  diagnostic: DashboardDiagnostic;
  retrying: boolean;
  onRetry: (id: string) => Promise<void>;
}) {
  const content = stateCopy(diagnostic);
  const failed = diagnostic.assessment?.status === "FAILED";
  const processing = !diagnostic.diagnostic_available
    && !failed
    && Boolean(diagnostic.assessment || diagnostic.interview_status === "ASSESSING" || diagnostic.interview_status === "COMPLETED");
  const date = formatWorkspaceDate(diagnostic.completed_at || diagnostic.updated_at);

  return (
    <section className={`dashboard-current-card is-${diagnosticTone(diagnostic)}`} aria-labelledby="current-diagnostic-title">
      <div className="dashboard-current-content">
        <div className="dashboard-current-heading">
          <div>
            <p className="app-kicker"><i aria-hidden="true" /> Current diagnostic</p>
            <h2 id="current-diagnostic-title" className="display">{diagnostic.target_role}</h2>
            <p className="dashboard-diagnostic-meta">
              {diagnostic.company ? <><span>{diagnostic.company}</span><b aria-hidden="true" /></> : null}
              <span>{date}</span><b aria-hidden="true" /><span>{diagnosticStatus(diagnostic)}</span>
            </p>
          </div>
          <span className={`diagnostic-state is-${diagnosticTone(diagnostic)}`}>
            {failed ? <WarningCircle size={14} /> : <i aria-hidden="true" />}
            {diagnosticStatus(diagnostic)}
          </span>
        </div>

        <div className="dashboard-current-message">
          <div>
            <h3>{content.title}</h3>
            <p>{content.copy}</p>
            {processing ? <small><Clock size={14} /> We&apos;ll notify you as soon as your diagnostic is ready.</small> : null}
          </div>
          {failed ? (
            <button type="button" className="app-primary-button" onClick={() => void onRetry(diagnostic.id)} disabled={retrying}>
              {retrying ? "Requesting retry..." : "Retry evaluation"}<ArrowRight size={17} />
            </button>
          ) : content.action ? (
            <Link className="app-primary-button" href={diagnosticDestination(diagnostic)}>
              {content.action}<ArrowRight size={17} />
            </Link>
          ) : null}
        </div>

        <DiagnosticProgress diagnostic={diagnostic} />
      </div>

      <div className="dashboard-current-visual" aria-label="Turning your experience into evidence">
        <CompactEnergyMesh energized={processing} variant="compact" />
        <p>Turning your experience into evidence.</p>
      </div>
    </section>
  );
}
