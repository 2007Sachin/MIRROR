"use client";

import "@/styles/progress.css";

import { ArrowLeft } from "@phosphor-icons/react";
import Link from "next/link";

import { AnswerList } from "@/components/progress/answer-list";
import { useRoleProgress } from "@/components/progress/use-role-progress";
import { EmptyState, PageAlert, PageLoading, PageShell } from "@/components/workspace/page-shell";
import type { RoleProgress } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { AREA_KEYS, areaLabel, dimensionFor, notExploredCount, roleProgressHref } from "@/lib/progress-view";

/** "Your answers for this part": every answer Mirror noticed something about, with honest filters. */
export function DimensionAnswersView({
  data,
  dimensionKey,
  practiceSessionId,
}: {
  data: RoleProgress;
  dimensionKey: string;
  practiceSessionId?: string;
}) {
  const dimension = AREA_KEYS.includes(dimensionKey) ? dimensionFor(data, dimensionKey) : null;
  const missing = dimension ? notExploredCount(dimension) : 0;

  return (
    <>
      <Link className="dh-back-link" href={roleProgressHref(data.role_profile_id)}>
        <ArrowLeft size={15} aria-hidden="true" /> {t.dimension.back(data.target_role)}
      </Link>

      {!dimension ? (
        <EmptyState title={t.dimension.unknown} body={t.role.notFound.body} action={{ href: roleProgressHref(data.role_profile_id), label: t.dimension.back(data.target_role) }} />
      ) : (
        <div className="dh-home-sections">
          <header>
            <p className="dh-section-label">{areaLabel(dimensionKey)}</p>
            <h1 className="dh-title display">{t.answers.title}</h1>
            <p className="dh-page-intro">{t.answers.body}</p>
          </header>
          <AnswerList
            roleProfileId={data.role_profile_id}
            answers={data.answers}
            dimension={dimensionKey}
            practiceSessionId={practiceSessionId}
          />
          {missing > 0 ? <p className="pg-quiet">{t.answers.notExplored(missing)}</p> : null}
        </div>
      )}
    </>
  );
}

export function DimensionAnswers({
  roleProfileId,
  dimensionKey,
  practiceSessionId,
}: {
  roleProfileId: string;
  dimensionKey: string;
  practiceSessionId?: string;
}) {
  const { state, data, error, reload } = useRoleProgress(roleProfileId);

  return (
    <PageShell>
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}
      {state === "ready" && !data ? (
        <EmptyState title={t.role.notFound.title} body={t.role.notFound.body} action={{ href: "/progress", label: t.role.back }} />
      ) : null}
      {state === "ready" && data ? (
        <DimensionAnswersView data={data} dimensionKey={dimensionKey} practiceSessionId={practiceSessionId} />
      ) : null}
    </PageShell>
  );
}
