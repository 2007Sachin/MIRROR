"use client";

import { ArrowRight, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState, PageAlert, PageHeader, PageLoading, PageShell, Section, usePageData } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type RoleProfileSummary, type Story } from "@/lib/api";
import { stories as t } from "@/lib/copy";
import { storyLibrary as L } from "@/lib/copy-stories";
import { formatShortDay } from "@/lib/dashboard-view";
import { improveHref, practiceLine, practiseStoryHref, usefulFor } from "@/lib/story-view";
import "@/styles/stories-guided.css";

const READINESS_CLASS: Record<string, string> = { READY: "is-ready", DEVELOPING: "is-active", STARTED: "is-attention" };

/**
 * The actions a story offers, one verb per outcome: "Add detail" until it is ready to tell
 * (an open review suggestion opens the editor at that part), then "Practice this story"
 * with "Edit story" beside it. Never two links that go to the same place.
 */
export function storyActions(story: Pick<Story, "id" | "completeness">, openSuggestionId?: string) {
  const edit = `/stories/${story.id}`;
  if (openSuggestionId) return [{ label: L.actions.addDetail, href: improveHref({ id: openSuggestionId, story_id: story.id }) }];
  if (story.completeness !== "READY") return [{ label: L.actions.addDetail, href: edit }];
  return [
    { label: L.actions.practice, href: practiseStoryHref(story.id) },
    { label: L.actions.edit, href: edit },
  ];
}

export function StoriesPage() {
  const { state, data, error, reload } = usePageData(
    async () => {
      const [active, archived, roles, practice, suggestions] = await Promise.all([
        mirrorApi.stories(),
        mirrorApi.stories({ archived: true }),
        mirrorApi.roles().catch(() => [] as RoleProfileSummary[]),  // names only; the list still loads
        mirrorApi.storyPracticeSummaries().catch(() => null),  // counts only; the list still loads
        mirrorApi.openStorySuggestions().catch(() => []),
      ]);
      const open = new Map<string, { id: string; count: number }>();
      for (const item of suggestions) {
        const current = open.get(item.story_id);
        open.set(item.story_id, current ? { id: current.id, count: current.count + 1 } : { id: item.id, count: 1 });
      }
      return { active, archived, roles, practice: practice ? new Map(practice.map((item) => [item.story_id, item])) : null, open };
    },
    t.errors.load,
  );
  const [restoring, setRestoring] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState("");
  const [notice, setNotice] = useState("");

  async function restore(story: Story) {
    setRestoring(story.id);
    setRestoreError("");
    setNotice("");
    try {
      await mirrorApi.restoreStory(story.id);
      setNotice(t.archived.restored);
      reload();
    } catch (reason) {
      setRestoreError(reason instanceof ApiError ? reason.message : t.errors.restore);
    } finally {
      setRestoring(null);
    }
  }

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={t.title}
        intro={t.intro}
        action={
          <Link className="dh-primary-action" href="/stories/new">
            <Plus size={16} aria-hidden="true" /> {L.add}
          </Link>
        }
      />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}
      {notice ? <p className="dh-notice" role="status">{notice}</p> : null}

      {state === "ready" && data && !data.active.length ? (
        <EmptyState title={t.empty.title} body={t.empty.body} action={{ href: "/stories/new", label: L.add }} />
      ) : null}

      {state === "ready" && data?.active.length ? (
        <ul className="sg-cards">
          {data.active.map((story) => {
            const open = data.open.get(story.id);
            return (
              <li key={story.id} className="sg-card">
                <div className="sg-card-head">
                  <strong>{story.title}</strong>
                  <span className={`dh-row-state ${READINESS_CLASS[story.completeness] ?? "is-attention"}`}>{L.readiness[story.completeness]}</span>
                </div>
                <p className="sg-card-purpose">
                  {story.themes.length ? L.purpose(story.themes.join(", ")) : story.role_profile_ids.length ? usefulFor(story, data.roles) : L.noPurpose}
                </p>
                <p className="dh-fine-print">
                  {L.version(story.current_version)} · {practiceLine(data.practice?.get(story.id))}
                </p>
                <div className="sg-card-actions">
                  {storyActions(story, open?.id).map((action) => (
                    <Link
                      key={action.label}
                      className="dh-text-action"
                      href={action.href}
                      title={open && open.count > 1 ? t.suggestions.count(open.count) : undefined}
                    >
                      {action.label} <ArrowRight size={15} aria-hidden="true" />
                    </Link>
                  ))}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}

      {state === "ready" && data?.archived.length ? (
        <Section id="stories-archived" title={t.archived.title} body={L.archivedBody}>
          {restoreError ? <PageAlert message={restoreError} /> : null}
          <ul className="dh-row-list">
            {data.archived.map((story) => (
              <li key={story.id}>
                <span className="dh-row-main">
                  <strong>{story.title}</strong>
                  <small>{t.archived.on(formatShortDay(story.archived_at))}</small>
                  {data.practice?.get(story.id)?.practice_count ? <small>{practiceLine(data.practice.get(story.id))}</small> : null}
                </span>
                <span className="dh-row-actions">
                  <Link className="dh-text-action" href={`/stories/${story.id}`}>
                    {t.open}
                  </Link>
                  <button type="button" className="dh-text-action" onClick={() => void restore(story)} disabled={restoring !== null}>
                    {restoring === story.id ? t.archived.restoring : t.archived.restore}
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </PageShell>
  );
}
