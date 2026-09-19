"use client";

import { ArrowRight, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/workspace/app-shell";
import { Reveal } from "@/components/motion/reveal";
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
      <header className="ws-page-header">
        <div><p className="ws-eyebrow">Diagnostic record</p><h1 className="display">Your diagnostics</h1><p>A record of the roles you&apos;ve tested, what you&apos;ve learned, and how your readiness has evolved.</p></div>
        <Link className="button-primary" href="/sessions/new">Start new <ArrowRight size={17} /></Link>
      </header>

      <div className="ws-tabs" role="tablist" aria-label="Filter diagnostics">
        {(["all", "progress", "completed"] as const).map((value) => (
          <button key={value} type="button" role="tab" aria-selected={filter === value} onClick={() => setFilter(value)}>
            {value === "all" ? "All" : value === "progress" ? "In progress" : "Completed"}
          </button>
        ))}
      </div>

      {error ? <div className="ws-alert is-inline" role="alert"><WarningCircle size={18} /><span>{error}</span><button type="button" onClick={() => void load()}>Retry</button></div> : null}

      <Reveal>
        <section className="diagnostics-index ws-panel" aria-live="polite">
          {loading ? <div className="ws-list-skeleton"><i className="skeleton" /><i className="skeleton" /><i className="skeleton" /></div> : null}
          {!loading && !visible.length ? (
            <div className="ws-empty"><h2>No diagnostics here yet.</h2><p>Start a diagnostic to test your evidence against a role.</p><Link href="/sessions/new">Start a diagnostic <ArrowRight size={15} /></Link></div>
          ) : null}
          {!loading && visible.length ? (
            <div className="ws-row-list reveal-stagger is-visible">
              {visible.map((diagnostic) => (
                <article key={diagnostic.id} className="ws-diagnostic-row">
                  <Link href={diagnosticDestination(diagnostic)} className="ws-diagnostic-link" aria-label={`Open ${diagnostic.target_role} diagnostic`}>
                    <div className="ws-row-main"><strong>{diagnostic.target_role}</strong><span>{diagnostic.company || "General diagnostic"}</span></div>
                    <time dateTime={diagnostic.completed_at || diagnostic.updated_at}>{formatWorkspaceDate(diagnostic.completed_at || diagnostic.updated_at)}</time>
                    <span className={`ws-status-chip is-${diagnosticTone(diagnostic)}`}><i aria-hidden="true" />{diagnosticStatus(diagnostic)}</span>
                    <ArrowRight size={16} />
                  </Link>
                  {diagnostic.assessment?.status === "FAILED" ? (
                    <div className="ws-row-actions">
                      <button type="button" onClick={() => void retry(diagnostic)} disabled={retrying === diagnostic.id}>
                        {retrying === diagnostic.id ? "Retrying..." : "Retry evaluation"}
                      </button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : null}
        </section>
      </Reveal>
    </AppShell>
  );
}
