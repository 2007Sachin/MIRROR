"use client";

import { ArrowRight, ArrowUpRight, Check, Minus } from "@phosphor-icons/react";
import Link from "next/link";
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
import { mirrorApi } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { formatShortDay, reviewHref } from "@/lib/dashboard-view";
import { startPracticeHref } from "@/lib/practice-view";
import { directionClass, progressAreas, progressState, stateClass } from "@/lib/progress-view";

export function ProgressPage({ initialRole }: { initialRole?: string }) {
  const [role, setRole] = useState(initialRole ?? "");
  const { state, data, error, reload } = usePageData(() => mirrorApi.progress(role || undefined), t.errors.load, [role]);

  const areas = useMemo(() => progressAreas(data?.dimensions ?? []), [data]);
  const stage = progressState(data);

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={t.title}
        intro={t.intro}
        action={
          data && data.roles.length > 1 ? (
            <label className="dh-role-picker">
              <span className="sr-only">{t.roleLabel}</span>
              <select value={role || data.role || ""} onChange={(event) => setRole(event.target.value)}>
                {data.roles.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
          ) : null
        }
      />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && stage === "EMPTY" ? (
        <EmptyState
          title={t.empty.title}
          body={t.empty.body}
          action={{ href: startPracticeHref(), label: t.empty.action }}
        />
      ) : null}

      {state === "ready" && stage !== "EMPTY" && data ? (
        <div className="dh-home-sections">
          {data.headline ? (
            <section className="dh-next-action" aria-labelledby="progress-headline">
              <p className="dh-section-label">{data.role ?? t.eyebrow}</p>
              <h2 id="progress-headline" className="display">{data.headline.title}</h2>
              <p className="dh-next-copy">{data.headline.body}</p>
            </section>
          ) : null}

          <Section id="progress-areas" label={t.developing.title} title={t.developing.title} body={t.developing.body}>
            <ul className="dh-development-list">
              {areas.map((area) => (
                <li key={area.key}>
                  <Link href={area.href}>
                    <span className="dh-development-copy">
                      <strong>{area.label}</strong>
                      <small>{area.note}</small>
                    </span>
                    <span className="dh-development-states">
                      <span className={`dh-development-state ${stateClass(area.state)}`}>{area.state}</span>
                      {area.directionLabel ? (
                        <span className={`dh-direction ${directionClass(area.direction)}`}>{area.directionLabel}</span>
                      ) : null}
                    </span>
                    <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          </Section>

          <Section id="progress-changes" label={t.changesTitle} title={t.changesTitle} body={stage === "COMPARABLE" ? t.changesBody : undefined}>
            {stage === "COMPARABLE" && data.changes.length ? (
              <ul className="dh-change-list">
                {data.changes.map((change) => (
                  <li key={change.text} className={change.kind === "IMPROVED" ? "is-improved" : "is-watch"}>
                    {change.kind === "IMPROVED" ? <Check size={17} aria-hidden="true" /> : <ArrowUpRight size={17} aria-hidden="true" />}
                    <span>{change.text}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {stage === "COMPARABLE" && !data.changes.length ? (
              <p className="dh-review-empty">
                <Minus size={15} aria-hidden="true" /> {t.noChanges}
              </p>
            ) : null}
            {stage === "ONE_PRACTICE" ? <p className="dh-review-empty">{t.changesLocked}</p> : null}
          </Section>

          <Section id="progress-history" label={t.historyTitle} title={t.historyTitle}>
            <ul className="dh-row-list">
              {data.practices.map((practice) => (
                <li key={practice.session_id}>
                  <span className="dh-row-main">
                    <strong>{practice.target_role}</strong>
                    <small>{practice.next_step.title}</small>
                  </span>
                  <time className="dh-row-date" dateTime={practice.completed_at}>{formatShortDay(practice.completed_at)}</time>
                  <Link className="dh-text-action" href={reviewHref(practice.session_id)}>
                    {t.viewReview} <ArrowRight size={15} aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      ) : null}
    </PageShell>
  );
}
