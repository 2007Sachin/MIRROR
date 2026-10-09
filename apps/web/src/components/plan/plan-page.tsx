"use client";

import "@/styles/plan.css";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PlanAreaCard, type PlanHrefs } from "@/components/plan/plan-area-card";
import { TargetOverview } from "@/components/plan/target-overview";
import { EmptyState, PageAlert, PageHeader, PageLoading, PageShell, usePageData } from "@/components/workspace/page-shell";
import { ApiError } from "@/lib/api";
import { choosePlanLink, getPlan, type Plan, type PlanArea, type PlanLink } from "@/lib/api-plan";
import { planCopy as t } from "@/lib/copy-plan";
import { planHref } from "@/lib/copy-targets";
import { findStoryHref } from "@/lib/map-view";
import { startPracticeHref } from "@/lib/practice-view";

/** Start the story from the approved example already linked to this need, when there is one. */
function storyHref(roleProfileId: string, area: PlanArea) {
  const item = [...area.have, ...area.suggested].find((link) => link.evidence_item_id)?.evidence_item_id;
  const base = findStoryHref(roleProfileId, area.theme);
  return item ? `${base}&evidence=${encodeURIComponent(item)}` : base;
}

function hrefsFor(plan: Plan, area: PlanArea): PlanHrefs {
  const role = plan.role!;
  return {
    // The exact role travels with the practice, so it stays on this role.
    PRACTICE: startPracticeHref(role.target_role, { mode: "FOCUSED_PRACTICE", focus: "role", theme: area.theme }, role.role_profile_id),
    STORY: storyHref(role.role_profile_id, area),
    ADD_EXAMPLE: "/experience",
  };
}

/** My plan for one role (`role` from the URL), else for the active role. */
export function PlanPage({ roleProfileId, initialTargetId }: { roleProfileId: string | null; initialTargetId?: string | null }) {
  const { state, data: plan, error, reload, setData } = usePageData(() => getPlan(roleProfileId), t.errors.load, [roleProfileId]);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const router = useRouter();

  // Plan pages always carry the role: a bare /plan pins the role it resolved, so links and reloads stay on it.
  const resolvedRole = plan?.role?.role_profile_id ?? null;
  useEffect(() => {
    if (!roleProfileId && resolvedRole) router.replace(planHref(resolvedRole, initialTargetId ?? undefined));
  }, [roleProfileId, resolvedRole, router, initialTargetId]);

  async function choose(area: PlanArea, link: PlanLink, confirmed: boolean) {
    if (!plan?.role) return;
    setBusy(true);
    setSaveError("");
    try {
      setData(await choosePlanLink(plan.role.role_profile_id, area.key, link, confirmed));
    } catch (reason) {
      setSaveError(reason instanceof ApiError && reason.kind !== "other" && reason.message ? reason.message : t.errors.save);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={plan?.role ? t.title(plan.role.target_role) : t.titleGeneral}
        intro={plan?.state === "READY" ? t.intro : undefined}
      />
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}
      {state === "ready" && plan ? <PlanBody plan={plan} busy={busy} onChoose={choose} reload={reload} initialTargetId={initialTargetId ?? null} /> : null}
      {saveError ? <PageAlert message={saveError} /> : null}
    </PageShell>
  );
}

function PlanBody({
  plan,
  busy,
  onChoose,
  reload,
  initialTargetId,
}: {
  plan: Plan;
  busy: boolean;
  onChoose: (area: PlanArea, link: PlanLink, confirmed: boolean) => void;
  reload: () => void;
  initialTargetId: string | null;
}) {
  // Section A (interview target) owns the page's one filled action when it shows rounds.
  const [targetPrimary, setTargetPrimary] = useState(false);
  if (plan.state === "NEEDS_REVIEW") {
    return (
      <EmptyState title={t.states.reviewTitle} body={t.states.reviewBody}>
        <Link className="dh-primary-action" href="/experience#review">{t.states.reviewAction}</Link>
      </EmptyState>
    );
  }
  if (plan.state === "NO_ROLE") {
    return (
      <EmptyState title={t.states.noRoleTitle} body={t.states.noRoleBody}>
        <Link className="dh-primary-action" href="/roles/new">{t.states.noRoleAction}</Link>
      </EmptyState>
    );
  }
  if (plan.state === "PREPARING") {
    return (
      <EmptyState title={t.states.preparingTitle} body={t.states.preparingBody}>
        <button type="button" className="dh-primary-action is-quiet" onClick={reload}>{t.states.preparingAction}</button>
      </EmptyState>
    );
  }
  if (plan.state === "UNAVAILABLE" || !plan.role) {
    return (
      <EmptyState title={t.states.unavailableTitle} body={t.states.unavailableBody}>
        <Link className="dh-primary-action is-quiet" href="/roles">{t.states.unavailableAction}</Link>
      </EmptyState>
    );
  }
  return (
    <>
      <TargetOverview key={plan.role.role_profile_id} roleProfileId={plan.role.role_profile_id} roleName={plan.role.target_role} initialTargetId={initialTargetId ?? undefined} onPrimary={setTargetPrimary} />
      <section className="pl-areas-section" aria-labelledby="pl-areas-title">
        <h2 id="pl-areas-title" className="pl-run-title">{t.areasTitle}</h2>
        <div className="pl-areas">
          {plan.areas.map((area) => (
            <PlanAreaCard
              key={area.key}
              area={area}
              recommended={area.key === plan.recommended_area_key}
              demoted={targetPrimary}
              hrefs={hrefsFor(plan, area)}
              busy={busy}
              onChoose={(link, confirmed) => onChoose(area, link, confirmed)}
            />
          ))}
        </div>
      </section>
    </>
  );
}
