"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageAlert, PageLoading, Section } from "@/components/workspace/page-shell";
import { mirrorApi, type RoleProfileSummary, type Story, type StoryPracticeRecord } from "@/lib/api";
import { stories as copy } from "@/lib/copy";
import { formatShortDay } from "@/lib/dashboard-view";
import { modeCopy } from "@/lib/practice-view";
import { practiceState, practiseStoryHref, roleLabel } from "@/lib/story-view";

const t = copy.practice;

type Load =
  | { state: "loading" }
  | { state: "error" }
  | { state: "ready"; records: StoryPracticeRecord[]; roles: RoleProfileSummary[] };

/**
 * Where this story was practised: when, for which exact role, which version, and a link to
 * the review once there is one. Provenance only; nothing here grades the story.
 */
export function StoryPractice({ story }: { story: Story }) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  const archived = Boolean(story.archived_at);

  useEffect(() => {
    let live = true;
    setLoad({ state: "loading" });
    Promise.all([mirrorApi.storyPractice(story.id), mirrorApi.roles().catch(() => [] as RoleProfileSummary[])])
      .then(([records, roles]) => { if (live) setLoad({ state: "ready", records, roles }); })
      .catch(() => { if (live) setLoad({ state: "error" }); });
    return () => { live = false; };
  }, [story.id, attempt]);

  const action = archived ? null : (
    <Link className="dh-text-action" href={practiseStoryHref(story.id)}>
      {t.start} <ArrowRight size={15} aria-hidden="true" />
    </Link>
  );

  return (
    <Section id="story-practice" title={t.title} body={t.intro} action={action}>
      {load.state === "loading" ? <PageLoading /> : null}
      {load.state === "error" ? <PageAlert message={copy.errors.practice} onRetry={() => setAttempt((value) => value + 1)} /> : null}
      {load.state === "ready" && !load.records.length ? <p className="dh-fine-print">{t.none}</p> : null}
      {load.state === "ready" && load.records.length ? (
        <ul className="dh-row-list" aria-label={t.title}>
          {load.records.map((record) => {
            const state = practiceState(record);
            const day = formatShortDay(record.session_started_at ?? record.session_created_at);
            return (
              <li key={record.id}>
                <span className="dh-row-main">
                  <strong>{t.row(day, modeCopy(record.practice_mode).title)}</strong>
                  <small>
                    {record.role_profile_id ? `${roleLabel(record.role_profile_id, load.roles)} · ` : ""}
                    {t.version(record.story_version)}
                  </small>
                </span>
                <span className={`dh-row-state ${state.started ? "is-ready" : "is-muted"}`}>{state.label}</span>
                {state.reviewHref ? (
                  <Link className="dh-text-action" href={state.reviewHref}>
                    {t.review} <ArrowRight size={15} aria-hidden="true" />
                  </Link>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {archived ? <p className="dh-fine-print">{t.archivedNote}</p> : null}
    </Section>
  );
}
