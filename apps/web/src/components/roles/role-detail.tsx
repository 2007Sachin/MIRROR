"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo } from "react";

import { InterviewMapView } from "@/components/roles/interview-map-view";
import { RoleTabs } from "@/components/roles/role-tabs";
import {
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  Section,
  usePageData,
} from "@/components/workspace/page-shell";
import { mirrorApi, type DashboardResponse, type InterviewMap } from "@/lib/api";
import { interviewMap as mapCopy, roles as t } from "@/lib/copy";
import { sessionRow } from "@/lib/dashboard-view";
import { startPracticeHref } from "@/lib/practice-view";
import { sessionsForRole } from "@/lib/role-view";

type RoleWorkspaceData = { map: InterviewMap; workspace: DashboardResponse };

async function loadRoleWorkspace(roleProfileId: string): Promise<RoleWorkspaceData> {
  const [map, workspace] = await Promise.all([mirrorApi.interviewMap(roleProfileId), mirrorApi.dashboard()]);
  return { map, workspace };
}

/** The role workspace: its Interview Map first, then the practice already done for it. */
export function RoleDetail({ roleProfileId }: { roleProfileId: string }) {
  const { state, data, error, reload } = usePageData(() => loadRoleWorkspace(roleProfileId), mapCopy.errors.load, [roleProfileId]);

  const history = useMemo(() => {
    if (!data) return [];
    const sessions = [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null);
    return sessionsForRole(sessions, data.map.target_role).map((session) => sessionRow(session, null));
  }, [data]);

  const role = data?.map.target_role ?? "";

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={state === "ready" ? role : mapCopy.eyebrow}
        intro={state === "ready" ? mapCopy.title : undefined}
        back={{ href: "/roles", label: t.detail.back }}
        action={
          state === "ready" ? (
            <Link className="dh-primary-action" href={startPracticeHref(role)}>
              {t.detail.start} <ArrowRight size={17} aria-hidden="true" />
            </Link>
          ) : null
        }
      />
      <RoleTabs roleProfileId={roleProfileId} current="map" />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && data ? (
        <div className="dh-home-sections">
          <InterviewMapView map={data.map} />

          <Section id="role-history" label={t.detail.history.title} title={t.detail.history.title}>
            {history.length ? (
              <ul className="dh-row-list">
                {history.map((row) => (
                  <li key={row.id}>
                    <span className="dh-row-main">
                      <strong>{row.state}</strong>
                      <small>{row.summary}</small>
                    </span>
                    <time className="dh-row-date" dateTime={row.date || undefined}>{row.date}</time>
                    <Link className="dh-text-action" href={row.href}>
                      {row.action} <ArrowRight size={15} aria-hidden="true" />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dh-review-empty">{t.detail.history.empty}</p>
            )}
          </Section>
        </div>
      ) : null}
    </PageShell>
  );
}
