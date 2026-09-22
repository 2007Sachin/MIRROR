"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo } from "react";

import {
  EmptyState,
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  Section,
  usePageData,
} from "@/components/workspace/page-shell";
import { mirrorApi, type DashboardResponse, type DashboardSummary } from "@/lib/api";
import { practice as t, practiceFocus } from "@/lib/copy";
import { formatShortDay, sessionKind } from "@/lib/dashboard-view";
import {
  continuePractice,
  otherFocusOptions,
  practiceHistory,
  recommendedFocus,
  startPracticeHref,
} from "@/lib/practice-view";

type PracticeData = { workspace: DashboardResponse; summary: DashboardSummary };

async function loadPractice(): Promise<PracticeData> {
  const workspace = await mirrorApi.dashboard();
  // A missing summary only costs the one-line result under a finished practice.
  const summary = await mirrorApi.dashboardSummary().catch(() => ({ latest_review: null }) as DashboardSummary);
  return { workspace, summary };
}

export function PracticePage() {
  const { state, data, error, reload } = usePageData(loadPractice, t.errors.load);

  const sessions = useMemo(
    () => (data ? [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null) : []),
    [data],
  );
  const rows = useMemo(() => practiceHistory(sessions, data?.summary.latest_review ?? null), [data, sessions]);
  const next = useMemo(() => continuePractice(sessions), [sessions]);
  const recommended = recommendedFocus();

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={t.title}
        intro={t.intro}
        action={
          <Link className="dh-primary-action" href={startPracticeHref()}>
            {t.start} <ArrowRight size={17} aria-hidden="true" />
          </Link>
        }
      />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} retryLabel={t.errors.retry} /> : null}

      {state === "ready" ? (
        <div className="dh-home-sections">
          {next ? (
            <section className="dh-next-action" aria-labelledby="practice-continue-title">
              <p className="dh-section-label">{t.continueTitle}</p>
              <h2 id="practice-continue-title" className="display">{next.target_role}</h2>
              <p className="dh-next-copy">
                {next.completed_at || next.updated_at
                  ? t.lastPractised(formatShortDay(next.completed_at || next.updated_at))
                  : t.neverPractised}
              </p>
              <div className="dh-action-row">
                <Link className="dh-primary-action" href={continueHref(next.id, next.target_role, sessionKind(next))}>
                  {continueLabel(sessionKind(next))} <ArrowRight size={17} aria-hidden="true" />
                </Link>
              </div>
            </section>
          ) : (
            <EmptyState title={t.empty.title} body={t.empty.body} action={{ href: startPracticeHref(), label: t.empty.action }} />
          )}

          <Section id="practice-focus" label={t.specificTitle} title={t.specificTitle} body={t.specificBody}>
            <ul className="dh-focus-list">
              <li className="is-recommended">
                <Link href={startPracticeHref(next?.target_role, recommended.key)}>
                  <span className="dh-focus-copy">
                    <strong>{recommended.title}</strong>
                    <small>{recommended.body}</small>
                  </span>
                  <span className="dh-focus-tag">{t.recommended}</span>
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
              </li>
              {otherFocusOptions().map((option) => (
                <li key={option.key}>
                  <Link href={startPracticeHref(next?.target_role, option.key)}>
                    <span className="dh-focus-copy">
                      <strong>{option.title}</strong>
                      <small>{option.body}</small>
                    </span>
                    <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
            <p className="dh-fine-print">{practiceFocus.note}</p>
          </Section>

          <Section id="practice-history" label={t.previousTitle} title={t.previousTitle}>
            {rows.length ? (
              <ul className="dh-row-list" aria-label={t.historyLabel}>
                {rows.map((row) => (
                  <li key={row.id}>
                    <span className="dh-row-main">
                      <strong>{row.role}</strong>
                      <small>{row.summary}</small>
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
              <p className="dh-review-empty">{t.previousEmpty}</p>
            )}
          </Section>
        </div>
      ) : null}
    </PageShell>
  );
}

function continueHref(id: string, role: string, kind: ReturnType<typeof sessionKind>) {
  if (kind === "in_progress" || kind === "ready") return `/app/interview/${id}`;
  if (kind === "setup") return `/sessions/new?role=${encodeURIComponent(role)}`;
  if (kind === "review_ready" || kind === "review_processing" || kind === "review_failed") return `/app/report/${id}`;
  return startPracticeHref(role);
}

function continueLabel(kind: ReturnType<typeof sessionKind>) {
  if (kind === "in_progress") return "Continue";
  if (kind === "ready") return "Begin";
  if (kind === "setup") return "Continue setup";
  if (kind === "review_ready") return "View review";
  return "Continue";
}

function rowStateClass(kind: ReturnType<typeof sessionKind>) {
  if (kind === "review_ready") return "is-ready";
  if (kind === "review_failed" || kind === "failed") return "is-attention";
  if (kind === "setup") return "is-muted";
  return "is-active";
}
