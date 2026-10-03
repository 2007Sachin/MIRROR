"use client";

import { useEffect, useState } from "react";

import { PageAlert, PageLoading, Section } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type Story, type StoryVersion } from "@/lib/api";
import { stories as t } from "@/lib/copy";
import { formatShortDay } from "@/lib/dashboard-view";
import { STORY_PART_ORDER, partLabel, versionSummary } from "@/lib/story-view";

type Load = { state: "loading" } | { state: "error" } | { state: "ready"; versions: StoryVersion[] };

/**
 * A story's saved versions, newest first. Earlier versions are shown read-only; bringing
 * one back asks the backend to add it as a new current version, so history only grows.
 */
export function StoryHistory({
  story,
  unsavedChanges,
  onRestored,
}: {
  story: Story;
  unsavedChanges: boolean;
  onRestored: (story: Story, message: string) => void;
}) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [restoreError, setRestoreError] = useState("");

  useEffect(() => {
    let live = true;
    setLoad({ state: "loading" });
    mirrorApi
      .storyVersions(story.id)
      .then((versions) => { if (live) setLoad({ state: "ready", versions }); })
      .catch(() => { if (live) setLoad({ state: "error" }); });
    return () => { live = false; };
  }, [story.id, story.current_version, attempt]);

  async function restore(version: StoryVersion) {
    setBusy(true);
    setRestoreError("");
    try {
      const restored = await mirrorApi.restoreStoryVersion(story.id, version.id);
      setOpenId(null);
      onRestored(restored, t.history.restored(version.version));
    } catch (reason) {
      setRestoreError(reason instanceof ApiError ? reason.message : t.errors.restoreVersion);
    } finally {
      setBusy(false);
    }
  }

  const archived = Boolean(story.archived_at);

  return (
    <Section id="story-history" title={t.history.title} body={t.history.intro}>
      {load.state === "loading" ? <PageLoading /> : null}
      {load.state === "error" ? (
        <PageAlert message={t.errors.history} onRetry={() => setAttempt((value) => value + 1)} />
      ) : null}
      {load.state === "ready" ? (
        <>
          {load.versions.length <= 1 ? <p className="dh-fine-print">{t.history.onlyOne}</p> : null}
          <ul className="dh-row-list" aria-label={t.history.title}>
            {load.versions.map((version) => {
              const current = version.version === story.current_version;
              const open = openId === version.id;
              return (
                <li key={version.id} className="dh-story-version-row">
                  <span className="dh-row-main">
                    <strong>{t.history.version(version.version)}</strong>
                    <small>{versionSummary(version, formatShortDay(version.created_at))}</small>
                  </span>
                  <span className={`dh-row-state ${current ? "is-ready" : "is-muted"}`}>
                    {current ? t.history.current : t.history.earlier}
                  </span>
                  {current ? null : (
                    <button
                      type="button"
                      className="dh-text-action"
                      aria-expanded={open}
                      aria-controls={`story-version-${version.id}`}
                      onClick={() => { setRestoreError(""); setOpenId(open ? null : version.id); }}
                    >
                      {open ? t.history.hide : t.history.view}
                    </button>
                  )}
                  {open ? (
                    <EarlierVersion
                      version={version}
                      busy={busy}
                      blocked={archived ? t.history.archivedFirst : unsavedChanges ? t.history.saveFirst : ""}
                      error={restoreError}
                      onRestore={() => void restore(version)}
                    />
                  ) : null}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
    </Section>
  );
}

function EarlierVersion({
  version,
  busy,
  blocked,
  error,
  onRestore,
}: {
  version: StoryVersion;
  busy: boolean;
  blocked: string;
  error: string;
  onRestore: () => void;
}) {
  return (
    <div className="dh-drill dh-story-version" id={`story-version-${version.id}`} aria-label={t.history.version(version.version)}>
      <p className="dh-guidance">{t.history.readOnly}</p>
      <dl>
        <div className="dh-story-version-part">
          <dt>{t.titleLabel}</dt>
          <dd>{version.title}</dd>
        </div>
        <div className="dh-story-version-part">
          <dt>{t.themesLabel}</dt>
          <dd>{version.themes.length ? version.themes.join(", ") : <span className="is-empty">{t.history.empty}</span>}</dd>
        </div>
        {STORY_PART_ORDER.map((part) => (
          <div key={part} className="dh-story-version-part">
            <dt>{partLabel(part)}</dt>
            <dd>{version[part] ? version[part] : <span className="is-empty">{t.history.empty}</span>}</dd>
          </div>
        ))}
      </dl>
      <div className="dh-action-row">
        <button className="dh-primary-action" type="button" onClick={onRestore} disabled={busy || Boolean(blocked)}>
          {busy ? t.history.restoring : t.history.restore}
        </button>
      </div>
      <p className="dh-fine-print">{blocked || t.history.restoreNote}</p>
      {error ? <PageAlert message={error} /> : null}
    </div>
  );
}
