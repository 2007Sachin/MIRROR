"use client";

import "@/styles/progress.css";

import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, ChartLineUp } from "@phosphor-icons/react";
import Link from "next/link";

import { AnswerList } from "@/components/progress/answer-list";
import { DevelopmentTimeline } from "@/components/progress/development-timeline";
import { RoleConnection } from "@/components/progress/role-connection";
import { StateMark } from "@/components/progress/state-mark";
import { useRoleProgress } from "@/components/progress/use-role-progress";
import { EmptyState, PageAlert, PageLoading, PageShell, Section } from "@/components/workspace/page-shell";
import type { RoleProgress } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { formatDay, reviewHref } from "@/lib/dashboard-view";
import {
  ROLE_TABS,
  baselineSeen,
  comparedWith,
  dimensionHref,
  insightViews,
  practiceTitle,
  roleMeta,
  roleProgressHref,
  startRoleHref,
  stateLabel,
  areaLabel,
  type RoleTab,
} from "@/lib/progress-view";

/** The page's content for one role. Shared by the real page and the local QA preview. */
export function RoleProgressView({ data, tab }: { data: RoleProgress; tab: RoleTab }) {
  return (
    <>
      <header className="pg-role-header">
        <Link className="dh-back-link" href="/progress">
          <ArrowLeft size={15} aria-hidden="true" /> {t.role.back}
        </Link>
        <div className="pg-role-row">
          <span className="pg-tile-icon is-large" aria-hidden="true">
            <ChartLineUp size={26} />
          </span>
          <div>
            <h1 className="dh-title display">{data.target_role}</h1>
            <p className="pg-role-meta">{roleMeta(data)}</p>
          </div>
          <Link className="pg-button is-dark" href={startRoleHref(data.target_role, data.role_profile_id)}>
            {t.role.start}
          </Link>
        </div>
        <nav className="pg-tabs" aria-label={t.role.tabsLabel}>
          {ROLE_TABS.map((key) => (
            <Link key={key} href={roleProgressHref(data.role_profile_id, key)} aria-current={key === tab ? "page" : undefined}>
              {t.role.tabs[key]}
            </Link>
          ))}
        </nav>
      </header>

      {tab === "overview" ? <Overview progress={data} /> : null}
      {tab === "answers" ? (
        <Section id="role-answers" title={t.answers.roleTitle} body={t.answers.roleBody}>
          <AnswerList roleProfileId={data.role_profile_id} answers={data.answers} dimension={null} />
        </Section>
      ) : null}
      {tab === "history" ? <History progress={data} /> : null}
      {tab === "connection" ? (
        <Section id="role-connection" title={t.connection.title} body={t.connection.body}>
          <RoleConnection progress={data} />
        </Section>
      ) : null}
    </>
  );
}

export function RoleProgressPage({ roleProfileId, tab }: { roleProfileId: string; tab: RoleTab }) {
  const { state, data, error, reload } = useRoleProgress(roleProfileId);

  return (
    <PageShell>
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && !data ? (
        <>
          <Link className="dh-back-link" href="/progress">
            <ArrowLeft size={15} aria-hidden="true" /> {t.role.back}
          </Link>
          <EmptyState title={t.role.notFound.title} body={t.role.notFound.body} action={{ href: "/progress", label: t.role.back }} />
        </>
      ) : null}

      {state === "ready" && data ? <RoleProgressView data={data} tab={tab} /> : null}
    </PageShell>
  );
}

function Overview({ progress }: { progress: RoleProgress }) {
  if (progress.stage === "NONE") {
    return (
      <EmptyState
        title={t.overview.none.title}
        body={t.overview.none.body}
        action={{ href: startRoleHref(progress.target_role, progress.role_profile_id), label: t.role.start }}
      />
    );
  }

  const insights = insightViews(progress.insights);
  const early = new Set(progress.practices.filter((item) => item.shorter_conversation).map((item) => item.session_id));
  const compared = (progress.dimensions[0]?.cells ?? []).filter((cell) => !early.has(cell.session_id)).length;

  return (
    <div className="dh-home-sections">
      {progress.stage === "COMPARABLE" ? (
        <Section
          id="since-last"
          title={t.overview.sinceTitle}
          body={progress.insights.length ? comparedWith(progress.insights) : undefined}
          action={<span className="pg-badge">{t.overview.basedOn(compared)}</span>}
        >
          {insights.length ? (
            <ul className="pg-insights">
              {insights.map((insight) => (
                <li key={insight.key} className={`is-${insight.trend.toLowerCase()}`}>
                  <Link href={dimensionHref(progress.role_profile_id, insight.dimension)}>
                    <span className="pg-insight-icon" aria-hidden="true">
                      {insight.trend === "MORE" ? <ArrowUp size={22} /> : insight.trend === "LESS" ? <ArrowDown size={22} /> : <ArrowRight size={22} />}
                    </span>
                    <strong>{insight.title}</strong>
                    <span>{insight.body}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dh-review-empty">{t.overview.noChange}</p>
          )}
        </Section>
      ) : (
        <Section id="baseline" title={t.overview.baselineTitle} body={t.overview.baselineBody}>
          {baselineSeen(progress).length ? null : <p className="pg-quiet">{t.timeline.notEnough}</p>}
          <ul className="pg-rows is-plain">
            {baselineSeen(progress).map((item) => (
              <li key={item.key}>
                <Link className="pg-area-row" href={dimensionHref(progress.role_profile_id, item.key)}>
                  <StateMark kind={item.state} />
                  <span className="pg-row-copy">
                    <strong>{item.label}</strong>
                    {item.note ? <small>{item.note}</small> : null}
                  </span>
                  <span className="pg-row-state">{stateLabel(item.state)}</span>
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section id="development" title={t.timeline.title} body={t.timeline.body}>
        <DevelopmentTimeline progress={progress} />
      </Section>
    </div>
  );
}

function History({ progress }: { progress: RoleProgress }) {
  return (
    <Section id="role-history" title={t.history.title} body={t.history.body}>
      {progress.practices.length ? (
        <ul className="pg-rows is-plain">
          {progress.practices.map((practice) => (
            <li key={practice.session_id}>
              <Link className="pg-area-row" href={reviewHref(practice.session_id)}>
                <time className="pg-date" dateTime={practice.completed_at}>
                  {formatDay(practice.completed_at)}
                </time>
                <span className="pg-row-copy">
                  <strong>{practiceTitle(practice)}</strong>
                  <small>
                    {[
                      t.timeline.practice(practice.number),
                      practice.question_count ? t.history.questions(practice.question_count) : "",
                      practice.shorter_conversation ? t.history.shorter : "",
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                </span>
                <span className="pg-row-state">{t.history.open}</span>
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dh-review-empty">{t.history.empty}</p>
      )}
    </Section>
  );
}
