"use client";

import { ArrowRight, Check } from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import { ApiError, mirrorApi, type AnswerAttempt } from "@/lib/api";
import { tryAgain as t } from "@/lib/copy";
import { beforeAfter, gainedLines, missingLines } from "@/lib/attempt-view";

/**
 * Answer the same question again, see what changed, and try once more or move on.
 * The first answer is shown, never edited.
 */
export function TryAgain({
  sessionId,
  answerTurnId,
  question,
  firstAnswer,
  area,
  onSaved,
  onClose,
}: {
  sessionId: string;
  answerTurnId: string;
  question: string;
  firstAnswer: string;
  area?: { key: string | null; title: string | null };
  onSaved: (attempt: AnswerAttempt) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnswerAttempt | null>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const resultPanel = useRef<HTMLDivElement>(null);
  const idempotencyKey = useRef(crypto.randomUUID());

  useEffect(() => {
    if (result) resultPanel.current?.focus();
    else field.current?.focus();
  }, [result]);

  async function submit() {
    if (!draft.trim()) return;
    setBusy(true);
    setError("");
    try {
      const attempt = await mirrorApi.tryAgain(sessionId, answerTurnId, {
        answer: draft.trim(),
        area_key: area?.key ?? null,
        area_title: area?.title ?? null,
        idempotency_key: idempotencyKey.current,
      });
      setResult(attempt);
      onSaved(attempt);
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 409 ? reason.message : t.errors.save);
    } finally {
      setBusy(false);
    }
  }

  function again() {
    setResult(null);
    setDraft("");
    idempotencyKey.current = crypto.randomUUID();
  }

  return (
    <div className="dh-drill" aria-live="polite">
      {area?.title ? <p className="dh-section-label">{area.title}</p> : null}
      <p className="dh-subhead">{t.question}</p>
      <p className="dh-answer-question">{question}</p>
      <details className="dh-first-answer">
        <summary>{t.yourFirst}</summary>
        <blockquote className="dh-answer-text">{firstAnswer}</blockquote>
      </details>

      {result?.comparison ? (
        <div ref={resultPanel} tabIndex={-1}>
          <AttemptComparison attempt={result} />
        </div>
      ) : (
        <label className="dh-form is-wide">
          <span>{t.answerLabel}</span>
          <textarea ref={field} className="field" rows={6} value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={6000} disabled={busy} />
          <small>{t.answerHint}</small>
        </label>
      )}
      {error ? <p className="dh-inline-error" role="alert">{error}</p> : null}

      <div className="dh-action-row">
        {result ? (
          <>
            <button className="dh-primary-action" type="button" onClick={again}>{t.again}</button>
            <button className="dh-primary-action is-quiet" type="button" onClick={onClose}>{t.done}</button>
          </>
        ) : (
          <>
            <button className="dh-primary-action" type="button" onClick={() => void submit()} disabled={busy || !draft.trim()}>
              {busy ? t.comparing : t.submit} {busy ? null : <ArrowRight size={16} aria-hidden="true" />}
            </button>
            <button className="dh-text-action is-quiet" type="button" onClick={onClose} disabled={busy}>{t.done}</button>
          </>
        )}
      </div>
    </div>
  );
}

/** What changed, what is still worth adding, and the side-by-side of both attempts. */
export function AttemptComparison({ attempt, compact = false }: { attempt: AnswerAttempt; compact?: boolean }) {
  const comparison = attempt.comparison;
  if (!comparison) return null;
  const gained = gainedLines(comparison);
  const missing = missingLines(comparison);
  const columns = beforeAfter(comparison);

  return (
    <div className="dh-attempt-result">
      <p className="dh-prose">{comparison.summary}</p>
      <div className="dh-review-columns">
        <div>
          <h3>{t.whatChanged}</h3>
          {gained.length ? (
            <ul className="dh-review-list">
              {gained.map((line) => (
                <li key={line}><Check size={17} aria-hidden="true" /><span>{line}</span></li>
              ))}
            </ul>
          ) : (
            <p className="dh-review-empty">{t.nothingChanged}</p>
          )}
        </div>
        <div>
          <h3>{t.stillWorth}</h3>
          {missing.length ? (
            <ul className="dh-review-list">
              {missing.map((line) => (
                <li key={line}><ArrowRight size={17} aria-hidden="true" /><span>{line}</span></li>
              ))}
            </ul>
          ) : (
            <p className="dh-review-empty">{t.nothingMissing}</p>
          )}
        </div>
      </div>

      {!compact ? (
        <div className="dh-before-after">
          <AttemptColumn title={t.firstAttempt} column={columns.first} />
          <AttemptColumn title={t.latestAttempt} column={columns.latest} />
        </div>
      ) : null}

      <p className="dh-prose"><strong>{t.suggestion}:</strong> {comparison.next_suggestion}</p>
      {comparison.source === "CHECKS" ? <p className="dh-fine-print">{t.checksNote}</p> : null}
    </div>
  );
}

function AttemptColumn({ title, column }: { title: string; column: { cameThrough: string[]; unclear: string[] } }) {
  return (
    <section className="dh-attempt-column" aria-label={title}>
      <h4>{title}</h4>
      <p className="dh-fine-print">{t.cameThrough}</p>
      <ul className="dh-check-list">
        {column.cameThrough.map((item) => (
          <li key={item} className="is-present"><Check size={15} aria-hidden="true" /><span>{item}</span></li>
        ))}
      </ul>
      {column.unclear.length ? (
        <>
          <p className="dh-fine-print">{t.stillUnclear}</p>
          <ul className="dh-check-list">
            {column.unclear.map((item) => (
              <li key={item} className="is-absent"><ArrowRight size={15} aria-hidden="true" /><span>{item}</span></li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
