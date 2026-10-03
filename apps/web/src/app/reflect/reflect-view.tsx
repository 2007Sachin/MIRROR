"use client";

import "@/styles/practice-reflect.css";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo } from "react";

import { RoleTileCard } from "@/components/progress/progress-hub";
import { EmptyState, PageAlert, PageHeader, PageLoading, PageShell, Section, usePageData } from "@/components/workspace/page-shell";
import { mirrorApi, type DashboardSummary, type ProgressRoleTile } from "@/lib/api";
import { getActiveRole } from "@/lib/api-active-role";
import { progress } from "@/lib/copy";
import { reflect as t } from "@/lib/copy-practice";
import { newSessionHref } from "@/lib/dashboard-view";
import { historyStateClass, practiceHistory, sameRole } from "@/lib/practice-view";

async function loadReflect() {
  const [workspace, active, summary, hub] = await Promise.all([
    mirrorApi.dashboard(),
    getActiveRole().catch(() => null),
    mirrorApi.dashboardSummary().catch(() => ({ latest_review: null }) as DashboardSummary),
    // How practice is developing is its own section: without it, reviews still show.
    mirrorApi.progressHub().then((value) => value.roles).catch(() => null),
  ]);
  return { workspace, role: active?.role ?? null, summary, hub };
}

type Row = ReturnType<typeof practiceHistory>[number];

/**
 * Reflect: completed practice and its reviews for the active role first, then the other
 * roles, then how practice is developing for each role (the progress pages).
 */
export function ReflectView() {
  const { state, data, error, reload } = usePageData(loadReflect, t.load);

  const rows = useMemo(() => {
    if (!data) return [];
    const sessions = [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null);
    return practiceHistory(sessions, data.summary.latest_review);
  }, [data]);
  const role = data?.role?.target_role ?? null;
  const mine = role ? rows.filter((row) => sameRole(row.role, role)) : rows;
  const others = role ? rows.filter((row) => !sameRole(row.role, role)) : [];
  const tiles = useMemo(() => activeFirst(data?.hub ?? [], data?.role?.role_profile_id ?? null), [data]);

  return (
    <PageShell>
      <PageHeader eyebrow={t.eyebrow} title={t.title} intro={t.intro} />
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && data ? (
        <div className="dh-home-sections">
          <Section id="reflect-recent" title={role ? t.recentTitle(role) : t.recentAllTitle}>
            {mine.length ? <ReviewRows rows={mine} /> : <EmptyState title={t.recentAllTitle} body={t.recentEmpty} />}
          </Section>

          {others.length ? (
            <Section id="reflect-other" title={t.otherTitle}>
              <ReviewRows rows={others} />
            </Section>
          ) : null}

          <Section id="reflect-developing" title={t.developingTitle} body={t.developingBody}>
            {data.hub === null ? (
              <p className="dh-review-empty">{t.developingUnavailable}</p>
            ) : !tiles.length ? (
              <EmptyState title={progress.hub.empty.title} body={progress.hub.empty.body} action={{ href: newSessionHref(), label: progress.hub.empty.action }} />
            ) : (
              <ul className="pg-tiles">
                {tiles.map((tile) => (
                  <li key={tile.role_profile_id}>
                    <RoleTileCard tile={tile} />
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      ) : null}
    </PageShell>
  );
}

function ReviewRows({ rows }: { rows: Row[] }) {
  return (
    <ul className="dh-row-list">
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
  );
}

function activeFirst(tiles: ProgressRoleTile[], activeId: string | null) {
  return [...tiles].sort((left, right) => Number(right.role_profile_id === activeId) - Number(left.role_profile_id === activeId));
}
