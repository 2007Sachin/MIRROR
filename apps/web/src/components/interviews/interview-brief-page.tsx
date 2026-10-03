"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";

import { InterviewForm } from "@/components/interviews/interview-form";
import { RoleTabs } from "@/components/roles/role-tabs";
import { PageAlert, PageHeader, PageLoading, PageShell, Section, usePageData } from "@/components/workspace/page-shell";
import {
  mirrorApi,
  type InterviewBrief,
  type InterviewDebriefView,
  type InterviewEvent,
  type InterviewFeeling,
  type InterviewOutcome,
} from "@/lib/api";
import { interviews as t } from "@/lib/copy";
import { reviewHref } from "@/lib/dashboard-view";
import { MAX_NOTES_LENGTH, formatWhen, normaliseQuestions, roundLabel, showDebrief } from "@/lib/interview-view";
import { coverageClass, coverageLabel, pressureTestHref } from "@/lib/map-view";

const FEELINGS: InterviewFeeling[] = ["WENT_WELL", "MIXED", "WENT_BADLY"];
const OUTCOMES: InterviewOutcome[] = ["WAITING", "NEXT_ROUND", "OFFER", "NOT_SELECTED", "WITHDREW"];

export function InterviewBriefPage({ roleProfileId, eventId }: { roleProfileId: string; eventId: string }) {
  const { state, data, error, reload, setData } = usePageData(
    async () => {
      const [brief, debrief] = await Promise.all([mirrorApi.interviewBrief(eventId), mirrorApi.interviewDebrief(eventId)]);
      return { brief, debrief };
    },
    t.errors.loadBrief,
    [eventId],
  );
  const brief = data?.brief;

  return (
    <PageShell>
      <PageHeader
        eyebrow={brief ? brief.role_title : t.eyebrow}
        title={brief ? t.brief.title(roundLabel(brief.event)) : t.title}
        intro={brief ? `${formatWhen(brief.event.scheduled_for)}${brief.event.company_label ? ` · ${brief.event.company_label}` : ""}` : undefined}
        back={{ href: `/roles/${roleProfileId}/interviews`, label: t.back }}
      />
      <RoleTabs roleProfileId={roleProfileId} current="interviews" />

      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {state === "ready" && data && brief ? (
        <>
          <p className="dh-page-intro">{t.brief.intro}</p>
          <EditDetails event={brief.event} onSaved={(event) => setData({ ...data, brief: { ...brief, event } })} />
          <BriefView brief={brief} roleProfileId={roleProfileId} />
          {showDebrief(brief.event) || data.debrief ? (
            <DebriefForm
              eventId={eventId}
              early={brief.event.timing !== "PAST"}
              view={data.debrief}
              onSaved={(debrief) => setData({ brief: { ...brief, event: { ...brief.event, has_debrief: true } }, debrief })}
            />
          ) : null}
        </>
      ) : null}
    </PageShell>
  );
}

/** A secondary action on the brief: the saved event (and its timing) always comes back from the server. */
function EditDetails({ event, onSaved }: { event: InterviewEvent; onSaved: (event: InterviewEvent) => void }) {
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState("");
  const openRef = useRef<HTMLButtonElement>(null);

  function close(message: string) {
    setEditing(false);
    setStatus(message);
    // The toggle is back in the DOM on the next frame.
    requestAnimationFrame(() => openRef.current?.focus());
  }

  return (
    <div>
      {editing ? (
        <Section id="interview-edit" title={t.edit.title}>
          <InterviewForm
            event={event}
            submitLabel={t.edit.submit}
            savingLabel={t.edit.saving}
            errorLabel={t.errors.edit}
            onSubmit={async (value) => {
              onSaved(await mirrorApi.updateInterview(event.id, value));
              close(t.edit.saved);
            }}
            onCancel={() => close("")}
          />
        </Section>
      ) : (
        <button ref={openRef} type="button" className="dh-text-action" onClick={() => { setStatus(""); setEditing(true); }}>
          {t.edit.open}
        </button>
      )}
      <p className="dh-fine-print" role="status" aria-live="polite" style={status ? undefined : { margin: 0 }}>
        {status}
      </p>
    </div>
  );
}

function BriefView({ brief, roleProfileId }: { brief: InterviewBrief; roleProfileId: string }) {
  return (
    <>
      {brief.state !== "READY" ? (
        <section className="dh-empty">
          <p>{t.brief.states[brief.state]}</p>
        </section>
      ) : null}

      {brief.themes.length ? (
        <Section id="brief-themes" title={t.brief.themesTitle} body={t.brief.themesNote}>
          <ul className="dh-row-list">
            {brief.themes.map((theme) => (
              <li key={theme.key}>
                <span className="dh-row-main">
                  <strong>{theme.label}</strong>
                  <span>{theme.prompt}</span>
                  {theme.support ? (
                    <small>
                      {t.brief.support}: {theme.support}
                    </small>
                  ) : null}
                </span>
                <span className="dh-row-actions">
                  <span className={`dh-row-state ${coverageClass(theme.coverage)}`}>{coverageLabel(theme.coverage)}</span>
                  {theme.story_id ? (
                    <Link className="dh-text-action" href={`/stories/${theme.story_id}`}>
                      {t.brief.openStory}
                    </Link>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {brief.recheck.length ? (
        <Section
          id="brief-recheck"
          title={t.brief.recheckTitle}
          body={t.brief.recheckNote}
          action={
            <Link className="dh-text-action" href={pressureTestHref(roleProfileId)}>
              {t.brief.recheckOpen} <ArrowRight size={15} aria-hidden="true" />
            </Link>
          }
        >
          <ul className="dh-step-list is-plain">
            {brief.recheck.map((claim) => (
              <li key={claim.claim_id}>
                <blockquote className="dh-pressure-statement">{claim.statement}</blockquote>
                <p className="dh-fine-print">
                  {t.brief.recheckQuestion}: {claim.question}
                </p>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {brief.focus ? (
        <Section
          id="brief-focus"
          title={t.brief.focusTitle}
          action={
            brief.focus.session_id ? (
              <Link className="dh-text-action" href={reviewHref(brief.focus.session_id)}>
                {t.brief.openReview} <ArrowRight size={15} aria-hidden="true" />
              </Link>
            ) : undefined
          }
        >
          <p className="dh-prose">
            <strong>{brief.focus.title}</strong>
          </p>
          <p className="dh-prose">{brief.focus.body}</p>
        </Section>
      ) : null}

      {brief.questions_to_ask.length ? (
        <Section id="brief-ask" title={t.brief.askTitle}>
          <ul className="dh-step-list is-plain">
            {brief.questions_to_ask.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section id="brief-limits" title={t.brief.limitsTitle}>
        <ul className="dh-plain-list">
          {brief.limitations.map((line) => (
            <li key={line} className="dh-fine-print">
              {line}
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

function DebriefForm({
  eventId,
  early,
  view,
  onSaved,
}: {
  eventId: string;
  early: boolean;
  view: InterviewDebriefView | null;
  onSaved: (view: InterviewDebriefView) => void;
}) {
  const [questions, setQuestions] = useState(view?.debrief.questions_asked.join("\n") ?? "");
  const [feeling, setFeeling] = useState<InterviewFeeling | "">(view?.debrief.feeling ?? "");
  const [outcome, setOutcome] = useState<InterviewOutcome>(view?.debrief.outcome ?? "WAITING");
  const [notes, setNotes] = useState(view?.debrief.notes ?? "");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus("");
    setMessage("");
    try {
      const saved = await mirrorApi.saveInterviewDebrief(eventId, {
        questions_asked: normaliseQuestions(questions),
        feeling: feeling || null,
        outcome,
        notes: notes.trim() || null,
      });
      setQuestions(saved.debrief.questions_asked.join("\n"));
      onSaved(saved);
      setStatus(t.debrief.saved);
    } catch {
      setMessage(t.errors.save);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Section id="debrief" title={t.debrief.title} body={early ? `${t.debrief.intro} ${t.debrief.earlyNote}` : t.debrief.intro}>
        <form className="dh-form is-wide" onSubmit={(event) => void submit(event)}>
          <label>
            <span>{t.debrief.questions}</span>
            <textarea className="field" rows={6} value={questions} onChange={(event) => setQuestions(event.target.value)} disabled={busy} />
            <small>{t.debrief.questionsHint}</small>
          </label>
          <label>
            <span>{t.debrief.feeling}</span>
            <select className="field" value={feeling} onChange={(event) => setFeeling(event.target.value as InterviewFeeling | "")} disabled={busy}>
              <option value="">{t.debrief.feelingNone}</option>
              {FEELINGS.map((value) => (
                <option key={value} value={value}>
                  {t.debrief.feelings[value]}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t.debrief.outcome}</span>
            <select className="field" value={outcome} onChange={(event) => setOutcome(event.target.value as InterviewOutcome)} disabled={busy}>
              {OUTCOMES.map((value) => (
                <option key={value} value={value}>
                  {t.debrief.outcomes[value]}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>{t.debrief.notes}</span>
            <textarea className="field" rows={4} maxLength={MAX_NOTES_LENGTH} value={notes} onChange={(event) => setNotes(event.target.value)} disabled={busy} />
          </label>
          {message ? <p className="dh-inline-error" role="alert">{message}</p> : null}
          <p className="dh-fine-print" role="status" aria-live="polite">
            {busy ? t.debrief.saving : status}
          </p>
          <div className="dh-action-row">
            <button className="dh-primary-action" type="submit" disabled={busy}>
              {busy ? t.debrief.saving : t.debrief.save}
            </button>
          </div>
        </form>
      </Section>

      {view?.follow_ups.length ? (
        <Section id="debrief-follow-ups" title={t.debrief.followUpsTitle} body={t.debrief.followUpsNote}>
          <ul className="dh-row-list">
            {view.follow_ups.map((item) => (
              <li key={item.question}>
                <span className="dh-row-main">
                  <strong>{item.question}</strong>
                  <small>
                    {item.theme_label ?? t.debrief.noTheme}
                    {item.coverage ? ` · ${coverageLabel(item.coverage)}` : ""}
                  </small>
                </span>
                {item.action !== "NONE" && item.action_href?.startsWith("/") ? (
                  <span className="dh-row-actions">
                    <Link className="dh-text-action" href={item.action_href as string}>
                      {t.debrief.actions[item.action]} <ArrowRight size={15} aria-hidden="true" />
                    </Link>
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </>
  );
}
