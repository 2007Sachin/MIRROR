"use client";

import "@/styles/dashboard.css";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ContinuePreparing,
  DashboardHeader,
  DevelopmentAreas,
  NextAction,
  ReviewSummary,
  SetupProgress,
} from "@/components/dashboard/sections";
import { PracticeLauncher } from "@/components/dashboard/practice-launcher";
import { RolePreparation } from "@/components/dashboard/role-preparation";
import { Loader } from "@/components/loader";
import { AppShell } from "@/components/workspace/app-shell";
import {
  ApiError,
  mirrorApi,
  type DashboardResponse,
  type DashboardSummary,
  type Onboarding,
  type Profile,
} from "@/lib/api";
import { home, loading } from "@/lib/copy";
import { briefHref } from "@/lib/practice-view";
import { canStartDirectly, createPractice } from "@/lib/start-practice";
import {
  developmentAreas,
  firstNameOf,
  greetingForHour,
  newSessionHref,
  practiceOptions,
  reviewIsPending,
  sessionKind,
} from "@/lib/dashboard-view";

type WorkspaceState = "loading" | "ready" | "error";
const POLL_DELAYS = [3000, 3000, 5000, 5000, 8000, 8000, 12000, 15000] as const;

export function EvidenceDashboard({ initialOnboarding }: { initialOnboarding: Onboarding }) {
  const router = useRouter();
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttempt = useRef(0);
  const mounted = useRef(true);
  const summaryFor = useRef<string | null>(null);
  const [state, setState] = useState<WorkspaceState>("loading");
  const [workspace, setWorkspace] = useState<DashboardResponse | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pollingFinished, setPollingFinished] = useState(false);

  const loadSummary = useCallback(async (latestReadyId: string | null) => {
    if (!latestReadyId || summaryFor.current === latestReadyId) return;
    summaryFor.current = latestReadyId;
    setSummaryLoading(true);
    try {
      const next = await mirrorApi.dashboardSummary();
      if (mounted.current) setSummary(next);
    } catch {
      summaryFor.current = null;
    } finally {
      if (mounted.current) setSummaryLoading(false);
    }
  }, []);

  const loadWorkspace = useCallback(async () => {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const next = await mirrorApi.dashboard();
        if (!mounted.current) return null;
        setWorkspace(next);
        setState("ready");
        setError("");
        const sessions = [next.current, ...next.previous].filter((item) => item !== null);
        const latestReady = sessions.find((item) => sessionKind(item) === "review_ready") ?? null;
        void loadSummary(latestReady?.id ?? null);
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
        setError(home.errors.load);
        return null;
      }
    }
    return null;
  }, [loadSummary, router]);

  useEffect(() => {
    mounted.current = true;
    const poll = async () => {
      const next = await loadWorkspace();
      if (!mounted.current || !reviewIsPending(next?.current ?? null)) return;
      if (pollAttempt.current >= 40) {
        setPollingFinished(true);
        return;
      }
      const delay = POLL_DELAYS[Math.min(pollAttempt.current, POLL_DELAYS.length - 1)];
      pollAttempt.current += 1;
      pollTimer.current = setTimeout(poll, delay);
    };

    const bootstrapTimer = setTimeout(() => {
      void poll();
      void mirrorApi.me()
        .then((next) => mounted.current && setProfile(next))
        .catch((reason: unknown) => {
          if (reason instanceof ApiError && reason.status === 401) router.replace("/login?reason=session_expired");
        });
    }, 0);
    return () => {
      mounted.current = false;
      clearTimeout(bootstrapTimer);
      if (pollTimer.current) clearTimeout(pollTimer.current);
    };
  }, [loadWorkspace, router]);

  async function refreshAfter(action: () => Promise<unknown>, failure: string, id: string) {
    setBusyId(id);
    setError("");
    try {
      await action();
      pollAttempt.current = 0;
      setPollingFinished(false);
      const next = await loadWorkspace();
      if (reviewIsPending(next?.current ?? null)) pollTimer.current = setTimeout(() => void loadWorkspace(), POLL_DELAYS[0]);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : failure);
    } finally {
      setBusyId(null);
    }
  }

  async function quickStart(role: string) {
    // One implementation of starting a practice, shared with the Practice pages.
    if (!canStartDirectly(role, initialOnboarding)) {
      router.push(newSessionHref(role));
      return;
    }
    router.push(briefHref(await createPractice(role, initialOnboarding)));
  }

  const sessions = useMemo(
    () => (workspace ? [workspace.current, ...workspace.previous].filter((item) => item !== null) : []),
    [workspace],
  );
  const current = workspace?.current ?? null;
  const kind = current ? sessionKind(current) : null;
  const review = summary?.latest_review ?? null;
  const reviewSession = review ? sessions.find((session) => session.id === review.session_id) ?? null : null;
  const areas = useMemo(() => review ? developmentAreas(review) : [], [review]);
  const options = useMemo(() => practiceOptions(sessions, initialOnboarding), [initialOnboarding, sessions]);
  const greeting = greetingForHour(new Date().getHours());

  function primaryAction() {
    if (!current || !kind) {
      return (
        <NextAction
          title={home.empty.title}
          body={home.empty.body}
          supporting={<SetupProgress steps={[
            { label: home.progress.experience, done: Boolean(initialOnboarding.onboarding_resume_document_id) },
            { label: home.progress.role, done: Boolean(initialOnboarding.target_role) },
            { label: home.progress.practice, done: false },
          ]} />}
        >
          <PracticeLauncher
            options={options}
            onQuickStart={quickStart}
            label={initialOnboarding.onboarding_resume_document_id && initialOnboarding.target_role ? home.empty.first : home.empty.start}
          />
        </NextAction>
      );
    }

    switch (kind) {
      case "review_ready": {
        const matchingReview = review?.session_id === current.id ? review : null;
        const title = matchingReview?.next_step.title ?? (summaryLoading ? home.next.loading : home.next.keepGoing);
        const body = matchingReview?.next_step.body ?? (summaryLoading ? home.latest.body : home.next.keepGoingBody);
        return (
          <NextAction title={title} body={body} role={current.target_role}>
            <PracticeLauncher options={options} preferredRole={current.target_role} onQuickStart={quickStart} label={home.next.review} />
          </NextAction>
        );
      }
      case "review_processing":
        return <NextAction title={home.processing.title} body={pollingFinished ? home.processing.slow : home.processing.body} role={current.target_role} />;
      case "review_failed":
        return (
          <NextAction title={home.failed.title} body={home.failed.body} role={current.target_role}>
            <button className="dh-primary-action" type="button" disabled={busyId === current.id} onClick={() => void refreshAfter(() => mirrorApi.retryAssessment(current.id), home.errors.retry, current.id)}>
              {busyId === current.id ? home.failed.retrying : home.failed.retry}
            </button>
          </NextAction>
        );
      case "in_progress":
        return (
          <NextAction title={home.inProgress.title} body={home.inProgress.body} role={current.target_role} meta="Your work is saved.">
            <Link className="dh-primary-action" href={`/app/interview/${current.id}`}>{home.inProgress.cont}</Link>
          </NextAction>
        );
      case "ready":
        return (
          <NextAction title={home.beginReady.title} body={home.beginReady.body} role={current.target_role}>
            <Link className="dh-primary-action" href={`/app/interview/${current.id}`}>{home.beginReady.begin}</Link>
          </NextAction>
        );
      case "failed":
        return (
          <NextAction title="This practice didn't finish." body="You can prepare this role again without changing your saved experience." role={current.target_role}>
            <Link className="dh-primary-action" href={newSessionHref(current.target_role)}>Start again</Link>
          </NextAction>
        );
      default:
        return (
          <NextAction title={home.setup.title} body={home.setup.body} role={current.target_role}>
            <Link className="dh-primary-action" href={newSessionHref(current.target_role)}>{home.setup.cont}</Link>
          </NextAction>
        );
    }
  }

  const continueRole = current?.target_role || initialOnboarding.target_role || options[0]?.role || "Choose a role";

  return (
    <AppShell profile={profile}>
      <div className="dh">
        {state === "loading" ? (
          <Loader label={loading.space.label} note={loading.space.note} />
        ) : (
          <>
            <DashboardHeader
              firstName={firstNameOf(profile?.full_name, profile?.email)}
              greeting={greeting}
              action={<PracticeLauncher options={options} onQuickStart={quickStart} />}
            />

            {error ? (
              <div className="dh-alert" role="alert">
                <span>{error}</span>
                {state === "error" ? <button type="button" onClick={() => void loadWorkspace()}>{home.errors.reload}</button> : null}
              </div>
            ) : null}

            {state === "ready" ? (
              <div className="dh-home-sections">
                {primaryAction()}
                <RolePreparation roleProfileId={initialOnboarding.onboarding_role_profile_id} />
                {review && reviewSession ? <ReviewSummary session={reviewSession} areas={areas} /> : null}
                {review ? <DevelopmentAreas areas={areas} /> : null}
                {current || initialOnboarding.target_role ? (
                  <ContinuePreparing
                    role={continueRole}
                    action={<PracticeLauncher options={options} preferredRole={continueRole} onQuickStart={quickStart} label={`Practice ${continueRole}`} quiet />}
                  />
                ) : null}
              </div>
            ) : null}
          </>
        )}
      </div>
    </AppShell>
  );
}
