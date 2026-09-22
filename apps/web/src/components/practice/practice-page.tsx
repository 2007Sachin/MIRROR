"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import {
  EmptyState,
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  Section,
  usePageData,
} from "@/components/workspace/page-shell";
import {
  mirrorApi,
  type DashboardResponse,
  type DashboardSummary,
  type Onboarding,
  type PracticeRecommendation,
} from "@/lib/api";
import { home, practice as t, startPractice as startCopy } from "@/lib/copy";
import { sessionKind } from "@/lib/dashboard-view";
import { MODES, briefHref, continuePractice, focusFor, modeCopy, practiceHistory, startPracticeHref } from "@/lib/practice-view";
import { canStartDirectly, createPractice } from "@/lib/start-practice";

type PracticeData = {
  workspace: DashboardResponse;
  summary: DashboardSummary;
  onboarding: Onboarding;
  recommendation: PracticeRecommendation | null;
};

async function loadPractice(): Promise<PracticeData> {
  const [workspace, onboarding] = await Promise.all([mirrorApi.dashboard(), mirrorApi.onboarding()]);
  // Neither of these is essential: without them the page still shows every way to practise.
  const summary = await mirrorApi.dashboardSummary().catch(() => ({ latest_review: null }) as DashboardSummary);
  const roleId = onboarding.onboarding_role_profile_id;
  const recommendation = roleId
    ? await mirrorApi.practiceRecommendation(roleId).then((value) => value.recommendation).catch(() => null)
    : null;
  return { workspace, summary, onboarding, recommendation };
}

export function PracticePage() {
  const { state, data, error, reload } = usePageData(loadPractice, t.errors.load);

  const sessions = useMemo(
    () => (data ? [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null) : []),
    [data],
  );
  const rows = useMemo(() => practiceHistory(sessions, data?.summary.latest_review ?? null), [data, sessions]);
  const unfinished = useMemo(() => continuePractice(sessions), [sessions]);
  const role = data?.onboarding.target_role ?? sessions[0]?.target_role ?? null;

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={t.title}
        intro={t.intro}
        action={
          <Link className="dh-primary-action is-quiet" href={startPracticeHref(role)}>
            {t.start} <ArrowRight size={17} aria-hidden="true" />
          </Link>
        }
      />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} retryLabel={t.errors.retry} /> : null}

      {state === "ready" && data ? (
        <div className="dh-home-sections">
          {unfinished ? (
            <section className="dh-continue" aria-labelledby="practice-continue-title">
              <div>
                <p className="dh-section-label">{t.continueTitle}</p>
                <h2 id="practice-continue-title" className="display">{unfinished.target_role}</h2>
              </div>
              <div className="dh-continue-actions">
                <Link className="dh-primary-action" href={`/app/interview/${unfinished.id}`}>
                  {sessionKind(unfinished) === "ready" ? home.beginReady.begin : home.inProgress.cont} <ArrowRight size={16} aria-hidden="true" />
                </Link>
              </div>
            </section>
          ) : null}

          <Recommended recommendation={data.recommendation} onboarding={data.onboarding} role={role} />

          <Section id="practice-modes" label={t.modesTitle} title={t.modesTitle}>
            <ul className="dh-focus-list">
              {MODES.map((mode) => (
                <li key={mode}>
                  <Link href={startPracticeHref(role, { mode })}>
                    <span className="dh-focus-copy">
                      <strong>{modeCopy(mode).title}</strong>
                      <small>{modeCopy(mode).body}</small>
                    </span>
                    <span className="dh-focus-tag is-quiet">{modeCopy(mode).length}</span>
                    <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          </Section>

          <Section id="practice-history" label={t.previousTitle} title={t.previousTitle}>
            {rows.length ? (
              <ul className="dh-row-list" aria-label={t.historyLabel}>
                {rows.map((row) => (
                  <li key={row.id}>
                    <span className="dh-row-main">
                      <strong>{row.role}</strong>
                      <small>{row.label} · {row.summary}</small>
                    </span>
                    <time className="dh-row-date" dateTime={row.date || undefined}>{row.date}</time>
                    <span className={`dh-row-state ${rowStateClass(row.kind)}`}>{row.state}</span>
                    <Link className="dh-text-action" href={row.href}>
                      {row.action} <ArrowRight size={15} aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title={t.empty.title} body={t.previousEmpty} />
            )}
          </Section>
        </div>
      ) : null}
    </PageShell>
  );
}

/**
 * One suggested quick drill, from the role's preparation areas or latest review.
 * With nothing to go on it says so, rather than inventing something to work on.
 */
function Recommended({
  recommendation,
  onboarding,
  role,
}: {
  recommendation: PracticeRecommendation | null;
  onboarding: Onboarding;
  role: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  if (!recommendation) {
    return (
      <section className="dh-next-action" aria-labelledby="practice-recommended-title">
        <p className="dh-section-label">{t.recommendedTitle}</p>
        <h2 id="practice-recommended-title" className="display">{t.recommendedFallback}</h2>
        <div className="dh-action-row">
          <Link className="dh-primary-action" href={startPracticeHref(role, { mode: "QUICK_DRILL" })}>
            {t.choose} <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </div>
      </section>
    );
  }

  const choice = { mode: recommendation.mode, focus: recommendation.focus, theme: recommendation.theme };
  const title = recommendation.theme ?? focusFor(recommendation.focus)?.title ?? modeCopy(recommendation.mode).title;

  async function start() {
    if (!recommendation) return;
    if (!canStartDirectly(recommendation.target_role, onboarding)) {
      router.push(startPracticeHref(recommendation.target_role, choice));
      return;
    }
    setBusy(true);
    setFailed(false);
    try {
      router.push(briefHref(await createPractice(recommendation.target_role, onboarding, choice)));
    } catch {
      setFailed(true);
      setBusy(false);
    }
  }

  return (
    <section className="dh-next-action" aria-labelledby="practice-recommended-title">
      <p className="dh-section-label">{t.recommendedTitle}</p>
      <h2 id="practice-recommended-title" className="display">{title}</h2>
      <p className="dh-next-copy">{recommendation.reason}</p>
      <div className="dh-action-row">
        <button className="dh-primary-action" type="button" onClick={() => void start()} disabled={busy}>
          {busy ? startCopy.focusStep.preparing : t.startDrill} {busy ? null : <ArrowRight size={16} aria-hidden="true" />}
        </button>
        <span className="dh-action-meta">
          {modeCopy(recommendation.mode).title} · {modeCopy(recommendation.mode).length}
        </span>
      </div>
      {failed ? <p className="dh-inline-error" role="alert">{startCopy.focusStep.failed}</p> : null}
    </section>
  );
}

function rowStateClass(kind: ReturnType<typeof sessionKind>) {
  if (kind === "review_ready") return "is-ready";
  if (kind === "review_failed" || kind === "failed") return "is-attention";
  if (kind === "setup") return "is-muted";
  return "is-active";
}

