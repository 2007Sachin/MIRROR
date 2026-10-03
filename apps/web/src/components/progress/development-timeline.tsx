"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { StateMark } from "@/components/progress/state-mark";
import type { RoleProgress } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { formatDay, formatShortDay } from "@/lib/dashboard-view";
import { areaLabel, dimensionAnswersHref, dimensionHref, markerLabel, stateLabel } from "@/lib/progress-view";

/**
 * Development over time: one column per practice, one row per part of an answer.
 * Every marker is a button that says what it means and links to the answers behind it.
 * The table is the text equivalent, and it scrolls inside its own box on narrow screens.
 */
export function DevelopmentTimeline({ progress }: { progress: RoleProgress }) {
  const [picked, setPicked] = useState<{ key: string; sessionId: string } | null>(null);
  const panel = useRef<HTMLDivElement>(null);
  // Moving focus to the detail is what announces it to a screen reader.
  useEffect(() => {
    if (picked) panel.current?.focus();
  }, [picked]);
  const columns = progress.dimensions[0]?.cells ?? [];
  const anyExplored = progress.dimensions.some((dimension) => dimension.cells.some((cell) => cell.state !== "NOT_EXPLORED"));

  if (!columns.length || !anyExplored) {
    return <p className="pg-quiet">{t.timeline.notEnough}</p>;
  }

  const dimension = picked ? progress.dimensions.find((item) => item.key === picked.key) : null;
  const cell = dimension?.cells.find((item) => item.session_id === picked?.sessionId);
  const practice = progress.practices.find((item) => item.session_id === picked?.sessionId);
  const roleId = progress.role_profile_id;

  return (
    <div className="pg-timeline-wrap">
      <div className="pg-timeline-scroll" role="region" aria-label={t.timeline.tableLabel} tabIndex={0}>
        <table className="pg-timeline">
          <caption className="sr-only">{t.timeline.tableLabel}</caption>
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">{t.timeline.areaColumn}</span></th>
              {columns.map((column) => (
                <th key={column.session_id} scope="col">
                  <span>{t.timeline.practice(column.number)}</span>
                  <small>{formatShortDay(column.completed_at)}</small>
                </th>
              ))}
              <th scope="col"><span className="sr-only">{t.timeline.viewAnswers}</span></th>
            </tr>
          </thead>
          <tbody>
            {progress.dimensions.map((row) => (
              <tr key={row.key}>
                <th scope="row">
                  <Link href={dimensionHref(roleId, row.key)}>{areaLabel(row.key)}</Link>
                </th>
                {row.cells.map((item) => {
                  const active = picked?.key === row.key && picked.sessionId === item.session_id;
                  return (
                    <td key={item.session_id}>
                      <button
                        type="button"
                        className={`pg-marker${active ? " is-active" : ""}`}
                        aria-pressed={active}
                        aria-label={markerLabel(item, row.key)}
                        onClick={() => setPicked(active ? null : { key: row.key, sessionId: item.session_id })}
                      >
                        <StateMark kind={item.state} />
                      </button>
                    </td>
                  );
                })}
                <td>
                  <Link className="pg-row-arrow" href={dimensionHref(roleId, row.key)} aria-label={t.timeline.rowLink(areaLabel(row.key))}>
                    <ArrowRight size={15} aria-hidden="true" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {columns.length > 3 ? <p className="pg-hint">{t.timeline.scrollHint}</p> : null}

      <ul className="pg-legend" aria-label={t.timeline.legendLabel}>
        {(["COMING_THROUGH", "DEVELOPING", "NEEDS_PRACTICE", "NOT_EXPLORED"] as const).map((state) => (
          <li key={state}>
            <StateMark kind={state} size={14} /> {stateLabel(state)}
          </li>
        ))}
      </ul>

      {dimension && cell ? (
        <div ref={panel} tabIndex={-1} className="pg-cell-detail" role="region" aria-label={markerLabel(cell, dimension.key)}>
          <p className="dh-section-label">
            {t.timeline.practice(cell.number)} · {formatDay(cell.completed_at)}
          </p>
          <h3>{areaLabel(dimension.key)}</h3>
          <p className="pg-cell-state">
            <StateMark kind={cell.state} /> {stateLabel(cell.state)}
          </p>
          {cell.state === "NOT_EXPLORED" ? <p>{t.timeline.notExplored}</p> : null}
          {cell.state !== "NOT_EXPLORED" && cell.answers_seen > 0 ? (
            <p>{t.timeline.counts(cell.answers_strong, cell.answers_seen)}</p>
          ) : null}
          {practice?.shorter_conversation ? <p className="pg-quiet">{t.timeline.shorter}</p> : null}
          <div className="pg-cell-actions">
            {cell.state !== "NOT_EXPLORED" && cell.answers_seen > 0 ? (
              <Link className="dh-text-action" href={dimensionAnswersHref(roleId, dimension.key, cell.session_id)}>
                {t.timeline.viewAnswers} <ArrowRight size={15} aria-hidden="true" />
              </Link>
            ) : null}
            <button type="button" className="dh-text-action is-quiet" onClick={() => setPicked(null)}>
              {t.timeline.close}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
