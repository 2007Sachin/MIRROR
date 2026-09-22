"use client";

import { ArrowRight, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo } from "react";

import {
  EmptyState,
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  usePageData,
} from "@/components/workspace/page-shell";
import { mirrorApi, type DashboardResponse, type Onboarding, type RoleProfileSummary } from "@/lib/api";
import { roles as t } from "@/lib/copy";
import { newSessionHref } from "@/lib/dashboard-view";
import { roleCards } from "@/lib/role-view";

type RolesData = { profiles: RoleProfileSummary[]; workspace: DashboardResponse; onboarding: Onboarding };

async function loadRoles(): Promise<RolesData> {
  const [workspace, onboarding] = await Promise.all([mirrorApi.dashboard(), mirrorApi.onboarding()]);
  // Roles set up before role profiles were recorded still show, from practice alone.
  const profiles = await mirrorApi.roles().catch(() => [] as RoleProfileSummary[]);
  return { profiles, workspace, onboarding };
}

export function RolesPage() {
  const { state, data, error, reload } = usePageData(loadRoles, t.errors.load);

  const cards = useMemo(() => {
    if (!data) return [];
    const sessions = [data.workspace.current, ...data.workspace.previous].filter((item) => item !== null);
    return roleCards(data.profiles, sessions, data.onboarding.target_role);
  }, [data]);

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={t.title}
        intro={t.intro}
        action={
          <Link className="dh-primary-action" href={newSessionHref()}>
            <Plus size={16} aria-hidden="true" /> {t.add}
          </Link>
        }
      />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && !cards.length ? (
        <EmptyState title={t.empty.title} body={t.empty.body} action={{ href: newSessionHref(), label: t.empty.action }} />
      ) : null}

      {state === "ready" && cards.length ? (
        <ul className="dh-role-list">
          {cards.map((card) => (
            <li key={card.key}>
              <div className="dh-role-main">
                {card.detailHref ? (
                  <Link className="dh-role-name" href={card.detailHref}>
                    {card.role}
                  </Link>
                ) : (
                  <span className="dh-role-name">{card.role}</span>
                )}
                <span className="dh-role-meta">
                  <span className={`dh-row-state ${card.status === "SETUP_INCOMPLETE" ? "is-attention" : card.status === "ACTIVE" ? "is-ready" : "is-muted"}`}>
                    {card.statusLabel}
                  </span>
                  {card.meta ? <small>{card.meta}</small> : null}
                </span>
              </div>
              <Link className="dh-text-action" href={card.href}>
                {card.action} <ArrowRight size={15} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </PageShell>
  );
}
