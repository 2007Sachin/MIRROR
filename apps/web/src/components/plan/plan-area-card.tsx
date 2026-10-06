"use client";

import Link from "next/link";

import type { PlanAction, PlanArea, PlanLink } from "@/lib/api-plan";
import { planCopy as t } from "@/lib/copy-plan";

export type PlanHrefs = Record<PlanAction, string>;

/** One role need: why it appears, what you have, what would strengthen it, and what to do. */
export function PlanAreaCard({
  area,
  recommended,
  demoted = false,
  hrefs,
  busy,
  onChoose,
}: {
  area: PlanArea;
  recommended: boolean;
  /** Another section holds the page's one filled action, so this card's action stays quiet. */
  demoted?: boolean;
  hrefs: PlanHrefs;
  busy: boolean;
  onChoose: (link: PlanLink, confirmed: boolean) => void;
}) {
  const headingId = `plan-${area.key}`;
  const actions: { key: PlanAction; label: string }[] = [
    { key: "PRACTICE", label: t.actions.practice },
    { key: "STORY", label: t.actions.story },
    { key: "ADD_EXAMPLE", label: t.actions.add },
  ];
  const main = actions.find((action) => action.key === area.primary_action) ?? actions[0];
  const rest = actions.filter((action) => action !== main);

  return (
    <article className="pl-card" data-recommended={recommended || undefined} aria-labelledby={headingId}>
      <header className="pl-card-head">
        {recommended ? <p className="pl-start">{t.startHere}</p> : null}
        <h2 id={headingId} className="pl-title">{area.title}</h2>
        <span className="pl-status" data-status={area.status}>{t.status[area.status]}</span>
      </header>

      <p className="pl-why">
        {area.why ? <><span className="pl-why-label">{t.whyFromRole}</span> “{area.why}”</> : t.whyGeneral}
      </p>

      <section className="pl-block" aria-label={t.haveTitle}>
        <h3>{t.haveTitle}</h3>
        {area.have.length ? (
          <ul className="pl-links">
            {area.have.map((link) => (
              <li key={link.evidence_item_id ?? link.story_id}>
                <span className="pl-link-main">
                  <span className="pl-kind">{link.kind === "STORY" ? t.story : t.example}</span>
                  <span>{link.title}</span>
                  {link.reason ? <span className="pl-reason">{t.reason[link.reason]}</span> : null}
                </span>
                <button type="button" className="dh-text-action is-quiet" disabled={busy} onClick={() => onChoose(link, false)} aria-label={`${t.unlink}: ${link.title}`}>
                  {t.unlink}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="pl-muted">{t.haveEmpty}</p>
        )}
        {area.suggested.length ? (
          <>
            <h4 className="pl-subhead">{t.suggestedTitle}</h4>
            <ul className="pl-links">
              {area.suggested.map((link) => (
                <li key={link.evidence_item_id ?? link.story_id}>
                  <span className="pl-link-main">
                    <span className="pl-kind">{link.kind === "STORY" ? t.story : t.example}</span>
                    <span>{link.title}</span>
                  </span>
                  <span className="pl-link-actions">
                    <button type="button" className="dh-text-action" disabled={busy} onClick={() => onChoose(link, true)} aria-label={`${t.confirm}: ${link.title}`}>
                      {t.confirm}
                    </button>
                    <button type="button" className="dh-text-action is-quiet" disabled={busy} onClick={() => onChoose(link, false)} aria-label={`${t.dismiss}: ${link.title}`}>
                      {t.dismiss}
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>

      <section className="pl-block" aria-label={t.strengthenTitle}>
        <h3>{t.strengthenTitle}</h3>
        <p>{area.strengthen}</p>
      </section>

      <div className="pl-actions">
        {/* One filled action per page: only the recommended need's main action is filled. */}
        <Link className={recommended && !demoted ? "dh-primary-action" : "dh-primary-action is-quiet"} href={hrefs[main.key]}>
          {main.label}
        </Link>
        {rest.map((action) => (
          <Link key={action.key} className="dh-text-action" href={hrefs[action.key]}>
            {action.label}
          </Link>
        ))}
      </div>
    </article>
  );
}
