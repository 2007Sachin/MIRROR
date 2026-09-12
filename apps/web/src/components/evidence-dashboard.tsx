"use client";

import { ArrowRight, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/workspace/app-shell";
import { CurrentDiagnostic } from "@/components/workspace/current-diagnostic";
import { EvidencePreview } from "@/components/workspace/evidence-preview";
import { QuickActions } from "@/components/workspace/quick-actions";
import { RecentDiagnostics } from "@/components/workspace/recent-diagnostics";
import {
  ApiError,
  mirrorApi,
  type DashboardDiagnostic,
  type DashboardResponse,
  type MirrorDocument,
  type Profile,
} from "@/lib/api";

type WorkspaceState = "loading" | "ready" | "error";

const POLL_DELAYS = [3000, 3000, 5000, 5000, 8000, 8000, 12000, 15000] as const;

function assessmentIsPending(diagnostic: DashboardDiagnostic | null) {
  if (!diagnostic || diagnostic.diagnostic_available) return false;
  return diagnostic.interview_status === "ASSESSING"
    || (diagnostic.interview_status === "COMPLETED"
      && diagnostic.assessment !== null
      && diagnostic.assessment.status !== "FAILED");
}

function firstName(profile: Profile | null) {
  const value = profile?.full_name?.trim() || profile?.email.split("@")[0] || "there";
  return value.split(/\s+/)[0];
}

function DashboardHeader({ profile }: { profile: Profile | null }) {
  return (
    <header className="dashboard-page-header">
      <div>
        <p className="app-kicker">Welcome back, {firstName(profile)}</p>
        <h1 className="display">Your evidence workspace</h1>
        <p>Continue where you left off, explore new opportunities, or strengthen your existing evidence.</p>
      </div>
      <Link className="app-primary-button" href="/sessions/new">
        Start a new diagnostic <ArrowRight size={17} />
      </Link>
    </header>
  );
}

function DashboardSkeleton() {
  return (
    <div className="dashboard-skeleton" role="status" aria-label="Loading evidence workspace">
      <i /><i /><i /><i />
    </div>
  );
}

export function EvidenceDashboard() {
  const router = useRouter();
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttempt = useRef(0);
  const mounted = useRef(true);
  const [state, setState] = useState<WorkspaceState>("loading");
  const [workspace, setWorkspace] = useState<DashboardResponse | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [documents, setDocuments] = useState<MirrorDocument[]>([]);
  const [documentsUnavailable, setDocumentsUnavailable] = useState(false);
  const [error, setError] = useState("");
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [pollingFinished, setPollingFinished] = useState(false);

  const loadWorkspace = useCallback(async () => {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const next = await mirrorApi.dashboard();
        if (!mounted.current) return null;
        setWorkspace(next);
        setState("ready");
        setError("");
        return next;
      } catch (reason) {
        if (!mounted.current) return null;
        if (reason instanceof ApiError && reason.status === 401) {
          router.replace("/login?reason=session_expired");
          return null;
        }
        const transient = reason instanceof ApiError && (reason.status === 0 || reason.status === 502 || reason.status === 503);
        if (transient && attempt < 2) {
          await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
          continue;
        }
        setState("error");
        setError("Mirror could not load your evidence workspace. Your saved interviews have not been removed.");
        return null;
      }
    }
    return null;
  }, [router]);

  useEffect(() => {
    mounted.current = true;
    const poll = async () => {
      const next = await loadWorkspace();
      if (!mounted.current || !assessmentIsPending(next?.current ?? null)) return;
      if (pollAttempt.current >= 40) {
        setPollingFinished(true);
        return;
      }
      const delay = POLL_DELAYS[Math.min(pollAttempt.current, POLL_DELAYS.length - 1)];
      pollAttempt.current += 1;
      pollTimer.current = setTimeout(poll, delay);
    };

    // Deferring bootstrap by one task prevents React Strict Mode's discarded
    // development mount from issuing a duplicate set of remote reads.
    const bootstrapTimer = setTimeout(() => {
      void (async () => {
        await poll();
        const [profileResult, documentsResult] = await Promise.allSettled([
          mirrorApi.me(),
          mirrorApi.documents(),
        ]);
        if (!mounted.current) return;
        if (profileResult.status === "fulfilled") setProfile(profileResult.value);
        if (documentsResult.status === "fulfilled") {
          setDocuments(documentsResult.value);
          setDocumentsUnavailable(false);
        } else {
          setDocumentsUnavailable(true);
        }
      })();
    }, 0);
    return () => {
      mounted.current = false;
      clearTimeout(bootstrapTimer);
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [loadWorkspace]);

  async function retryAssessment(id: string) {
    setRetryingId(id);
    setError("");
    try {
      await mirrorApi.retryAssessment(id);
      pollAttempt.current = 0;
      setPollingFinished(false);
      const next = await loadWorkspace();
      if (assessmentIsPending(next?.current ?? null)) {
        pollTimer.current = setTimeout(() => void loadWorkspace(), POLL_DELAYS[0]);
      }
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Mirror could not retry this evaluation.");
    } finally {
      setRetryingId(null);
    }
  }

  const current = workspace?.current ?? null;
  const previous = workspace?.previous ?? [];

  return (
    <AppShell profile={profile}>
      <DashboardHeader profile={profile} />

      {error ? (
        <div className="app-inline-alert" role="alert">
          <WarningCircle size={19} />
          <span>{error}</span>
          <button type="button" onClick={() => void loadWorkspace()}>Retry</button>
        </div>
      ) : null}

      {state === "loading" ? <DashboardSkeleton /> : null}

      {state === "ready" && !current ? (
        <section className="dashboard-first-diagnostic app-panel" aria-labelledby="first-diagnostic-title">
          <p className="app-kicker">Your first diagnostic</p>
          <h2 id="first-diagnostic-title" className="display">Build your first evidence case.</h2>
          <p>Give Mirror a role and the professional evidence you want tested. Mirror will identify what appears convincing, what remains uncertain, and where an interview needs to probe deeper.</p>
          <Link className="app-primary-button" href="/sessions/new">Start a diagnostic <ArrowRight size={17} /></Link>
        </section>
      ) : null}

      {current ? (
        <>
          <div className="dashboard-primary-grid">
            <CurrentDiagnostic
              diagnostic={current}
              retrying={retryingId === current.id}
              onRetry={retryAssessment}
            />
            <QuickActions />
          </div>
          {pollingFinished && assessmentIsPending(current) ? (
            <p className="dashboard-poll-note">Evaluation is taking longer than usual. You can leave this page and return later; Mirror will keep your interview saved.</p>
          ) : null}
          <div className="dashboard-secondary-grid">
            <RecentDiagnostics diagnostics={previous} />
            <EvidencePreview documents={documents} unavailable={documentsUnavailable} />
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
