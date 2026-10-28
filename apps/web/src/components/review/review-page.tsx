"use client";

import "@/styles/practice-reflect.css";

import { ArrowRight, Info } from "@phosphor-icons/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { Loader } from "@/components/loader";
import { AttemptComparison, TryAgain } from "@/components/review/try-again";
import { ReviewStorySuggestions } from "@/components/stories/story-suggestions";
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
import { reflect, reflection as r } from "@/lib/copy-practice";
import { attemptsByAnswer, latestAttempt } from "@/lib/attempt-view";
import { formatDay } from "@/lib/dashboard-view";
import { focusFor, modeCopy, startPracticeHref } from "@/lib/practice-view";
import { claimGroups, timecode, type ClaimGroup } from "@/lib/review-groups";
import { answerBlocks, answerTargets, practiceNext, reviewStrengths, strengthenItem, type AnswerTarget } from "@/lib/review-view";

type ViewState = "loading" | "processing" | "error" | "ready";

const WAIT_LIMIT_MS = 5 * 60 * 1000;

/** Short at first, then slower, for about five minutes in total. */
function pollDelay(elapsedMs: number) {
  if (elapsedMs < 30_000) return 5_000;
  if (elapsedMs < 120_000) return 10_000;
  return 20_000;
}

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
  const [elapsedMinutes, setElapsedMinutes] = useState(0);
  const [waitedOut, setWaitedOut] = useState(false);

  useEffect(() => {
    mounted.current = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const started = Date.now();
    const tick = window.setInterval(() => {
      if (mounted.current) setElapsedMinutes(Math.floor((Date.now() - started) / 60_000));
    }, 15_000);

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
          const elapsed = Date.now() - started;
          setElapsedMinutes(Math.floor(elapsed / 60_000));
          setState("processing");
          if (elapsed >= WAIT_LIMIT_MS) {
            setWaitedOut(true);
            return;
          }
          timer = setTimeout(load, pollDelay(elapsed));
        } catch (statusReason) {
          fail(statusReason);
        }
      }
    };

    void load();
    return () => {
      mounted.current = false;
      window.clearInterval(tick);
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
  const strengthen = useMemo(() => strengthenItem(review), [review]);
  const workItems = useMemo(() => (review?.improvements ?? []).slice(0, 3), [review]);
  const blocks = useMemo(() => answerBlocks(turns ?? [], report), [turns, report]);
  const landedFrom = useMemo(() => answerTargets(strengths.length, blocks, "cameThrough"), [strengths, blocks]);
  const strengthenFrom = useMemo(() => answerTargets(strengthen ? 1 : 0, blocks, "couldBeClearer")[0] ?? null, [strengthen, blocks]);
  const byAnswer = useMemo(() => attemptsByAnswer(attempts), [attempts]);
  const groups = useMemo(() => claimGroups(report), [report]);
  const next = practiceNext(review);
  const role = report?.session.target_role ?? review?.target_role ?? "";

  function saved(attempt: AnswerAttempt) {
    setAttempts((current) => [...current, attempt]);
  }

  if (state === "loading") {
    return (
      <PageShell readingRoom>
        <Loader page label={loading.report.label} note={loading.report.note} />
      </PageShell>
    );
  }

  if (state === "processing") {
    return (
      <PageShell readingRoom>
        <PageHeader eyebrow={t.eyebrow} title={reportCopy.states.processingTitle} back={{ href: "/practice", label: t.back }} />
        {waitedOut ? null : <Loader label={loading.reflecting.label} note={loading.reflecting.note} />}
        <p className="dh-prose">{waitedOut ? reportCopy.states.stillPreparing : reportCopy.states.processingWait(elapsedMinutes)}</p>
        <div className="dh-action-row">
          {waitedOut ? (
            <button className="dh-primary-action" type="button" onClick={() => void retry()} disabled={retrying}>
              {retrying ? reportCopy.states.retrying : reportCopy.states.retry}
            </button>
          ) : null}
          <Link className="dh-text-action" href="/dashboard">
            {reportCopy.states.comeBack} <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </div>
      </PageShell>
    );
  }

  if (state === "error") {
    return (
      <PageShell readingRoom>
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
          <Link className="dh-text-action" href="/dashboard">
            {reportCopy.states.comeBack} <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </div>
      </PageShell>
    );
  }

  if (!report || !review) return null;

  // "Practise the same answer" opens the retry on the answer the one thing to strengthen came from.
  const sameAnswer = strengthenFrom ? "#review-strengthen-title" : "#review-answers-title";

  return (
    <PageShell readingRoom>
      <PageHeader eyebrow={t.eyebrow} title={role} back={{ href: "/reflect", label: reflect.eyebrow }} />
      <p className="dh-step-count">
        <time dateTime={report.session.completed_at}>{formatDay(report.session.completed_at)}</time>
      </p>
      {/* The summary first: the backend's own label and sentence, beside the one next practice. */}
      <section className="pr-summary" aria-labelledby="review-summary-title">
        <div className="pr-summary-main">
          <p className="dh-section-label">{reportCopy.summary.eyebrow}</p>
          <h2 id="review-summary-title">{report.verdict.label}</h2>
          <p>{report.verdict.summary}</p>
          {review.counts ? (
            <p className="pr-counts">{reportCopy.cameThrough.counts(review.counts.clear, review.counts.could_be_stronger, review.counts.worth_revisiting)}</p>
          ) : null}
          {review.shorter_conversation ? <p className="dh-action-meta">{reportCopy.shorterNote}</p> : null}
        </div>
        <section className="dh-next-action" aria-labelledby="review-next">
          <p className="dh-section-label">{r.nextTitle}</p>
          {next ? (
            <>
              <h2 id="review-next" className="display">{focusFor(next.focus)?.title ?? review.next_step.title}</h2>
              <p className="dh-next-copy">{review.next_step.body}</p>
              <div className="dh-action-row">
                <Link className="dh-primary-action" href={startPracticeHref(role, next, review.role_profile_id)}>
                  {r.nextAction} <ArrowRight size={17} aria-hidden="true" />
                </Link>
                <span className="dh-action-meta">{modeCopy(next.mode).title} · {modeCopy(next.mode).length}</span>
              </div>
            </>
          ) : (
            <>
              <h2 id="review-next" className="display">{r.nextChoose}</h2>
              <div className="dh-action-row">
                <Link className="dh-primary-action" href={startPracticeHref(role, { mode: "QUICK_DRILL", focus: "role" }, review.role_profile_id)}>
                  {r.nextChooseAction} <ArrowRight size={17} aria-hidden="true" />
                </Link>
              </div>
            </>
          )}
        </section>
      </section>
      {report.assessment_scope ? (
        <aside className="dh-trust" data-testid="report-assessment-scope" aria-labelledby="review-scope-title">
          <Info size={20} aria-hidden="true" />
          <div>
            <p className="dh-section-label">{reportCopy.scope.eyebrow}</p>
            <h2 id="review-scope-title">{report.assessment_scope.round_label}</h2>
            <p>{reportCopy.scope.body}</p>
            <p>{reportCopy.scope.competencies(report.assessment_scope.competency_titles)}</p>
            <p>{reportCopy.scope.provenance}</p>
          </div>
        </aside>
      ) : null}

      <div className="dh-home-sections">
        <Section id="review-landed" title={r.landedTitle}>
          {strengths.length ? (
            <ul className="pr-reflection-list">
              {strengths.map((strength, index) => (
                <li key={strength.key}>
                  <p className="pr-need"><span>{r.roleNeed}</span> {strength.label}</p>
                  <p>{strength.note}</p>
                  <FromAnswer target={landedFrom[index]} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="dh-review-empty">{r.landedEmpty}</p>
          )}
        </Section>

        <Section id="review-strengthen" title={r.strengthenTitle}>
          {workItems.length ? (
            <div className="pr-reflection-list">
              {workItems.map((item, index) => (
              <div key={item.title}>
                {index === 0 && strengthen?.need ? <p className="pr-need"><span>{r.roleNeed}</span> {strengthen.need}</p> : null}
                <strong>{item.title}</strong>
                <p>{item.note}</p>
                {item.from_label ? <p className="dh-quiet">{`${r.relatesTo}: ${item.from_label}`}</p> : null}
                {index === 0 ? <FromAnswer target={strengthenFrom} /> : null}
                {index === 0 ? (
                  <>
                    {strengthenFrom ? (
                      <span className="dh-row-actions is-start">
                        <button className="dh-text-action" type="button" onClick={() => setOpenRetry(openRetry === "strengthen" ? null : "strengthen")} aria-expanded={openRetry === "strengthen"}>
                          {tryCopy.action} <ArrowRight size={15} aria-hidden="true" />
                        </button>
                      </span>
                    ) : null}
                  </>
                ) : null}
                {index === 0 && strengthenFrom && openRetry === "strengthen" ? (
                  <TryAgain
                    sessionId={sessionId}
                    answerTurnId={strengthenFrom.answerTurnId}
                    question={strengthenFrom.question}
                    firstAnswer={strengthenFrom.answer}
                    area={{ key: review.practice_focus ?? null, title: strengthen?.title ?? item.title }}
                    onSaved={saved}
                    onClose={() => setOpenRetry(null)}
                  />
                ) : null}
              </div>
              ))}
            </div>
          ) : (
            <p className="dh-review-empty">{r.strengthenEmpty}</p>
          )}
        </Section>


        {groups.length ? (
          <Section id="review-came-through" label={reportCopy.cameThrough.eyebrow} title={reportCopy.cameThrough.title} body={reportCopy.cameThrough.legend}>
            <div className="pr-claims">
              {groups.map((group) => <ClaimList key={group.key} group={group} />)}
            </div>
          </Section>
        ) : null}

        <Section id="review-repeat" title={r.repeatTitle}>
          <ul className="pr-repeat">
            <li>
              <a href={sameAnswer} onClick={strengthenFrom ? () => setOpenRetry("strengthen") : undefined}>
                <strong>{r.repeat.sameAnswer}</strong>
                <small>{r.repeat.sameAnswerBody}</small>
              </a>
            </li>
            <li>
              <Link href="/stories">
                <strong>{r.repeat.editStory}</strong>
                <small>{r.repeat.editStoryBody}</small>
              </Link>
            </li>
            <li>
              <Link href={startPracticeHref(role, { mode: "FOCUSED_PRACTICE" }, review.role_profile_id)}>
                <strong>{r.repeat.anotherTheme}</strong>
                <small>{r.repeat.anotherThemeBody}</small>
              </Link>
            </li>
            <li>
              <Link href="/dashboard">
                <strong>{r.repeat.finish}</strong>
                <small>{r.repeat.finishBody}</small>
              </Link>
            </li>
          </ul>
        </Section>

        <ReviewStorySuggestions sessionId={sessionId} />

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

/** The answer a reflection item came from: the question, and the moment the review noted. */
function FromAnswer({ target }: { target: AnswerTarget | null | undefined }) {
  if (!target) return null;
  return (
    <div className="pr-from-answer">
      <p>{r.fromAnswer} “{target.question}”</p>
      {target.quote ? <blockquote>{target.quote}</blockquote> : null}
    </div>
  );
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

/**
 * One group of what the person shared, as the backend grouped it. Each row says where the item came
 * from (their documents, the job description or the conversation); quotes are shown as said or
 * written, and Mirror's own sentence is marked as Mirror's note. Nothing missing is filled in.
 */
function ClaimList({ group }: { group: ClaimGroup }) {
  const copy = reportCopy.cameThrough;
  const openByDefault = group.key === "contradicted";
  return (
    <div className={`pr-claim-group is-${group.key}`}>
      <h3>{copy.groups[group.key]}</h3>
      <ul className="pr-claim-list">
        {group.claims.map((claim, index) => (
          <li key={claim.id}>
            <details className="pr-claim" open={openByDefault || (group.key === "held" && index === 0)}>
              <summary>
                <span className="pr-claim-text">{claim.claim_text}</span>
                <span className="sr-only">, </span>
                <span className="pr-source">{copy.sources[claim.source] ?? copy.sourceDocument}</span>
              </summary>
              <div className="pr-claim-body">
                {claim.evidence.length ? (
                  <ul className="pr-quotes">
                    {claim.evidence.map((quote, quoteIndex) => {
                      const spoken = Boolean(quote.turn_id);
                      const time = spoken ? timecode(quote.timecode_ms) : null;
                      const source = spoken ? copy.sources.SPOKEN : copy.sources[claim.source] ?? copy.sourceDocument;
                      const rowSource = copy.sources[claim.source] ?? copy.sourceDocument;
                      return (
                        <li key={`${quote.quote}-${quoteIndex}`}>
                          <blockquote>{quote.quote}</blockquote>
                          <p className="pr-quote-meta">
                            {source !== rowSource ? <span className="pr-source">{source}</span> : null}
                            {spoken ? <span className="pr-time">{time ?? copy.noTime}</span> : null}
                            <span>{copy.directions[quote.direction] ?? copy.directions.CONTEXT_ONLY}</span>
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="dh-review-empty">{copy.noQuotes}</p>
                )}
                <p className="pr-note"><span>{copy.mirrorNote}</span> {claim.explanation}</p>
              </div>
            </details>
          </li>
        ))}
      </ul>
    </div>
  );
}
