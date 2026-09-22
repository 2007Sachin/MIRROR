"use client";

import { ArrowRight, Trash, X } from "@phosphor-icons/react";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { PageAlert, PageHeader, PageLoading, PageShell, usePageData } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type Story, type StoryInput, type StoryPart } from "@/lib/api";
import { stories as t } from "@/lib/copy";
import { STORY_PART_ORDER, completenessClass, completenessLabel, partLabel, partPrompt } from "@/lib/story-view";

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

/** Editing an existing story. */
export function StoryEditor({ storyId }: { storyId: string }) {
  const router = useRouter();
  const { state, data, error, reload, setData } = usePageData(() => mirrorApi.story(storyId), t.errors.load, [storyId]);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [saveError, setSaveError] = useState("");
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (data) setDraft(draftFrom(data));
  }, [data]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    setSaveError("");
    try {
      setData(await mirrorApi.updateStory(storyId, inputFrom(draft)));
      setNotice(t.saved);
    } catch (reason) {
      setSaveError(reason instanceof ApiError ? reason.message : t.errors.save);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await mirrorApi.deleteStory(storyId);
      router.push("/stories");
    } catch {
      setSaveError(t.errors.delete);
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <PageShell>
      <PageHeader eyebrow={t.eyebrow} title={data?.title ?? t.title} back={{ href: "/stories", label: t.back }} />
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}
      {state === "ready" && data ? (
        <>
          <p className="dh-step-count">
            <span className={`dh-row-state ${completenessClass(data)}`}>{completenessLabel(data)}</span> · {t.from[data.origin]}
          </p>
          {data.source_text ? (
            <p className="dh-guidance">
              <strong>{t.sourceLabel}:</strong> “{data.source_text}”
            </p>
          ) : null}
          <StoryForm draft={draft} onChange={setDraft} onSubmit={save} busy={busy} submitLabel={busy ? t.saving : t.save} />
          {notice ? <p className="dh-notice" role="status">{notice}</p> : null}
          {saveError ? <PageAlert message={saveError} /> : null}
          <div className="dh-action-row">
            <button className="dh-text-action is-quiet" type="button" onClick={() => setConfirming(true)} disabled={busy}>
              <Trash size={15} aria-hidden="true" /> {t.delete}
            </button>
          </div>
          {confirming ? <DeleteDialog busy={busy} onCancel={() => setConfirming(false)} onConfirm={() => void remove()} /> : null}
        </>
      ) : null}
    </PageShell>
  );
}

/** Adding a story: a plain form, or one guided prompt at a time. */
export function NewStory() {
  const router = useRouter();
  const params = useSearchParams();
  const guided = params.get("guided") === "1";
  const theme = params.get("theme")?.trim() || "";
  const roleProfileId = params.get("role");
  const [draft, setDraft] = useState<Draft>(() => ({ ...emptyDraft(), themes: theme }));
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState("");

  async function create(input: StoryInput) {
    setBusy(true);
    setSaveError("");
    try {
      const story = await mirrorApi.createStory({
        ...input,
        role_profile_id: roleProfileId || null,
        origin: guided ? "FIND_A_STORY" : "MANUAL",
      });
      router.push(`/stories/${story.id}`);
    } catch (reason) {
      setSaveError(reason instanceof ApiError ? reason.message : t.errors.save);
      setBusy(false);
    }
  }

  return (
    <PageShell>
      <PageHeader
        eyebrow={guided ? t.guide.eyebrow : t.eyebrow}
        title={guided ? (theme ? t.guide.title(theme) : t.guide.titleGeneral) : t.add}
        intro={guided ? t.guide.intro : undefined}
        back={{ href: "/stories", label: t.back }}
      />
      {guided ? (
        <GuidedStory theme={theme} draft={draft} onChange={setDraft} busy={busy} onFinish={() => void create(inputFrom(draft))} />
      ) : (
        <StoryForm
          draft={draft}
          onChange={setDraft}
          onSubmit={(event) => { event.preventDefault(); void create(inputFrom(draft)); }}
          busy={busy}
          submitLabel={busy ? t.saving : t.save}
        />
      )}
      {saveError ? <PageAlert message={saveError} /> : null}
    </PageShell>
  );
}

function StoryForm({
  draft,
  onChange,
  onSubmit,
  busy,
  submitLabel,
}: {
  draft: Draft;
  onChange: (next: Draft) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  busy: boolean;
  submitLabel: string;
}) {
  return (
    <form className="dh-form is-wide" onSubmit={onSubmit} aria-busy={busy}>
      <label>
        <span>{t.titleLabel}</span>
        <input className="field" value={draft.title} onChange={(event) => onChange({ ...draft, title: event.target.value })} required minLength={2} maxLength={200} disabled={busy} />
        <small>{t.titleHint}</small>
      </label>
      <label>
        <span>{t.themesLabel}</span>
        <input className="field" value={draft.themes} onChange={(event) => onChange({ ...draft, themes: event.target.value })} disabled={busy} />
        <small>{t.themesHint}</small>
      </label>
      {STORY_PART_ORDER.map((part) => (
        <label key={part}>
          <span>{partLabel(part)}</span>
          <textarea className="field" rows={3} value={draft[part]} onChange={(event) => onChange({ ...draft, [part]: event.target.value })} maxLength={4000} disabled={busy} />
          <small>{partPrompt(part)}</small>
        </label>
      ))}
      <button className="dh-primary-action" type="submit" disabled={busy || draft.title.trim().length < 2}>
        {submitLabel}
      </button>
    </form>
  );
}

/**
 * "Help me find a story": Mirror asks one question at a time, the candidate answers.
 * The title is asked last, once they know what the story is about.
 */
function GuidedStory({
  theme,
  draft,
  onChange,
  busy,
  onFinish,
}: {
  theme: string;
  draft: Draft;
  onChange: (next: Draft) => void;
  busy: boolean;
  onFinish: () => void;
}) {
  const prompts = t.guide.prompts;
  const total = prompts.length + 1;
  const [step, setStep] = useState(0);
  const field = useRef<HTMLTextAreaElement | HTMLInputElement | null>(null);

  useEffect(() => {
    field.current?.focus();
  }, [step]);

  const onTitle = step === prompts.length;
  const prompt = onTitle ? null : prompts[step];
  const part = prompt?.part as StoryPart | undefined;

  return (
    <div className="dh-drill">
      <p className="dh-step-count" aria-live="polite">{t.guide.step(step + 1, total)}</p>
      {prompt && part ? (
        <label className="dh-form is-wide">
          <span className="dh-answer-question">{prompt.prompt(theme || "this")}</span>
          <textarea
            ref={(node) => { field.current = node; }}
            className="field"
            rows={5}
            value={draft[part]}
            onChange={(event) => onChange({ ...draft, [part]: event.target.value })}
            maxLength={4000}
          />
          {step === 0 ? <small>{t.guide.nothingYet}</small> : <small>{partPrompt(part)}</small>}
        </label>
      ) : (
        <label className="dh-form is-wide">
          <span className="dh-answer-question">{t.titleLabel}</span>
          <input
            ref={(node) => { field.current = node; }}
            className="field"
            value={draft.title}
            onChange={(event) => onChange({ ...draft, title: event.target.value })}
            maxLength={200}
          />
          <small>{t.titleHint}</small>
        </label>
      )}
      <div className="dh-action-row">
        {step > 0 ? (
          <button className="dh-primary-action is-quiet" type="button" onClick={() => setStep(step - 1)} disabled={busy}>
            {t.guide.back}
          </button>
        ) : null}
        {onTitle ? (
          <button className="dh-primary-action" type="button" onClick={onFinish} disabled={busy || draft.title.trim().length < 2}>
            {busy ? t.saving : t.guide.finish}
          </button>
        ) : (
          <button className="dh-primary-action" type="button" onClick={() => setStep(step + 1)}>
            {t.guide.next} <ArrowRight size={16} aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}

function DeleteDialog({ busy, onCancel, onConfirm }: { busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    if (node && !node.open) node.showModal();
    return () => { if (node?.open) node.close(); };
  }, []);
  return (
    <dialog ref={dialog} className="dh-role-dialog" aria-labelledby="story-delete-title" onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}>
      <div className="dh-role-dialog-panel">
        <header>
          <div>
            <h2 id="story-delete-title">{t.deleteTitle}</h2>
            <p>{t.deleteBody}</p>
          </div>
          <button type="button" className="dh-dialog-close" onClick={onCancel} disabled={busy} aria-label={t.cancel}>
            <X size={19} aria-hidden="true" />
          </button>
        </header>
        <div className="dh-action-row">
          <button className="dh-primary-action is-quiet" type="button" onClick={onCancel} disabled={busy}>{t.cancel}</button>
          <button className="dh-primary-action is-danger" type="button" onClick={onConfirm} disabled={busy}>{t.confirmDelete}</button>
        </div>
      </div>
    </dialog>
  );
}
