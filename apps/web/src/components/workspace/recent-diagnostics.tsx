import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";

import type { DashboardDiagnostic } from "@/lib/api";
import {
  diagnosticDestination,
  diagnosticStatus,
  diagnosticTone,
  formatWorkspaceDate,
} from "@/components/workspace/workspace-utils";

export function RecentDiagnostics({ diagnostics }: { diagnostics: DashboardDiagnostic[] }) {
  return (
    <section className="dashboard-recent app-panel" aria-labelledby="recent-diagnostics-title">
      <div className="app-section-heading is-split">
        <div>
          <h2 id="recent-diagnostics-title">Recent diagnostics</h2>
          <p>Revisit past roles and findings.</p>
        </div>
        <Link href="/diagnostics">View all <ArrowRight size={14} /></Link>
      </div>
      {diagnostics.length ? (
        <div className="diagnostic-row-list">
          {diagnostics.slice(0, 3).map((diagnostic) => (
            <Link key={diagnostic.id} href={diagnosticDestination(diagnostic)}>
              <div>
                <strong>{diagnostic.target_role}</strong>
                <span>{diagnostic.company || "General diagnostic"}</span>
              </div>
              <time dateTime={diagnostic.completed_at || diagnostic.updated_at}>
                {formatWorkspaceDate(diagnostic.completed_at || diagnostic.updated_at)}
              </time>
              <span className={`diagnostic-state is-${diagnosticTone(diagnostic)}`}><i aria-hidden="true" />{diagnosticStatus(diagnostic)}</span>
              <ArrowRight size={15} />
            </Link>
          ))}
        </div>
      ) : (
        <p className="app-empty-copy">Completed and in-progress diagnostics will appear here.</p>
      )}
    </section>
  );
}
