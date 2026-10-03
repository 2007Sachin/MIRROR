"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useState } from "react";

import { StateMark } from "@/components/progress/state-mark";
import type { ProgressAnswer, RoleProgress } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { formatShortDay } from "@/lib/dashboard-view";
import { answerHref, answerKey } from "@/lib/progress-view";

/**
 * What the role looks for, and where it has come up in the person's answers.
 * "Not explored yet" is a plain statement of what hasn't come up, never a weakness.
 */
export function RoleConnection({ progress }: { progress: RoleProgress }) {
  const [open, setOpen] = useState<string | null>(null);
  const { connection } = progress;
  const byKey = new Map<string, ProgressAnswer>(progress.answers.map((answer) => [answerKey(answer), answer]));

  if (connection.state === "PREPARING") return <p className="dh-review-empty">{t.connection.preparing}</p>;
  if (connection.state === "UNAVAILABLE" || !connection.areas.length) return <p className="dh-review-empty">{t.connection.unavailable}</p>;
  if (!progress.practice_count) return <p className="dh-review-empty">{t.connection.noPractice}</p>;

  return (
    <div className="pg-connection">
      <ul className="pg-rows is-plain">
        {connection.areas.map((area) => {
          const answers = area.answers
            .map((ref) => byKey.get(answerKey(ref)))
            .filter((answer): answer is ProgressAnswer => Boolean(answer));
          const expanded = open === area.key;
          return (
            <li key={area.key}>
              <div className="pg-area-row">
                <StateMark kind={area.seen} />
                <span className="pg-row-copy">
                  <strong>{area.name}</strong>
                  <small>
                    {t.connection.seen[area.seen]}
                    {area.practices_seen ? ` · ${t.connection.practices(area.practices_seen)}` : ""}
                  </small>
                </span>
                {area.seen !== "NOT_EXPLORED" ? (
                  <button
                    type="button"
                    className="dh-text-action"
                    aria-expanded={expanded}
                    aria-controls={`area-${area.key}`}
                    onClick={() => setOpen(expanded ? null : area.key)}
                  >
                    {expanded ? t.connection.hideAnswers : t.connection.showAnswers}
                  </button>
                ) : null}
              </div>
              {expanded ? (
                <div id={`area-${area.key}`} className="pg-area-answers">
                  <p className="dh-section-label">{t.connection.answersFor(area.name)}</p>
                  {answers.length ? (
                    <ul className="pg-rows">
                      {answers.map((answer) => (
                        <li key={answerKey(answer)}>
                          <Link href={answerHref(progress.role_profile_id, answer.session_id, answer.answer_turn_id)}>
                            <span className="pg-row-copy">
                              <strong>{answer.question}</strong>
                              <small>
                                {t.timeline.practice(answer.practice_number)} · {formatShortDay(answer.completed_at)}
                              </small>
                            </span>
                            <ArrowRight size={16} aria-hidden="true" />
                          </Link>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="dh-review-empty">{t.connection.empty}</p>
                  )}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
      <p className="pg-quiet">{t.connection.note}</p>
    </div>
  );
}
