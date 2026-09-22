"use client";

import { ArrowRight, Check, Minus } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { RoleTabs } from "@/components/roles/role-tabs";
import { PageAlert, PageHeader, PageLoading, PageShell, usePageData } from "@/components/workspace/page-shell";
import {
  ApiError,
  mirrorApi,
  type AnswerChecks,
  type PressureReadiness,
  type PressureTest,
  type StoryPart,
} from "@/lib/api";
import { experience as experienceCopy, pressureTest as t, roles as rolesCopy } from "@/lib/copy";
import { storyFromAnswers } from "@/lib/story-view";

type Item = PressureTest["items"][number];

export function PressureTestPage({ roleProfileId }: { roleProfileId: string }) {
  const { state, data, error, reload, setData } = usePageData(
    () => mirrorApi.pressureTest(roleProfileId),
    t.errors.load,
    [roleProfileId],
  );
  const [open, setOpen] = useState<string | null>(null);

  function replaceItem(next: Item) {
    if (!data) return;
    setData({ ...data, items: data.items.map((item) => (item.claim_id === next.claim_id ? next : item)) });
  }

  return (
    <PageShell>
      <PageHeader
        eyebrow={rolesCopy.eyebrow}
        title={t.title}
        intro={t.intro}
        back={{ href: "/roles", label: rolesCopy.detail.back }}
      />
      <RoleTabs roleProfileId={roleProfileId} current="pressure" />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && data && data.state !== "READY" ? (
        <section className="dh-empty">
          <p>{t.states[data.state]}</p>
          <Link className="dh-primary-action" href="/experience">
            {experienceCopy.title} <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </section>
      ) : null}

      {state === "ready" && data?.state === "READY" ? (
        <ol className="dh-pressure-list">
          {data.items.map((item) => (
            <li key={item.claim_id}>
              <PressureItemView
                item={item}
                roleProfileId={roleProfileId}
                open={open === item.claim_id}
                onOpen={() => setOpen(open === item.claim_id ? null : item.claim_id)}
                onChange={replaceItem}
              />
            </li>
          ))}
        </ol>
      ) : null}
    </PageShell>
  );
}

function PressureItemView({
  item,
  roleProfileId,
  open,
  onOpen,
  onChange,
}: {
  item: Item;
  roleProfileId: string;
  open: boolean;
  onOpen: () => void;
  onChange: (next: Item) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  async function mark(readiness: PressureReadiness) {
    setSaving(true);
    setSaveError("");
    try {
      await mirrorApi.setPressureReadiness(item.claim_id, readiness);
      onChange({ ...item, readiness });
    } catch {
      setSaveError(t.errors.save);
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="dh-pressure-item">
      <blockquote className="dh-pressure-statement">{item.statement}</blockquote>
      <p className="dh-fine-print">
        {t.where}: {item.where}
        {item.related_theme ? ` · ${t.relatedTo} ${item.related_theme}` : ""}
      </p>

      <h3 className="dh-subhead">{t.mayAsk}</h3>
      <ul className="dh-step-list is-plain">
        {item.questions.map((question) => (
          <li key={question.kind}>{question.text}</li>
        ))}
      </ul>

      <fieldset className="dh-pressure-ready" disabled={saving}>
        <legend>{t.howReady}</legend>
        <button type="button" aria-pressed={item.readiness === "CAN_EXPLAIN"} onClick={() => void mark("CAN_EXPLAIN")}>
          {item.readiness === "CAN_EXPLAIN" ? <Check size={15} aria-hidden="true" /> : null} {t.canExplain}
        </button>
        <button type="button" aria-pressed={item.readiness === "NEEDS_PREPARATION"} onClick={() => void mark("NEEDS_PREPARATION")}>
          {item.readiness === "NEEDS_PREPARATION" ? <Check size={15} aria-hidden="true" /> : null} {t.needPrepare}
        </button>
      </fieldset>
      {saveError ? <p className="dh-inline-error" role="alert">{saveError}</p> : null}

      <div className="dh-action-row">
        <button className="dh-primary-action" type="button" onClick={onOpen} aria-expanded={open}>
          {open ? t.stop : t.start}
        </button>
        {item.story_id ? (
          <Link className="dh-text-action" href={`/stories/${item.story_id}`}>
            {t.savedStory} <ArrowRight size={15} aria-hidden="true" />
          </Link>
        ) : null}
      </div>

      {open ? <PressureDrill item={item} roleProfileId={roleProfileId} onSaved={(storyId) => onChange({ ...item, story_id: storyId })} /> : null}
    </article>
  );
}

/** One question at a time, the candidate's own words, and a note on what the answer contains. */
function PressureDrill({
  item,
  roleProfileId,
  onSaved,
}: {
  item: Item;
  roleProfileId: string;
  onSaved: (storyId: string) => void;
}) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState("");
  const [answers, setAnswers] = useState<Array<{ part: StoryPart; answer: string }>>([]);
  const [checks, setChecks] = useState<AnswerChecks | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const question = item.questions[step];
  const last = step === item.questions.length - 1;

  async function check() {
    if (!draft.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      setChecks(await mirrorApi.answerChecks(question.kind, draft.trim()));
    } catch {
      setMessage(t.errors.check);
    } finally {
      setBusy(false);
    }
  }

  function keep() {
    const next = draft.trim() ? [...answers, { part: question.story_part, answer: draft.trim() }] : answers;
    setAnswers(next);
    setDraft("");
    setChecks(null);
    return next;
  }

  async function save(collected: Array<{ part: StoryPart; answer: string }>) {
    setBusy(true);
    setMessage("");
    try {
      const story = await mirrorApi.createStory(
        storyFromAnswers({
          statement: item.statement,
          claimId: item.claim_id,
          roleProfileId,
          theme: item.related_theme,
          answers: collected,
        }),
      );
      onSaved(story.id);
      router.push(`/stories/${story.id}`);
    } catch (reason) {
      setMessage(reason instanceof ApiError ? reason.message : t.errors.save);
      setBusy(false);
    }
  }

  return (
    <div className="dh-drill" aria-live="polite">
      <p className="dh-step-count">{t.question(step + 1, item.questions.length)}</p>
      <p className="dh-answer-question">{question.text}</p>
      <p className="dh-fine-print">{question.why}</p>

      <label className="dh-form is-wide">
        <span>{t.answerLabel}</span>
        <textarea className="field" rows={5} value={draft} onChange={(event) => setDraft(event.target.value)} disabled={busy} />
        <small>{t.answerHint}</small>
      </label>

      {checks ? (
        <div className="dh-answer-note">
          <h3>{t.noticed}</h3>
          <ul className="dh-check-list">
            {checks.checks.map((item) => (
              <li key={item.key} className={item.present ? "is-present" : "is-absent"}>
                {item.present ? <Check size={15} aria-hidden="true" /> : <Minus size={15} aria-hidden="true" />}
                <span>{item.text}</span>
              </li>
            ))}
          </ul>
          {checks.follow_up ? <p className="dh-prose"><strong>{t.tryFollowUp}:</strong> {checks.follow_up}</p> : null}
          <p className="dh-fine-print">{t.checksNote}</p>
        </div>
      ) : null}
      {message ? <p className="dh-inline-error" role="alert">{message}</p> : null}

      <div className="dh-action-row">
        <button className="dh-primary-action is-quiet" type="button" onClick={() => void check()} disabled={busy || !draft.trim()}>
          {busy && !checks ? t.checking : t.check}
        </button>
        {!last ? (
          <button className="dh-primary-action" type="button" onClick={() => { keep(); setStep(step + 1); }} disabled={busy}>
            {t.next} <ArrowRight size={16} aria-hidden="true" />
          </button>
        ) : (
          <button className="dh-primary-action" type="button" onClick={() => void save(keep())} disabled={busy || (!draft.trim() && !answers.length)}>
            {busy ? t.saving : t.saveStory}
          </button>
        )}
        {!last && answers.length ? (
          <button className="dh-text-action" type="button" onClick={() => void save(keep())} disabled={busy}>
            {t.saveStory}
          </button>
        ) : null}
      </div>
    </div>
  );
}
