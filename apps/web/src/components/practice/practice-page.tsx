"use client";

import "@/styles/practice-reflect.css";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo } from "react";

import { DiscardPractice } from "@/components/practice/discard-practice";
import {
  EmptyState,
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  Section,
  usePageData,
} from "@/components/workspace/page-shell";
import { getActiveRole, type ActiveRoleOption } from "@/lib/api-active-role";
import {
  mirrorApi,
  type DashboardResponse,
  type DashboardSummary,
  type PracticeRecommendation,
} from "@/lib/api";
import { practice as t } from "@/lib/copy";
import { practiceHome as h } from "@/lib/copy-practice";
import {
  MODES,
  continueHref,
  focusFor,
  historyStateClass,
  modeCopy,
  practiceHistory,
  practiceLabel,
  startPracticeHref,
  unfinishedPractices,
} from "@/lib/practice-view";

type PracticeData = {
  workspace: DashboardResponse;
  summary: DashboardSummary;
  role: ActiveRoleOption | null;
  fallbackRole: string | null;
  recommendation: PracticeRecommendation | null;
};

async function loadPractice(): Promise<PracticeData> {
  const [workspace, onboarding] = await Promise.all([mirrorApi.dashboard(), mirrorApi.onboarding()]);
  // None of these is essential: without them the page still shows every way to practise.
  const [summary, active] = await Promise.all([
    mirrorApi.dashboardSummary().catch(() => ({ latest_review: null }) as DashboardSummary),
    getActiveRole().catch(() => null),
  ]);
  const role = active?.role ?? null;
  const roleId = role?.role_profile_id ?? onboarding.onboarding_role_profile_id;
  const recommendation = roleId
    ? await mirrorApi.practiceRecommendation(roleId).then((value) => value.recommendation).catch(() => null)
    : null;
  return { workspace, summary, role, fallbackRole: onboarding.target_role, recommendation };
}

/**
 * Practice home. One way in ("Start practice", which only opens the pre-practice check),
 * unfinished practice to continue or discard, and completed practice as history.
 * Nothing on this page creates a practice.
 */
export function PracticePage() {
  const { state, data, error, reload } = usePageData(loadPractice, t.errors.load);

  const sessions = useMemo(
    () => (data ? [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null) : []),
    [data],
  );
  const rows = useMemo(() => practiceHistory(sessions, data?.summary.latest_review ?? null), [data, sessions]);
  const unfinished = useMemo(() => unfinishedPractices(sessions), [sessions]);
  const role = data?.role?.target_role ?? data?.fallbackRole ?? null;
  const roleProfileId = data?.role?.role_profile_id ?? null;

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={t.title}
        intro={h.intro}
        action={
          <Link className="dh-primary-action" href={startPracticeHref(role, undefined, roleProfileId)}>
            {h.start} <ArrowRight size={17} aria-hidden="true" />
          </Link>
        }
      />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} retryLabel={t.errors.retry} /> : null}

      {state === "ready" && data ? (
        <div className="dh-home-sections">
          {unfinished.length ? (
            <Section id="practice-continue" title={h.unfinishedTitle} body={h.unfinishedBody}>
              <ul className="pr-draft-list">
                {unfinished.map((session) => {
                  const href = continueHref(session);
                  return (
                    <li key={session.id}>
                      <span className="pr-draft-copy">
                        <strong>{session.target_role}</strong>
                        <small>{href ? practiceLabel(session.practice_mode ?? "FULL_INTERVIEW", session.practice_focus, session.practice_theme) : h.setupUnfinished}</small>
                      </span>
                      <span className="pr-draft-actions">
                        {href ? (
                          <Link className="dh-primary-action is-quiet" href={href}>
                            {h.continue} <ArrowRight size={16} aria-hidden="true" />
                          </Link>
                        ) : null}
                        <DiscardPractice sessionId={session.id} onDiscarded={reload} />
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Section>
          ) : null}

          <Section id="practice-modes" title={h.formatsTitle} body={h.formatsBody}>
            <dl className="pr-formats">
              {MODES.map((mode) => (
                <div key={mode}>
                  <dt>{modeCopy(mode).title}</dt>
                  <dd>{modeCopy(mode).body}</dd>
                  <dd className="pr-format-length">{modeCopy(mode).length}</dd>
                </div>
              ))}
            </dl>
          </Section>

          <Suggestion recommendation={data.recommendation} />

          <Section id="practice-history" title={t.previousTitle}>
            {rows.length ? (
              <ul className="dh-row-list" aria-label={t.historyLabel}>
                {rows.map((row) => (
                  <li key={row.id}>
                    <span className="dh-row-main">
                      <strong>{row.role}</strong>
                      <small>{row.label} · {row.summary}</small>
                    </span>
                    <time className="dh-row-date" dateTime={row.date || undefined}>{row.date}</time>
                    <span className={`dh-row-state ${historyStateClass(row.kind)}`}>{row.state}</span>
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
 * One suggested practice, from the role's preparation areas or latest review. It only
 * opens the pre-practice check with the choice filled in; it never starts anything.
 */
function Suggestion({ recommendation }: { recommendation: PracticeRecommendation | null }) {
  if (!recommendation) {
    return <p className="dh-review-empty">{t.recommendedFallback}</p>;
  }
  const choice = { mode: recommendation.mode, focus: recommendation.focus, theme: recommendation.theme };
  const title = recommendation.theme ?? focusFor(recommendation.focus)?.title ?? modeCopy(recommendation.mode).title;
  return (
    <section className="pr-suggestion" aria-labelledby="practice-suggestion-title">
      <p className="dh-section-label">{h.suggestionTitle}</p>
      <h2 id="practice-suggestion-title" className="display">{title}</h2>
      <p className="dh-next-copy">{recommendation.reason}</p>
      <p className="dh-action-meta">
        {modeCopy(recommendation.mode).title} · {modeCopy(recommendation.mode).length}
      </p>
      <Link className="dh-text-action" href={startPracticeHref(recommendation.target_role, choice, recommendation.role_profile_id)}>
        {h.useSuggestion} <ArrowRight size={15} aria-hidden="true" />
      </Link>
    </section>
  );
}
