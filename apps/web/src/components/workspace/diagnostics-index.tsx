"use client";

import { ArrowRight, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/workspace/app-shell";
import {
  diagnosticDestination,
  diagnosticStatus,
  diagnosticTone,
  formatWorkspaceDate,
} from "@/components/workspace/workspace-utils";
import { ApiError, mirrorApi, type DashboardDiagnostic, type Profile } from "@/lib/api";

type DiagnosticFilter = "all" | "progress" | "completed";

export function DiagnosticsIndex() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [diagnostics, setDiagnostics] = useState<DashboardDiagnostic[]>([]);
  const [filter, setFilter] = useState<DiagnosticFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState<string | null>(null);

  async function load() {
    setError("");
    try {
      const [workspace, nextProfile] = await Promise.all([mirrorApi.dashboard(), mirrorApi.me()]);
      setProfile(nextProfile);
      setDiagnostics(workspace.current ? [workspace.current, ...workspace.previous] : workspace.previous);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        router.replace("/login?reason=session_expired");
        return;
      }
      setError("Mirror could not load your diagnostics. Your saved interviews have not been removed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const visible = useMemo(() => diagnostics.filter((diagnostic) => {
    if (filter === "completed") return diagnostic.diagnostic_available;
    if (filter === "progress") return !diagnostic.diagnostic_available && diagnostic.assessment?.status !== "FAILED";
    return true;
  }), [diagnostics, filter]);

  async function retry(diagnostic: DashboardDiagnostic) {
    setRetrying(diagnostic.id);
    setError("");
    try {
      await mirrorApi.retryAssessment(diagnostic.id);
      await load();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Mirror could not retry this evaluation.");
    } finally {
      setRetrying(null);
    }
  }

  return (
    <AppShell profile={profile}>
      <header className="workspace-route-header">
        <div><p className="app-kicker">Diagnostic record</p><h1 className="display">Your diagnostics</h1><p>A record of the roles you&apos;ve tested, what you&apos;ve learned, and how your readiness has evolved.</p></div>
        <Link className="app-primary-button" href="/sessions/new">Start new <ArrowRight size={17} /></Link>
      </header>

      <div className="workspace-tabs" role="tablist" aria-label="Filter diagnostics">
        {(["all", "progress", "completed"] as const).map((value) => (
          <button key={value} type="button" role="tab" aria-selected={filter === value} onClick={() => setFilter(value)}>
            {value === "all" ? "All" : value === "progress" ? "In progress" : "Completed"}
          </button>
        ))}
      </div>

      {error ? <div className="app-inline-alert" role="alert"><WarningCircle size={18} /><span>{error}</span><button type="button" onClick={() => void load()}>Retry</button></div> : null}

      <section className="diagnostics-index app-panel" aria-live="polite">
        {loading ? <div className="workspace-list-skeleton"><i /><i /><i /></div> : null}
        {!loading && !visible.length ? (
          <div className="workspace-route-empty"><h2>No diagnostics here yet.</h2><p>Start a diagnostic to test your evidence against a role.</p><Link href="/sessions/new">Start a diagnostic <ArrowRight size={15} /></Link></div>
        ) : null}
        {visible.map((diagnostic) => (
          <article key={diagnostic.id} className="diagnostics-index-row">
            <Link href={diagnosticDestination(diagnostic)} aria-label={`Open ${diagnostic.target_role} diagnostic`}>
              <div><strong>{diagnostic.target_role}</strong><span>{diagnostic.company || "General diagnostic"}</span></div>
              <time dateTime={diagnostic.completed_at || diagnostic.updated_at}>{formatWorkspaceDate(diagnostic.completed_at || diagnostic.updated_at)}</time>
              <span className={`diagnostic-state is-${diagnosticTone(diagnostic)}`}><i aria-hidden="true" />{diagnosticStatus(diagnostic)}</span>
              <ArrowRight size={16} />
            </Link>
            {diagnostic.assessment?.status === "FAILED" ? (
              <button type="button" onClick={() => void retry(diagnostic)} disabled={retrying === diagnostic.id}>
                {retrying === diagnostic.id ? "Retrying..." : "Retry evaluation"}
              </button>
            ) : null}
          </article>
        ))}
      </section>
    </AppShell>
  );
}
