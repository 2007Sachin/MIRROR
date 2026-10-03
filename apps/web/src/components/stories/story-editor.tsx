"use client";

import { Archive, ArrowCounterClockwise, ArrowRight, X } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { StoryHistory } from "@/components/stories/story-history";
import { StoryPractice } from "@/components/stories/story-practice";
import { StoryRoles } from "@/components/stories/story-roles";
import { storyActions } from "@/components/stories/stories-page";
import { StorySuggestions } from "@/components/stories/story-suggestions";
import { PageAlert, PageHeader, PageLoading, PageShell, usePageData } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type Story, type StoryInput, type StoryPart, type StorySuggestion } from "@/lib/api";
import { approvedEvidenceItem } from "@/lib/api-stories-guided";
import { stories as t } from "@/lib/copy";
import { storiesGuided as g, storyLibrary, type GuidedStep } from "@/lib/copy-stories";
import { STORY_PART_GROUPS, STORY_PART_ORDER, completenessClass, completenessLabel, partLabel, partPrompt, suggestionCopy, suggestionIsOlder } from "@/lib/story-view";
import "@/styles/stories-guided.css";

/** A story that does not exist (or is not yours) stays not found: no Retry. */
async function storyOrNull(storyId: string): Promise<Story | null> {
  try {
    return await mirrorApi.story(storyId);
  } catch (reason) {
    if (reason instanceof ApiError && (reason.status === 404 || reason.status === 422)) return null;
    throw reason;
  }
}

type Draft = { title: string; themes: string } & Record<StoryPart, string>;

const emptyDraft = (): Draft => ({
  title: "",
  themes: "",
  ...(Object.fromEntries(STORY_PART_ORDER.map((part) => [part, ""])) as Record<StoryPart, string>),
});

function draftFrom(story: Story): Draft {
  return {
    title: story.title,
    themes: story.themes.join(", "),
    ...(Object.fromEntries(STORY_PART_ORDER.map((part) => [part, story[part] ?? ""])) as Record<StoryPart, string>),
  };
}

function inputFrom(draft: Draft): StoryInput {
  const parts = Object.fromEntries(STORY_PART_ORDER.map((part) => [part, draft[part].trim() || null]));
  return {
    title: draft.title.trim(),
    themes: draft.themes.split(",").map((theme) => theme.trim()).filter(Boolean),
    ...parts,
  };
}

/** Editing an existing story. Saving a change adds a version; archiving is reversible. */
export function StoryEditor({ storyId }: { storyId: string }) {
  const router = useRouter();
  // Arriving from a review suggestion: its context is shown, but nothing is saved until the candidate saves.
  const suggestionId = useSearchParams().get("suggestion");
  const [suggestion, setSuggestion] = useState<StorySuggestion | null>(null);
  const { state, data, error, reload, setData } = usePageData(() => storyOrNull(storyId), t.errors.load, [storyId]);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [saveError, setSaveError] = useState("");
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (data) setDraft(draftFrom(data));
  }, [data]);

  useEffect(() => {
    if (!suggestionId) return;
    let live = true;
    mirrorApi
      .storySuggestions(storyId)
      .then((found) => { if (live) setSuggestion(found.find((item) => item.id === suggestionId && item.status === "OPEN") ?? null); })
      .catch(() => undefined);  // the editor works without it
    return () => { live = false; };
  }, [storyId, suggestionId]);

  useEffect(() => {
    if (!suggestion || !data || data.archived_at) return;
    const field = document.getElementById(`story-part-${suggestion.story_part}`);
    field?.scrollIntoView({ block: "center" });
    field?.focus();
  }, [suggestion, data]);

  const archived = Boolean(data?.archived_at);
  const unsavedChanges = data ? JSON.stringify(draft) !== JSON.stringify(draftFrom(data)) : false;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    setSaveError("");
    try {
      const before = data?.current_version ?? 0;
      const saved = await mirrorApi.updateStory(storyId, inputFrom(draft));
      setData(saved);
      setNotice(t.saved);
      if (suggestion && saved.current_version > before) {
        // The server accepts only if this save changed the part the suggestion is about.
        try {
          await mirrorApi.acceptStorySuggestion(suggestion.id, saved.current_version);
          setSuggestion(null);
          setNotice(t.suggestions.acceptedNotice);
        } catch {
          setNotice(t.suggestions.stillOpen);
        }
      }
    } catch (reason) {
      setSaveError(reason instanceof ApiError ? reason.message : t.errors.save);
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    setBusy(true);
    try {
      await mirrorApi.archiveStory(storyId);
      router.push("/stories");
    } catch {
      setSaveError(t.errors.archive);
      setBusy(false);
      setConfirming(false);
    }
  }

  async function restore() {
    setBusy(true);
    setNotice("");
    setSaveError("");
    try {
      setData(await mirrorApi.restoreStory(storyId));
      setNotice(t.archived.restored);
    } catch (reason) {
      setSaveError(reason instanceof ApiError ? reason.message : t.errors.restore);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell>
      <PageHeader eyebrow={t.eyebrow} title={data?.title ?? t.title} back={{ href: "/stories", label: t.back }} />
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}
      {state === "ready" && !data ? (
        <section className="dh-empty">
          <h2>{storyLibrary.notFound}</h2>
          <Link className="dh-primary-action" href="/stories">{g.backToStories}</Link>
        </section>
      ) : null}
      {state === "ready" && data ? (
        <>
          {archived ? (
            <div className="dh-guidance dh-story-archived" role="status">
              <p>{t.archived.notice}</p>
              <button className="dh-primary-action" type="button" onClick={() => void restore()} disabled={busy}>
                <ArrowCounterClockwise size={16} aria-hidden="true" /> {busy ? t.archived.restoring : t.archived.restore}
              </button>
            </div>
          ) : null}
          <p className="dh-step-count">
            <span className={`dh-row-state ${completenessClass(data)}`}>{completenessLabel(data)}</span> · {t.from[data.origin]}
          </p>
          {data.source_text ? (
            <p className="dh-guidance">
              <strong>{t.sourceLabel}:</strong> “{data.source_text}”
            </p>
          ) : null}
          {suggestion ? (
            <div className="dh-guidance dh-story-suggestion-banner" role="note">
              <p className="dh-subhead">{t.suggestions.banner}</p>
              <strong>{suggestionCopy(suggestion).title}</strong>
              <p>{suggestionCopy(suggestion).why}</p>
              <p className="dh-fine-print">{t.suggestions.part(partLabel(suggestion.story_part))}</p>
              {suggestionIsOlder(suggestion) ? (
                <p className="dh-fine-print dh-story-older">{t.suggestions.olderVersion(suggestion.practised_version, suggestion.current_version)}</p>
              ) : null}
              <p className="dh-fine-print">{archived ? t.suggestions.archived : t.suggestions.bannerNote}</p>
            </div>
          ) : null}
          <StoryForm
            draft={draft}
            onChange={setDraft}
            onSubmit={save}
            busy={busy}
            emphasize={suggestion?.story_part ?? null}
            readOnly={archived}
            submitLabel={busy ? t.saving : t.save}
          />
          {notice ? <p className="dh-notice" role="status">{notice}</p> : null}
          {saveError ? <PageAlert message={saveError} /> : null}

          {/* Actionable and reusable first: an open suggestion, then who this story is for,
              then where it has been practised. Version history and archiving are secondary
              to normal use, so they sit last, and history stays closed until asked for. */}
          <StorySuggestions story={data} />
          <StoryRoles story={data} />
          <StoryPractice story={data} />
          <details className="dh-story-history-disclosure">
            <summary>{t.history.disclosure}</summary>
            <StoryHistory
              story={data}
              unsavedChanges={unsavedChanges}
              onRestored={(story, message) => { setData(story); setSaveError(""); setNotice(message); }}
            />
          </details>
          {archived ? null : (
            <div className="dh-action-row dh-story-manage">
              <button className="dh-text-action is-quiet" type="button" onClick={() => setConfirming(true)} disabled={busy}>
                <Archive size={15} aria-hidden="true" /> {t.archive}
              </button>
            </div>
          )}
          {confirming ? <ArchiveDialog busy={busy} onCancel={() => setConfirming(false)} onConfirm={() => void archive()} /> : null}
        </>
      ) : null}
    </PageShell>
  );
}

/**
 * Adding a story: one question at a time (context, challenge, action, result, learning),
 * with "Save for later" on every step. Editing an existing story uses the full form above.
 */
export function NewStory() {
  const params = useSearchParams();
  const theme = params.get("theme")?.trim() || "";
  const roleProfileId = params.get("role");
  const evidenceId = params.get("evidence");
  const steps = g.steps;
  const [draft, setDraft] = useState<Draft>(() => ({ ...emptyDraft(), themes: theme }));
  const [source, setSource] = useState<string | null>(null);
  const [why, setWhy] = useState(theme ? g.why.theme(theme) : "");
  const [step, setStep] = useState(0);
  const [saved, setSaved] = useState<Story | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [saveError, setSaveError] = useState("");
  const [retryFinish, setRetryFinish] = useState(false);
  const field = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    let live = true;
    if (evidenceId) {
      // Only an APPROVED experience item may start a story; anything else starts blank.
      approvedEvidenceItem(evidenceId)
        .then((item) => {
          if (!live) return;
          if (!item) { setWhy(g.why.notApproved); return; }
          setSource([item.title, item.detail].filter(Boolean).join(" ").slice(0, 3000));
          setDraft((current) => (current.title.trim() ? current : { ...current, title: item.title.slice(0, 200) }));
          setWhy(g.why.experience);
        })
        .catch(() => undefined);  // a blank story still works
    } else if (roleProfileId && theme) {
      mirrorApi
        .roles()
        .then((roles) => {
          const role = roles.find((item) => item.id === roleProfileId);
          if (live && role) setWhy(g.why.roleTheme(role.target_role, theme));
        })
        .catch(() => undefined);  // the general line stays
    }
    return () => { live = false; };
  }, [evidenceId, roleProfileId, theme]);

  useEffect(() => {
    field.current?.focus();
  }, [step]);

  async function persist(finish: boolean) {
    setBusy(true);
    setNotice("");
    setSaveError("");
    setRetryFinish(finish);
    try {
      const content = { ...inputFrom(draft), title: draft.title.trim() || (theme ? g.titleFor(theme) : g.untitled) };
      const story = saved
        ? await mirrorApi.updateStory(saved.id, content)
        : await mirrorApi.createStory({
            ...content,
            role_profile_id: roleProfileId || null,
            source_text: source,
            origin: source ? "EXPERIENCE" : theme ? "FIND_A_STORY" : "MANUAL",
          });
      setSaved(story);
      setNotice(g.saved);
      if (finish) setDone(true);
    } catch (reason) {
      // The draft is never cleared on failure: everything typed stays in the fields.
      setSaveError(reason instanceof ApiError ? reason.message : g.errors.save);
    } finally {
      setBusy(false);
    }
  }

  const current: GuidedStep = steps[step];
  const extra = current.extra;
  const last = step === steps.length - 1;
  const next = done && saved ? storyActions(saved)[0] : null;

  return (
    <PageShell>
      <PageHeader eyebrow={t.eyebrow} title={theme ? g.titleFor(theme) : g.title} intro={g.intro} back={{ href: "/stories", label: t.back }} />
      {why ? <p className="sg-why">{why}</p> : null}
      {roleProfileId ? (
        <p className="dh-fine-print dh-story-reuse">
          {t.roles.reuse} <Link className="dh-text-action" href="/stories">{t.roles.reuseLink}</Link>
        </p>
      ) : null}
      {source ? (
        <p className="dh-guidance">
          <strong>{g.basedOn}:</strong> “{source}”
        </p>
      ) : null}

      {next ? (
        <section className="sg-done" role="status">
          <p>{g.saved}</p>
          <div className="dh-action-row">
            <Link className="dh-primary-action" href={next.href}>{next.label}</Link>
            <Link className="dh-text-action" href="/stories">{g.backToStories}</Link>
          </div>
        </section>
      ) : (
        <div className="sg-builder" aria-busy={busy}>
          <label className="dh-form is-wide sg-name">
            <span>{g.nameLabel}</span>
            <input className="field" value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} maxLength={200} />
            <small>{g.nameHint}</small>
          </label>

          <ol className="sg-steps">
            {steps.map((item, index) => (
              <li key={item.key} className={index < step ? "is-done" : index === step ? "is-current" : undefined} aria-current={index === step ? "step" : undefined}>
                {item.name}
              </li>
            ))}
          </ol>
          <p className="sg-progress" aria-live="polite">
            {g.progress(step + 1, steps.length)} · {current.name}
          </p>

          <label className="dh-form is-wide">
            <span className="dh-answer-question">{current.question(theme)}</span>
            <textarea
              ref={field}
              className="field"
              rows={5}
              value={draft[current.part]}
              onChange={(event) => setDraft({ ...draft, [current.part]: event.target.value })}
              maxLength={4000}
            />
            <small>{current.hint}</small>
          </label>
          {extra ? (
            <label className="dh-form is-wide sg-extra">
              <span>{extra.label}</span>
              <textarea
                className="field"
                rows={3}
                value={draft[extra.part]}
                onChange={(event) => setDraft({ ...draft, [extra.part]: event.target.value })}
                maxLength={4000}
              />
            </label>
          ) : null}

          <div className="dh-action-row">
            {step > 0 ? (
              <button className="dh-primary-action is-quiet" type="button" onClick={() => setStep(step - 1)} disabled={busy}>
                {g.back}
              </button>
            ) : null}
            {last ? (
              <button className="dh-primary-action" type="button" onClick={() => void persist(true)} disabled={busy}>
                {busy ? g.saving : g.finish}
              </button>
            ) : (
              <button className="dh-primary-action" type="button" onClick={() => setStep(step + 1)} disabled={busy}>
                {g.next} <ArrowRight size={16} aria-hidden="true" />
              </button>
            )}
            <button className="dh-text-action" type="button" onClick={() => void persist(false)} disabled={busy}>
              {busy ? g.saving : g.saveForLater}
            </button>
          </div>
        </div>
      )}

      {notice && !done ? (
        <p className="dh-notice" role="status">
          {notice} <Link className="dh-text-action" href="/stories">{g.backToStories}</Link>
        </p>
      ) : null}
      {saveError ? <PageAlert message={saveError} onRetry={() => void persist(retryFinish)} retryLabel={g.errors.retry} /> : null}
    </PageShell>
  );
}

function StoryForm({
  draft,
  onChange,
  onSubmit,
  busy,
  readOnly = false,
  emphasize = null,
  submitLabel,
}: {
  draft: Draft;
  onChange: (next: Draft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  busy: boolean;
  readOnly?: boolean;
  emphasize?: StoryPart | null;
  submitLabel: string;
}) {
  const locked = busy || readOnly;
  return (
    <form className="dh-form is-wide" onSubmit={onSubmit} aria-busy={busy}>
      <label>
        <span>{t.titleLabel}</span>
        <input className="field" value={draft.title} onChange={(event) => onChange({ ...draft, title: event.target.value })} required minLength={2} maxLength={200} disabled={locked} readOnly={readOnly} />
        <small>{t.titleHint}</small>
      </label>
      <label>
        <span>{t.themesLabel}</span>
        <input className="field" value={draft.themes} onChange={(event) => onChange({ ...draft, themes: event.target.value })} disabled={locked} readOnly={readOnly} />
        <small>{t.themesHint}</small>
      </label>
      {STORY_PART_GROUPS.map((group) => (
        <fieldset key={group.key} className="dh-story-part-group">
          <legend>{group.label}</legend>
          {group.parts.map((part) => (
            <label key={part} className={emphasize === part ? "is-suggested" : undefined}>
              <span>{partLabel(part)}</span>
              <textarea id={`story-part-${part}`} className="field" rows={3} value={draft[part]} onChange={(event) => onChange({ ...draft, [part]: event.target.value })} maxLength={4000} disabled={locked} readOnly={readOnly} />
              <small>{partPrompt(part)}</small>
            </label>
          ))}
        </fieldset>
      ))}
      {readOnly ? null : (
        <button className="dh-primary-action" type="submit" disabled={busy || draft.title.trim().length < 2}>
          {submitLabel}
        </button>
      )}
    </form>
  );
}

function ArchiveDialog({ busy, onCancel, onConfirm }: { busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    if (node && !node.open) node.showModal();
    return () => { if (node?.open) node.close(); };
  }, []);
  return (
    <dialog ref={dialog} className="dh-role-dialog" aria-labelledby="story-archive-title" aria-describedby="story-archive-body" onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}>
      <div className="dh-role-dialog-panel">
        <header>
          <div>
            <h2 id="story-archive-title">{t.archiveTitle}</h2>
            <p id="story-archive-body">{t.archiveBody}</p>
          </div>
          <button type="button" className="dh-dialog-close" onClick={onCancel} disabled={busy} aria-label={t.cancel}>
            <X size={19} aria-hidden="true" />
          </button>
        </header>
        <div className="dh-action-row">
          <button className="dh-primary-action is-quiet" type="button" onClick={onCancel} disabled={busy}>{t.cancel}</button>
          <button className="dh-primary-action" type="button" onClick={onConfirm} disabled={busy}>{t.confirmArchive}</button>
        </div>
      </div>
    </dialog>
  );
}
