"use client";

import { ArrowRight, Check } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { mirrorApi, type InterviewMap } from "@/lib/api";
import { homePreparation as t } from "@/lib/copy";
import { areaHref, mapStrengths } from "@/lib/map-view";

/**
 * Home's snapshot of the current role: what is ready to discuss and what is still
 * worth preparing, both read from the Interview Map. It renders nothing when the
 * map is unavailable, because Home must never fail because of it.
 */
export function RolePreparation({ roleProfileId }: { roleProfileId: string | null }) {
  const [map, setMap] = useState<InterviewMap | null>(null);

  useEffect(() => {
    if (!roleProfileId) return;
    let active = true;
    void mirrorApi
      .interviewMap(roleProfileId)
      .then((next) => active && setMap(next))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [roleProfileId]);

  if (!map || map.state !== "READY") return null;
  const ready = mapStrengths(map, 3);
  const areas = map.preparation_areas.slice(0, 2);

  return (
    <section className="dh-section" aria-labelledby="dh-preparation-title">
      <div className="dh-section-heading">
        <div>
          <p className="dh-section-label">{t.label}</p>
          <h2 id="dh-preparation-title" className="display">{t.title(map.themes.length, map.preparation_areas.length)}</h2>
        </div>
        <Link className="dh-text-action" href={`/roles/${map.role_profile_id}`}>
          {t.open} <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>
      <div className="dh-review-columns">
        <div>
          <h3>{t.ready}</h3>
          {ready.length ? (
            <ul className="dh-review-list">
              {ready.map((theme) => (
                <li key={theme.key}>
                  <Check size={17} aria-hidden="true" />
                  <span>{theme.name}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dh-review-empty">{t.readyEmpty}</p>
          )}
        </div>
        <div>
          <h3>{t.prepare}</h3>
          {areas.length ? (
            <ul className="dh-review-list">
              {areas.map((area) => (
                <li key={area.key}>
                  <ArrowRight size={17} aria-hidden="true" />
                  <Link href={areaHref(map, area)}>{area.title}</Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dh-review-empty">{t.prepareEmpty}</p>
          )}
        </div>
      </div>
    </section>
  );
}
