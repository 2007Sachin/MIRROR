"use client";

import "@/styles/progress.css";

import { ArrowLeft } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";

import { StateMark } from "@/components/progress/state-mark";
import { AttemptComparison, TryAgain } from "@/components/review/try-again";
import { EmptyState, PageAlert, PageLoading, PageShell, Section, usePageData } from "@/components/workspace/page-shell";
import { ApiError, mirrorApi, type AnswerAttempt, type ProgressAnswerDetail } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { formatDay, reviewHref } from "@/lib/dashboard-view";
import { AREA_KEYS, areaLabel, dimensionHref, roleProgressHref, strengthenSteps } from "@/lib/progress-view";

function load(roleProfileId: string, sessionId: string, turnId: string) {
  return mirrorApi.progressAnswer(roleProfileId, sessionId, turnId).catch((reason: unknown) => {
    if (reason instanceof ApiError && reason.status === 404) return null;
    throw reason;
  });
}

/** One answer: what was said, what Mirror noticed about it, how to strengthen it, and try again. */
export function AnswerView({
  data,
  dimension,
  onSaved,
}: {
  data: ProgressAnswerDetail;
  dimension: string | null;
  onSaved: (attempt: AnswerAttempt) => void;
}) {
  const [retrying, setRetrying] = useState(false);
  const area = dimension && AREA_KEYS.includes(dimension) ? dimension : null;
  const back = area
    ? { href: dimensionHref(data.role_profile_id, area), label: t.answer.back(areaLabel(area)) }
    : { href: roleProgressHref(data.role_profile_id, "answers"), label: t.answer.back(data.target_role) };

  const noticed = area ? data.signals.filter((signal) => signal.dimension === area) : data.signals;
  const focus = noticed.find((signal) => signal.state !== "STRONG");
  // Steps only follow a real gap the review named, never a neutral or strong answer.
  const gap = noticed.find((signal) => signal.state === "NEEDS_PRACTICE");
  const steps = gap ? strengthenSteps(gap.dimension) : [];
  const attempts = data.attempts;
  const latest = attempts.length ? attempts[attempts.length - 1] : null;

  return (
    <>
      <Link className="dh-back-link" href={back.href}>
        <ArrowLeft size={15} aria-hidden="true" /> {back.label}
      </Link>

      <div className="dh-home-sections">
        <header>
          <h1 className="dh-title display pg-question">{data.question}</h1>
          <p className="pg-role-meta">
            {t.timeline.practice(data.practice_number)} · {formatDay(data.completed_at)} ·{" "}
            {t.answers.questionOf(data.question_position, data.question_total)}
          </p>
        </header>

        <section className="pg-answer-card" aria-labelledby="your-answer">
          <p className="dh-section-label" id="your-answer">{t.answer.yourAnswer}</p>
          <blockquote className="dh-answer-text">{data.answer}</blockquote>
        </section>

        <section className="pg-noticed" aria-labelledby="noticed-title">
          <h2 id="noticed-title" className="pg-noticed-title">{t.answer.noticed}</h2>
          {noticed.length ? (
            <ul>
              {noticed.map((signal) => (
                <li key={signal.dimension}>
                  {area ? null : (
                    <p className="pg-noticed-area">
                      <StateMark kind={signal.state} size={14} /> {areaLabel(signal.dimension)} · {t.answers.states[signal.state]}
                    </p>
                  )}
                  <p>{signal.observation}</p>
                  {signal.quote ? (
                    <p className="pg-quote">
                      <span className="sr-only">{t.answer.quoteLabel}: </span>“{signal.quote}”
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p>{t.answer.noticedEmpty}</p>
          )}
        </section>

        {steps.length ? (
          <Section id="strengthen" title={t.answer.strengthen}>
            <ul className="pg-steps">
              {steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ul>
          </Section>
        ) : null}

        {attempts.length ? (
          <Section id="attempts" title={t.answer.retriesTitle} body={t.answer.retriesBody}>
            <ol className="pg-attempts">
              {attempts.map((attempt) => (
                <li key={attempt.id}>
                  <p className="dh-section-label">{t.answer.attempt(attempt.sequence)}</p>
                  <blockquote className="dh-answer-text">{attempt.answer_text}</blockquote>
                </li>
              ))}
            </ol>
            {latest?.comparison ? <AttemptComparison attempt={latest} compact /> : null}
          </Section>
        ) : null}

        <div className="pg-actions">
          <button type="button" className="pg-button is-dark" aria-expanded={retrying} onClick={() => setRetrying(!retrying)}>
            {t.answer.tryAgain}
          </button>
          <Link className="pg-button" href={reviewHref(data.session_id)}>
            {t.answer.viewConversation}
          </Link>
        </div>

        {retrying ? (
          <TryAgain
            sessionId={data.session_id}
            answerTurnId={data.answer_turn_id}
            question={data.question}
            firstAnswer={data.answer}
            area={{ key: null, title: area ? areaLabel(area) : focus ? areaLabel(focus.dimension) : null }}
            onSaved={onSaved}
            onClose={() => setRetrying(false)}
          />
        ) : null}
      </div>
    </>
  );
}

export function AnswerDetail({
  roleProfileId,
  sessionId,
  turnId,
  dimension,
}: {
  roleProfileId: string;
  sessionId: string;
  turnId: string;
  dimension: string | null;
}) {
  const { state, data, error, reload, setData } = usePageData<ProgressAnswerDetail | null>(
    () => load(roleProfileId, sessionId, turnId),
    t.errors.load,
    [roleProfileId, sessionId, turnId],
  );

  return (
    <PageShell>
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}
      {state === "ready" && !data ? (
        <>
          <Link className="dh-back-link" href={roleProgressHref(roleProfileId, "answers")}>
            <ArrowLeft size={15} aria-hidden="true" /> {t.answers.back}
          </Link>
          <EmptyState title={t.answer.unavailable} body={t.role.notFound.body} action={{ href: "/progress", label: t.role.back }} />
        </>
      ) : null}
      {state === "ready" && data ? (
        <AnswerView
          data={data}
          dimension={dimension}
          onSaved={(attempt) => setData({ ...data, attempts: [...data.attempts, attempt] })}
        />
      ) : null}
    </PageShell>
  );
}
