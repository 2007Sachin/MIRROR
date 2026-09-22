"use client";

import { ArrowRight, Check, Info } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Loader } from "@/components/loader";
import { AttemptComparison, TryAgain } from "@/components/review/try-again";
import { PageHeader, PageShell, Section } from "@/components/workspace/page-shell";
import {
  ApiError,
  mirrorApi,
  type AnswerAttempt,
  type PublicInterviewTurn,
  type ReportEvidence,
  type ReportResponse,
  type SessionReview,
} from "@/lib/api";
import { loading, report as reportCopy, review as t, tryAgain as tryCopy } from "@/lib/copy";
import { attemptsByAnswer, latestAttempt } from "@/lib/attempt-view";
import { formatDay } from "@/lib/dashboard-view";
import { focusFor, modeCopy, startPracticeHref } from "@/lib/practice-view";
import { stateClass } from "@/lib/progress-view";
import { answerBlocks, practiceNext, retryTargets, reviewStrengths } from "@/lib/review-view";

type ViewState = "loading" | "processing" | "error" | "ready";

const POLL_MS = 5000;
const MAX_POLLS = 24;

export function ReviewPage({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const mounted = useRef(true);
  const [state, setState] = useState<ViewState>("loading");
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [review, setReview] = useState<SessionReview | null>(null);
  const [turns, setTurns] = useState<PublicInterviewTurn[] | null>(null);
  const [turnsFailed, setTurnsFailed] = useState(false);
  const [attempts, setAttempts] = useState<AnswerAttempt[]>([]);
  const [openRetry, setOpenRetry] = useState<string | null>(null);
  const [openComparison, setOpenComparison] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [retryable, setRetryable] = useState(false);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    mounted.current = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;

    const fail = (reason: unknown) => {
      if (!mounted.current) return;
      if (reason instanceof ApiError && reason.status === 401) {
        router.replace("/login?reason=session_expired");
        return;
      }
      setRetryable(false);
      setState("error");
      setMessage(reason instanceof ApiError && reason.status === 404 ? reportCopy.states.notFound : reportCopy.states.loadFailed);
    };

    const load = async () => {
      try {
        const [nextReport, nextReview] = await Promise.all([
          mirrorApi.report(sessionId),
          mirrorApi.sessionReview(sessionId),
        ]);
        if (!mounted.current) return;
        setReport(nextReport);
        setReview(nextReview);
        setState("ready");
        // The conversation is a bonus: the review stands on its own without it.
        void mirrorApi
          .interviewTurns(sessionId)
          .then((next) => mounted.current && setTurns(next))
          .catch(() => mounted.current && setTurnsFailed(true));
        // Earlier attempts are shown next to their answer; without them the page is unchanged.
        void mirrorApi
          .attempts(sessionId)
          .then((next) => mounted.current && setAttempts(next))
          .catch(() => undefined);
      } catch (reason) {
        if (!(reason instanceof ApiError) || reason.status !== 409) {
          fail(reason);
          return;
        }
        try {
          const pipeline = await mirrorApi.assessmentStatus(sessionId);
          if (!mounted.current) return;
          if (pipeline.status === "FAILED") {
            setRetryable(true);
            setState("error");
            setMessage(reportCopy.states.savedRetry);
            return;
          }
          setState("processing");
          attempts += 1;
          if (attempts < MAX_POLLS) timer = setTimeout(load, POLL_MS);
          else {
            setState("error");
            setMessage(reportCopy.states.longWait);
          }
        } catch (statusReason) {
          fail(statusReason);
        }
      }
    };

    void load();
    return () => {
      mounted.current = false;
      if (timer) clearTimeout(timer);
    };
  }, [router, sessionId]);

  async function retry() {
    setRetrying(true);
    try {
      await mirrorApi.retryAssessment(sessionId);
      router.replace("/practice");
    } catch (reason) {
      setMessage(reason instanceof ApiError ? reason.message : reportCopy.states.retryFailed);
    } finally {
      setRetrying(false);
    }
  }

  const strengths = useMemo(() => reviewStrengths(review), [review]);
  const improvements = useMemo(() => (review?.improvements ?? []).slice(0, 3), [review]);
  const blocks = useMemo(() => answerBlocks(turns ?? [], report), [turns, report]);
  const targets = useMemo(() => retryTargets(improvements.length, blocks), [improvements, blocks]);
  const byAnswer = useMemo(() => attemptsByAnswer(attempts), [attempts]);
  const next = practiceNext(review);
  const role = report?.session.target_role ?? review?.target_role ?? "";

  function saved(attempt: AnswerAttempt) {
    setAttempts((current) => [...current, attempt]);
  }

  if (state === "loading") {
    return (
      <PageShell>
        <Loader page label={loading.report.label} note={loading.report.note} />
      </PageShell>
    );
  }

  if (state === "processing") {
    return (
      <PageShell>
        <PageHeader eyebrow={t.eyebrow} title={reportCopy.states.processingTitle} back={{ href: "/practice", label: t.back }} />
        <Loader label={loading.reflecting.label} note={loading.reflecting.note} />
        <p className="dh-prose">{reportCopy.states.processingBody}</p>
      </PageShell>
    );
  }

  if (state === "error") {
    return (
      <PageShell>
        <PageHeader
          eyebrow={t.eyebrow}
          title={retryable ? reportCopy.states.failedTitle : reportCopy.states.unavailableTitle}
          back={{ href: "/practice", label: t.back }}
        />
        <p className="dh-prose" role="alert">{message}</p>
        <div className="dh-action-row">
          {retryable ? (
            <button className="dh-primary-action" type="button" onClick={() => void retry()} disabled={retrying}>
              {retrying ? reportCopy.states.retrying : reportCopy.states.retry}
            </button>
          ) : null}
          <Link className="dh-text-action" href="/practice">
            {t.back} <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </div>
      </PageShell>
    );
  }

  if (!report || !review) return null;

  return (
    <PageShell>
      <PageHeader eyebrow={t.eyebrow} title={role} back={{ href: "/practice", label: t.back }} />
      <p className="dh-step-count">
        <time dateTime={report.session.completed_at}>{formatDay(report.session.completed_at)}</time>
      </p>

      <div className="dh-home-sections">
        <section className="dh-next-action" aria-labelledby="review-overview">
          <p className="dh-section-label">{t.overview}</p>
          <h2 id="review-overview" className="display">{review.next_step.title}</h2>
          <p className="dh-next-copy">{report.verdict.summary}</p>
          {review.counts ? (
            <p className="dh-action-meta">
              {review.counts.clear} {reportCopy.cameThrough.groups.held.toLowerCase()} ·{" "}
              {t.toImprove(review.counts.could_be_stronger + review.counts.worth_revisiting)}
            </p>
          ) : null}
          {review.shorter_conversation ? <p className="dh-action-meta">{reportCopy.shorterNote}</p> : null}
          {/* Kept as a range with its own note, never a single number or a gauge. */}
          <dl className="dh-readiness">
            <div>
              <dt>{reportCopy.readiness.role}</dt>
              <dd>{range(report.role_readiness)}</dd>
            </div>
            <div>
              <dt>{reportCopy.readiness.interview}</dt>
              <dd>{range(report.interview_readiness)}</dd>
            </div>
          </dl>
          <p className="dh-fine-print">{t.readinessNote}</p>
        </section>

        <Section id="review-clear" label={t.clearTitle} title={t.clearTitle}>
          {strengths.length ? (
            <ul className="dh-plain-list">
              {strengths.map((strength) => (
                <li key={strength.key}>
                  <strong>{strength.label}</strong>
                  <small>{strength.note}</small>
                  <span className={`dh-row-state ${stateClass("Coming through clearly")}`}>
                    <Check size={14} aria-hidden="true" /> {reportCopy.cameThrough.groups.held}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dh-review-empty">{t.clearEmpty}</p>
          )}
        </Section>

        <Section id="review-improve" label={t.improveTitle} title={t.improveTitle}>
          {improvements.length ? (
            <ul className="dh-plain-list">
              {improvements.map((item, index) => {
                const target = targets[index];
                const key = `item-${index}`;
                return (
                  <li key={key}>
                    <strong>{item.title}</strong>
                    <small>{item.note}</small>
                    {item.from_label ? <small className="dh-quiet">{`${t.improveFrom}: ${item.from_label}`}</small> : null}
                    <span className="dh-row-actions is-start">
                      {target ? (
                        <button className="dh-text-action" type="button" onClick={() => setOpenRetry(openRetry === key ? null : key)} aria-expanded={openRetry === key}>
                          {tryCopy.action} <ArrowRight size={15} aria-hidden="true" />
                        </button>
                      ) : null}
                      <Link className={target ? "dh-text-action is-quiet" : "dh-text-action"} href={startPracticeHref(role, next ?? { mode: "QUICK_DRILL" })}>
                        {t.practiceThis} <ArrowRight size={15} aria-hidden="true" />
                      </Link>
                    </span>
                    {target && openRetry === key ? (
                      <TryAgain
                        sessionId={sessionId}
                        answerTurnId={target.answerTurnId}
                        question={target.question}
                        firstAnswer={target.answer}
                        area={{ key: review.practice_focus ?? null, title: item.title }}
                        onSaved={saved}
                        onClose={() => setOpenRetry(null)}
                      />
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="dh-review-empty">{t.improveEmpty}</p>
          )}
        </Section>

        <Section id="review-answers" label={t.answersTitle} title={t.answersTitle} body={t.answersBody}>
          {turnsFailed ? <p className="dh-review-empty">{t.answersUnavailable}</p> : null}
          {!turnsFailed && turns === null ? <div className="dh-row-skeleton" aria-hidden="true" /> : null}
          {turns !== null && !blocks.length ? <p className="dh-review-empty">{t.answersEmpty}</p> : null}
          {blocks.length ? (
            <ol className="dh-answer-list">
              {blocks.map((block) => {
                const previous = block.answerTurnId ? byAnswer.get(block.answerTurnId) : undefined;
                const latest = latestAttempt(previous);
                const retryKey = block.answerTurnId ? `answer-${block.answerTurnId}` : null;
                return (
                  <li key={block.id}>
                    <p className="dh-answer-question">{block.question}</p>
                    {block.answer ? (
                      <blockquote className="dh-answer-text">{block.answer}</blockquote>
                    ) : (
                      <p className="dh-review-empty">{t.noAnswer}</p>
                    )}
                    {block.cameThrough.length || block.couldBeClearer.length ? (
                      <div className="dh-answer-notes">
                        <QuoteNotes title={t.cameThrough} quotes={block.cameThrough} tone="is-ready" />
                        <QuoteNotes title={t.couldBeClearer} quotes={block.couldBeClearer} tone="is-active" />
                      </div>
                    ) : null}
                    {block.answerTurnId && block.answer && retryKey ? (
                      <span className="dh-row-actions is-start">
                        <button className="dh-text-action" type="button" onClick={() => setOpenRetry(openRetry === retryKey ? null : retryKey)} aria-expanded={openRetry === retryKey}>
                          {tryCopy.action} <ArrowRight size={15} aria-hidden="true" />
                        </button>
                        {latest ? (
                          <button className="dh-text-action is-quiet" type="button" onClick={() => setOpenComparison(openComparison === retryKey ? null : retryKey)} aria-expanded={openComparison === retryKey}>
                            {tryCopy.latestAvailable(previous?.length ?? 0)} · {openComparison === retryKey ? tryCopy.hideComparison : tryCopy.showComparison}
                          </button>
                        ) : null}
                      </span>
                    ) : null}
                    {latest && openComparison === retryKey ? (
                      <div className="dh-drill">
                        <p className="dh-subhead">{tryCopy.yourLatest}</p>
                        <blockquote className="dh-answer-text">{latest.answer_text}</blockquote>
                        <AttemptComparison attempt={latest} />
                      </div>
                    ) : null}
                    {block.answerTurnId && block.answer && openRetry === retryKey ? (
                      <TryAgain
                        sessionId={sessionId}
                        answerTurnId={block.answerTurnId}
                        question={block.question}
                        firstAnswer={block.answer}
                        onSaved={saved}
                        onClose={() => setOpenRetry(null)}
                      />
                    ) : null}
                  </li>
                );
              })}
            </ol>
          ) : null}
        </Section>

        <section className="dh-next-action" aria-labelledby="review-next">
          <p className="dh-section-label">{t.nextTitle}</p>
          {next ? (
            <>
              <h2 id="review-next" className="display">{focusFor(next.focus)?.title ?? review.next_step.title}</h2>
              <p className="dh-next-copy">{review.next_step.body}</p>
              <div className="dh-action-row">
                <Link className="dh-primary-action" href={startPracticeHref(role, next)}>
                  {t.nextStart} <ArrowRight size={17} aria-hidden="true" />
                </Link>
                <span className="dh-action-meta">{modeCopy(next.mode).title} · {modeCopy(next.mode).length}</span>
              </div>
            </>
          ) : (
            <>
              <h2 id="review-next" className="display">{t.nextChoose}</h2>
              <div className="dh-action-row">
                <Link className="dh-primary-action" href={startPracticeHref(role, { mode: "QUICK_DRILL" })}>
                  {t.nextChooseAction} <ArrowRight size={17} aria-hidden="true" />
                </Link>
              </div>
            </>
          )}
        </section>

        <aside className="dh-trust" aria-labelledby="review-trust">
          <Info size={20} aria-hidden="true" />
          <div>
            <h2 id="review-trust">{reportCopy.trust.title}</h2>
            <ul>
              {reportCopy.trust.points.map((point) => (
                <li key={point}>{point}</li>
              ))}
              <li>
                {report.trust_and_limitations.outcome_validation_status === "NOT_VALIDATED"
                  ? reportCopy.trust.outcomeNotValidated
                  : `${reportCopy.trust.outcomeOther} ${report.trust_and_limitations.outcome_validation_status.replaceAll("_", " ").toLowerCase()}`}
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </PageShell>
  );
}

function range(value: ReportResponse["role_readiness"]) {
  if (value.low == null || value.high == null) return reportCopy.readiness.none;
  return `${value.low}–${value.high} · ${value.label}`;
}

function QuoteNotes({ title, quotes, tone }: { title: string; quotes: ReportEvidence[]; tone: string }) {
  if (!quotes.length) return null;
  return (
    <div className={`dh-answer-note ${tone}`}>
      <h3>{title}</h3>
      <ul>
        {quotes.slice(0, 2).map((quote, index) => (
          <li key={`${quote.quote}-${index}`}>{quote.quote}</li>
        ))}
      </ul>
    </div>
  );
}
