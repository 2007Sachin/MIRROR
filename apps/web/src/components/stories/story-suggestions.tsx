"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageAlert, PageLoading, Section } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type RoleProfileSummary, type Story, type StorySuggestion } from "@/lib/api";
import { stories as copy } from "@/lib/copy";
import { formatShortDay } from "@/lib/dashboard-view";
import { improveHref, partLabel, roleLabel, suggestionCopy, suggestionIsOlder } from "@/lib/story-view";

const t = copy.suggestions;

/** One open suggestion: what Review noticed, where it belongs, and the candidate's two choices. */
export function SuggestionCard({
  suggestion,
  roles,
  onDismissed,
  showTitle = false,
}: {
  suggestion: StorySuggestion;
  roles?: RoleProfileSummary[];
  onDismissed: (next: StorySuggestion) => void;
  showTitle?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const text = suggestionCopy(suggestion);

  async function dismiss() {
    setBusy(true);
    setError("");
    try {
      onDismissed(await mirrorApi.dismissStorySuggestion(suggestion.id));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : copy.errors.dismiss);
      setBusy(false);
    }
  }

  return (
    <li className="dh-story-suggestion">
      <span className="dh-row-main">
        {showTitle ? <small className="dh-story-useful-for">{suggestion.story_title}</small> : null}
        <strong>{text.title}</strong>
        <small>{text.why}</small>
        <small>
          {t.part(partLabel(suggestion.story_part))} · {t.practised(suggestion.practised_version, formatShortDay(suggestion.created_at))}
          {roles && suggestion.role_profile_id ? ` · ${roleLabel(suggestion.role_profile_id, roles)}` : ""}
        </small>
        {suggestionIsOlder(suggestion) ? <small className="dh-story-older">{t.olderVersion(suggestion.practised_version, suggestion.current_version)}</small> : null}
        {suggestion.story_archived ? <small className="dh-story-older">{t.archived}</small> : null}
      </span>
      <span className="dh-row-actions">
        {suggestion.story_archived ? null : (
          <Link className="dh-text-action" href={improveHref(suggestion)}>
            {t.improve} <ArrowRight size={15} aria-hidden="true" />
          </Link>
        )}
        <button type="button" className="dh-text-action is-quiet" onClick={() => void dismiss()} disabled={busy}>
          {busy ? t.dismissing : t.dismiss}
        </button>
      </span>
      {error ? <PageAlert message={error} /> : null}
    </li>
  );
}

/** Suggested improvements on the story page: open ones first, earlier ones folded away. */
export function StorySuggestions({ story }: { story: Story }) {
  const [items, setItems] = useState<StorySuggestion[] | null>(null);
  const [roles, setRoles] = useState<RoleProfileSummary[]>([]);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setItems(null);
    setFailed(false);
    Promise.all([mirrorApi.storySuggestions(story.id), mirrorApi.roles().catch(() => [] as RoleProfileSummary[])])
      .then(([found, owned]) => { if (live) { setItems(found); setRoles(owned); } })
      .catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [story.id, story.current_version, story.archived_at, attempt]);

  if (!failed && items !== null && !items.length) return null;  // nothing from any review: stay out of the way
  const open = (items ?? []).filter((item) => item.status === "OPEN");
  const earlier = (items ?? []).filter((item) => item.status !== "OPEN");
  const replace = (next: StorySuggestion) => setItems((current) => (current ?? []).map((item) => (item.id === next.id ? next : item)));

  return (
    <Section id="story-suggestions" title={t.title} body={t.intro}>
      {items === null && !failed ? <PageLoading /> : null}
      {failed ? <PageAlert message={copy.errors.suggestions} onRetry={() => setAttempt((value) => value + 1)} /> : null}
      {open.length ? (
        <ul className="dh-row-list" aria-label={t.title}>
          {open.map((item) => <SuggestionCard key={item.id} suggestion={item} roles={roles} onDismissed={replace} />)}
        </ul>
      ) : items?.length ? <p className="dh-fine-print">{t.none}</p> : null}
      {earlier.length ? (
        <details className="dh-first-answer">
          <summary>{t.earlier(earlier.length)}</summary>
          <ul className="dh-row-list">
            {earlier.map((item) => (
              <li key={item.id}>
                <span className="dh-row-main">
                  <strong>{suggestionCopy(item).title}</strong>
                  <small>{t.practised(item.practised_version, formatShortDay(item.created_at))}</small>
                </span>
                <span className="dh-row-state is-muted">{item.status === "ACCEPTED" ? t.accepted(item.resolved_version) : t.dismissed}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Section>
  );
}

/** On Review: open suggestions for the stories this practice used. Silent when there are none. */
export function ReviewStorySuggestions({ sessionId }: { sessionId: string }) {
  const [items, setItems] = useState<StorySuggestion[]>([]);

  useEffect(() => {
    let live = true;
    // A review must never break because suggestions are unavailable: fail quietly.
    mirrorApi.sessionStorySuggestions(sessionId).then((found) => { if (live) setItems(found); }).catch(() => undefined);
    return () => { live = false; };
  }, [sessionId]);

  const open = items.filter((item) => item.status === "OPEN");
  if (!open.length) return null;
  return (
    <Section id="review-story-suggestions" label={t.reviewTitle} title={t.reviewTitle} body={t.reviewIntro}>
      <ul className="dh-row-list">
        {open.map((item) => (
          <SuggestionCard
            key={item.id}
            suggestion={item}
            showTitle
            onDismissed={(next) => setItems((current) => current.map((row) => (row.id === next.id ? next : row)))}
          />
        ))}
      </ul>
    </Section>
  );
}
