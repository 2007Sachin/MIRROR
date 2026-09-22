"use client";

import { ArrowRight, Plus } from "@phosphor-icons/react";
import Link from "next/link";

import { EmptyState, PageAlert, PageHeader, PageLoading, PageShell, usePageData } from "@/components/workspace/page-shell";
import { mirrorApi } from "@/lib/api";
import { stories as t } from "@/lib/copy";
import { formatShortDay } from "@/lib/dashboard-view";
import { completenessClass, completenessLabel, nextMissingPart, partLabel } from "@/lib/story-view";

export function StoriesPage() {
  const { state, data, error, reload } = usePageData(() => mirrorApi.stories(), t.errors.load);

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={t.title}
        intro={t.intro}
        action={
          <span className="dh-header-actions">
            <Link className="dh-text-action" href="/stories/new?guided=1">
              {t.findOne}
            </Link>
            <Link className="dh-primary-action" href="/stories/new">
              <Plus size={16} aria-hidden="true" /> {t.add}
            </Link>
          </span>
        }
      />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && data && !data.length ? (
        <EmptyState title={t.empty.title} body={t.empty.body} action={{ href: "/stories/new?guided=1", label: t.findOne }} />
      ) : null}

      {state === "ready" && data?.length ? (
        <ul className="dh-row-list">
          {data.map((story) => {
            const next = nextMissingPart(story);
            return (
              <li key={story.id}>
                <span className="dh-row-main">
                  <strong>{story.title}</strong>
                  <small>
                    {story.themes.length ? `${story.themes.join(", ")} · ` : ""}
                    {next && story.completeness !== "READY" ? t.nextPart(partLabel(next)) : t.from[story.origin]}
                  </small>
                </span>
                <time className="dh-row-date" dateTime={story.updated_at}>{formatShortDay(story.updated_at)}</time>
                <span className={`dh-row-state ${completenessClass(story)}`}>{completenessLabel(story)}</span>
                <Link className="dh-text-action" href={`/stories/${story.id}`}>
                  {t.edit} <ArrowRight size={15} aria-hidden="true" />
                </Link>
              </li>
            );
          })}
        </ul>
      ) : null}
    </PageShell>
  );
}
