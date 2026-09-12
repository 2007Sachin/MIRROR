"use client";

import { ArrowRight, Briefcase, MagnifyingGlass, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/workspace/app-shell";
import { ApiError, mirrorApi, type DashboardDiagnostic, type Profile } from "@/lib/api";

export function RoleExplorer() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [diagnostics, setDiagnostics] = useState<DashboardDiagnostic[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
      setError("Mirror could not restore your role history. You can still begin a new diagnostic.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const roles = useMemo(() => {
    const seen = new Set<string>();
    return diagnostics.filter((diagnostic) => {
      const key = diagnostic.target_role.trim().toLocaleLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 6);
  }, [diagnostics]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const role = query.trim();
    if (!role) return;
    router.push(`/sessions/new?role=${encodeURIComponent(role)}`);
  }

  return (
    <AppShell profile={profile}>
      <header className="workspace-route-header is-stacked">
        <div><p className="app-kicker">Role explorer</p><h1 className="display">Explore roles with clarity</h1><p>Understand what different roles demand and see how your experience can be tested against them.</p></div>
      </header>

      <form className="role-search" onSubmit={submit}>
        <MagnifyingGlass size={21} aria-hidden="true" />
        <label className="sr-only" htmlFor="role-search-input">Role to explore</label>
        <input id="role-search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search or enter a role, for example Product Manager" />
        <button type="submit" disabled={!query.trim()}>Start diagnostic <ArrowRight size={16} /></button>
      </form>

      {error ? <div className="app-inline-alert" role="alert"><WarningCircle size={18} /><span>{error}</span><button type="button" onClick={() => void load()}>Retry</button></div> : null}

      <section className="role-history" aria-labelledby="role-history-title">
        <div className="app-section-heading"><div><h2 id="role-history-title">Roles you&apos;ve explored</h2><p>Based only on your existing Mirror diagnostics.</p></div></div>
        {loading ? <div className="workspace-list-skeleton"><i /><i /><i /></div> : null}
        {!loading && !roles.length ? (
          <div className="workspace-route-empty app-panel"><h2>No role benchmarks yet.</h2><p>Enter a role above to start building a benchmark with real role context.</p></div>
        ) : (
          <div className="role-card-grid">
            {roles.map((diagnostic) => (
              <article key={diagnostic.id} className="app-panel">
                <span><Briefcase size={20} /></span>
                <div><p>Previously tested role</p><h3>{diagnostic.target_role}</h3><small>{diagnostic.company || "No company specified"}</small></div>
                <Link href={`/sessions/new?role=${encodeURIComponent(diagnostic.target_role)}`}>Start a new diagnostic <ArrowRight size={15} /></Link>
              </article>
            ))}
          </div>
        )}
      </section>
    </AppShell>
  );
}
