"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";

import { StateMark } from "@/components/progress/state-mark";
import type { ProgressAnswer } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { formatShortDay } from "@/lib/dashboard-view";
import { ANSWER_FILTERS, answerHref, answerKey, answerRows, areaLabel, type AnswerFilter } from "@/lib/progress-view";

/**
 * The answers behind an area (or behind the whole role). Only filters Mirror can back up
 * are offered: an answer is "strong" or "needs practice" only when the review said so.
 */
export function AnswerList({
  roleProfileId,
  answers,
  dimension,
  practiceSessionId,
}: {
  roleProfileId: string;
  answers: ProgressAnswer[];
  dimension: string | null;
  practiceSessionId?: string;
}) {
  const [filter, setFilter] = useState<AnswerFilter>("ALL");
  const scoped = practiceSessionId ? answers.filter((answer) => answer.session_id === practiceSessionId) : answers;
  const everything = answerRows(scoped, dimension);
  const rows = answerRows(scoped, dimension, filter);

  if (!everything.length) return <p className="dh-review-empty">{t.answers.empty}</p>;

  return (
    <div className="pg-answers">
      <div className="pg-filters" role="group" aria-label={t.answers.filterLabel}>
        {ANSWER_FILTERS.map((option) => (
          <button
            key={option}
            type="button"
            className={filter === option ? "is-active" : undefined}
            aria-pressed={filter === option}
            onClick={() => setFilter(option)}
          >
            {t.answers.filters[option]} ({answerRows(scoped, dimension, option).length})
          </button>
        ))}
      </div>

      {rows.length ? (
        <ul className="pg-rows">
          {rows.map(({ answer, signal }) => (
            <li key={`${answerKey(answer)}:${signal.dimension}`}>
              <Link href={answerHref(roleProfileId, answer.session_id, answer.answer_turn_id, dimension ?? signal.dimension)}>
                <StateMark kind={signal.state} />
                <span className="pg-row-copy">
                  <strong>{answer.question}</strong>
                  <small>
                    {t.timeline.practice(answer.practice_number)} · {formatShortDay(answer.completed_at)} ·{" "}
                    {t.answers.questionOf(answer.question_position, answer.question_total)}
                  </small>
                  {dimension === null ? (
                    <span className="pg-chips">
                      {answer.signals.map((item) => (
                        <span key={item.dimension} className="pg-chip">
                          <StateMark kind={item.state} size={12} /> {areaLabel(item.dimension)}
                        </span>
                      ))}
                    </span>
                  ) : null}
                </span>
                <span className="pg-row-state">{t.answers.states[signal.state]}</span>
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="dh-review-empty">{t.answers.emptyFilter}</p>
      )}
    </div>
  );
}
