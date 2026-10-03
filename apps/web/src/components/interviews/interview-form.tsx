"use client";

import { useState, type FormEvent } from "react";

import { ApiError, type InterviewEvent, type InterviewEventCreate, type InterviewRoundKind } from "@/lib/api";
import { interviews as t } from "@/lib/copy";
import { MAX_COMPANY_LENGTH, isoToLocalInput, localInputToIso } from "@/lib/interview-view";

const ROUNDS: InterviewRoundKind[] = ["SCREENING", "TECHNICAL", "BEHAVIOURAL", "HR", "OTHER"];

/** The add and edit forms share these fields. An empty company label is sent as null, which clears it. */
export function InterviewForm({
  event,
  submitLabel,
  savingLabel,
  errorLabel,
  onSubmit,
  onCancel,
}: {
  event?: InterviewEvent;
  submitLabel: string;
  savingLabel: string;
  errorLabel: string;
  onSubmit: (value: InterviewEventCreate) => Promise<void>;
  onCancel?: () => void;
}) {
  const [when, setWhen] = useState(event ? isoToLocalInput(event.scheduled_for) : "");
  const [round, setRound] = useState<InterviewRoundKind>(event?.round_kind ?? "OTHER");
  const [company, setCompany] = useState(event?.company_label ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(formEvent: FormEvent) {
    formEvent.preventDefault();
    if (busy) return;
    const scheduled = localInputToIso(when);
    if (!scheduled) {
      setMessage(errorLabel);
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await onSubmit({ scheduled_for: scheduled, round_kind: round, company_label: company.trim() || null });
    } catch (reason) {
      setMessage(reason instanceof ApiError && reason.status !== 422 ? reason.message : errorLabel);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="dh-form is-wide" onSubmit={(formEvent) => void submit(formEvent)}>
      <label>
        <span>{t.add.when}</span>
        <input
          className="field"
          type="datetime-local"
          value={when}
          onChange={(change) => setWhen(change.target.value)}
          required
          disabled={busy}
          autoFocus={Boolean(event)}
        />
      </label>
      <label>
        <span>{t.add.round}</span>
        <select className="field" value={round} onChange={(change) => setRound(change.target.value as InterviewRoundKind)} disabled={busy}>
          {ROUNDS.map((kind) => (
            <option key={kind} value={kind}>
              {t.rounds[kind]}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{t.add.company}</span>
        <input
          className="field"
          type="text"
          value={company}
          maxLength={MAX_COMPANY_LENGTH}
          onChange={(change) => setCompany(change.target.value)}
          disabled={busy}
        />
        <small>{t.add.companyHint}</small>
      </label>
      {message ? <p className="dh-inline-error" role="alert">{message}</p> : null}
      <p className="dh-fine-print" role="status" aria-live="polite" style={busy ? undefined : { margin: 0 }}>
        {busy ? savingLabel : ""}
      </p>
      <div className="dh-action-row">
        {/* Editing is secondary on the brief, so its save stays quiet: one filled primary per screen. */}
        <button className={event ? "dh-text-action" : "dh-primary-action"} type="submit" disabled={busy || !when}>
          {busy ? savingLabel : submitLabel}
        </button>
        {onCancel ? (
          <button type="button" className="dh-text-action is-quiet" onClick={onCancel} disabled={busy}>
            {t.edit.cancel}
          </button>
        ) : null}
      </div>
    </form>
  );
}
