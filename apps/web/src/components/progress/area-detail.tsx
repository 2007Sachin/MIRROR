"use client";

import { ArrowRight } from "@phosphor-icons/react";
import Link from "next/link";
import { useMemo } from "react";

import {
  PageAlert,
  PageHeader,
  PageLoading,
  PageShell,
  Section,
  usePageData,
} from "@/components/workspace/page-shell";
import { mirrorApi } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { startPracticeHref } from "@/lib/practice-view";
import { AREA_KEYS, areaLabel, findArea, stateClass } from "@/lib/progress-view";

export function AreaDetail({ areaKey }: { areaKey: string }) {
  const known = AREA_KEYS.includes(areaKey);
  const { state, data, error, reload } = usePageData(() => mirrorApi.progress(), t.errors.load);

  const area = useMemo(() => (known ? findArea(data, areaKey) : null), [data, areaKey, known]);
  const meaning = t.meanings[areaKey];
  const notExplored = area?.state === "Not explored yet";

  return (
    <PageShell>
      <PageHeader
        eyebrow={t.eyebrow}
        title={known ? areaLabel(areaKey) : t.area.notFound}
        back={{ href: "/progress", label: t.area.back }}
        action={
          known ? (
            <Link className="dh-primary-action" href={startPracticeHref(data?.role, area?.focus)}>
              {t.area.practiceThis} <ArrowRight size={17} aria-hidden="true" />
            </Link>
          ) : null
        }
      />

      {!known ? <p className="dh-review-empty">{t.area.notFound}</p> : null}
      {known && state === "loading" ? <PageLoading /> : null}
      {known && state === "error" ? <PageAlert message={error} onRetry={reload} /> : null}

      {known && state === "ready" ? (
        <div className="dh-home-sections">
          {area ? (
            <p className={`dh-development-state is-inline ${stateClass(area.state)}`}>
              {area.state}
              {area.directionLabel ? <span className="dh-direction-inline"> · {area.directionLabel}</span> : null}
            </p>
          ) : null}

          {meaning ? (
            <Section id="area-means" label={t.area.whatThisMeans} title={t.area.whatThisMeans}>
              <p className="dh-prose">{meaning.means}</p>
            </Section>
          ) : null}

          <Section id="area-heard" label={t.area.whatWeHeard} title={t.area.whatWeHeard}>
            {!area || notExplored ? (
              <p className="dh-review-empty">{area?.note || t.area.notExplored}</p>
            ) : (
              <>
                <p className="dh-prose">{area.note}</p>
                <p className="dh-prose">{t.heard[areaKey]}</p>
              </>
            )}
          </Section>

          {area && area.excerpts.length ? (
            <Section
              id="area-excerpts"
              label={t.area.fromYourPractice}
              title={t.area.fromYourPractice}
              body={t.area.fromYourPracticeNote}
            >
              <ul className="dh-quote-list">
                {area.excerpts.map((excerpt, index) => (
                  <li key={`${excerpt.quote}-${index}`}>
                    <blockquote>{excerpt.quote}</blockquote>
                    <p>{excerpt.note}</p>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}

          {meaning ? (
            <Section id="area-improve" label={t.area.howToImprove} title={t.area.howToImprove}>
              <ol className="dh-step-list">
                {meaning.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <div className="dh-action-row">
                <Link className="dh-primary-action" href={startPracticeHref(data?.role, area?.focus)}>
                  {t.area.practiceThis} <ArrowRight size={17} aria-hidden="true" />
                </Link>
              </div>
            </Section>
          ) : null}
        </div>
      ) : null}
    </PageShell>
  );
}
