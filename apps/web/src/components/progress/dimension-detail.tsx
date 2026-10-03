"use client";

import "@/styles/progress.css";

import { ArrowLeft, ArrowRight, CheckCircle, WarningCircle } from "@phosphor-icons/react";
import Link from "next/link";

import { StateMark } from "@/components/progress/state-mark";
import { useRoleProgress } from "@/components/progress/use-role-progress";
import { EmptyState, PageAlert, PageLoading, PageShell, Section } from "@/components/workspace/page-shell";
import type { ProgressDimension, RoleProgress } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { formatShortDay } from "@/lib/dashboard-view";
import {
  AREA_KEYS,
  answerHref,
  answerRows,
  areaLabel,
  dimensionAnswersHref,
  dimensionFor,
  focusedPracticeHref,
  patternLine,
  roleProgressHref,
} from "@/lib/progress-view";

const SHOWN = 4;

/** One part of an answer for one role: the pattern, the answers behind it, and what to practise. */
export function DimensionView({ data, dimensionKey }: { data: RoleProgress; dimensionKey: string }) {
  const roleProfileId = data.role_profile_id;
  const dimension = AREA_KEYS.includes(dimensionKey) ? dimensionFor(data, dimensionKey) : null;
  const rows = answerRows(data.answers, dimensionKey);
  const tone = dimension ? patternTone(dimension) : "is-neutral";

  return (
    <>
      <Link className="dh-back-link" href={roleProgressHref(roleProfileId)}>
        <ArrowLeft size={15} aria-hidden="true" /> {t.dimension.back(data.target_role)}
      </Link>

      {!dimension ? (
        <EmptyState title={t.dimension.unknown} body={t.role.notFound.body} action={{ href: roleProgressHref(roleProfileId), label: t.dimension.back(data.target_role) }} />
      ) : (
        <div className="dh-home-sections">
          <header>
            <h1 className="dh-title display">{areaLabel(dimensionKey)}</h1>
            <p className="dh-page-intro">{t.definitions[dimensionKey]}</p>
          </header>

          <section className={`pg-pattern ${tone}`} aria-labelledby="pattern-title">
            <p className="dh-section-label" id="pattern-title">{t.dimension.recentTitle}</p>
            <p className="pg-pattern-line">
              {tone === "is-attention" ? (
                <WarningCircle size={20} weight="fill" aria-hidden="true" />
              ) : tone === "is-positive" ? (
                <CheckCircle size={20} aria-hidden="true" />
              ) : (
                <StateMark kind={dimension.state} />
              )}
              <strong>{patternLine(dimension)}</strong>
            </p>
            {dimension.state !== "NOT_EXPLORED" && dimension.note ? <p className="pg-pattern-note">{dimension.note}</p> : null}
          </section>

          <Section id="supporting" title={t.dimension.supportingTitle} body={t.dimension.supportingBody}>
            {rows.length ? (
              <>
                <ul className="pg-rows">
                  {rows.slice(0, SHOWN).map(({ answer, signal }) => (
                    <li key={`${answer.session_id}:${answer.answer_turn_id}`}>
                      <Link href={answerHref(roleProfileId, answer.session_id, answer.answer_turn_id, dimensionKey)}>
                        <StateMark kind={signal.state} />
                        <span className="pg-row-copy">
                          <strong>{answer.question}</strong>
                          <small>
                            {t.timeline.practice(answer.practice_number)} · {formatShortDay(answer.completed_at)}
                          </small>
                        </span>
                        <span className="pg-row-state">{t.answers.states[signal.state]}</span>
                        <ArrowRight size={16} aria-hidden="true" />
                      </Link>
                    </li>
                  ))}
                </ul>
                {rows.length > SHOWN ? (
                  <Link className="dh-text-action" href={dimensionAnswersHref(roleProfileId, dimensionKey)}>
                    {t.dimension.seeAll} ({rows.length}) <ArrowRight size={15} aria-hidden="true" />
                  </Link>
                ) : null}
              </>
            ) : (
              <p className="dh-review-empty">{t.dimension.supportingEmpty}</p>
            )}
          </Section>

          <section className="pg-next" aria-labelledby="next-title">
            <h2 id="next-title" className="display">{t.dimension.nextTitle}</h2>
            <p>{t.dimension.next[dimensionKey]}</p>
            <div className="pg-actions">
              <Link className="pg-button is-dark" href={focusedPracticeHref(data.target_role, roleProfileId, dimension)}>
                {t.dimension.startFocused}
              </Link>
              <Link className="pg-button" href={dimensionAnswersHref(roleProfileId, dimensionKey)}>
                {t.dimension.viewQuestions}
              </Link>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

export function DimensionDetail({ roleProfileId, dimensionKey }: { roleProfileId: string; dimensionKey: string }) {
  const { state, data, error, reload } = useRoleProgress(roleProfileId);

  return (
    <PageShell>
      {state === "loading" ? <PageLoading /> : null}
      {state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}
      {state === "ready" && !data ? (
        <EmptyState title={t.role.notFound.title} body={t.role.notFound.body} action={{ href: "/progress", label: t.role.back }} />
      ) : null}
      {state === "ready" && data ? <DimensionView data={data} dimensionKey={dimensionKey} /> : null}
    </PageShell>
  );
}

/** The tone follows the same sentence the page shows: the trend when there is a current one, else the state. */
function patternTone(dimension: ProgressDimension) {
  if (dimension.trend && dimension.current) {
    if (dimension.trend === "LESS") return "is-attention";
    if (dimension.trend === "MORE") return "is-positive";
  }
  if (dimension.state === "NEEDS_PRACTICE") return "is-attention";
  if (dimension.state === "COMING_THROUGH") return "is-positive";
  return "is-neutral";
}
