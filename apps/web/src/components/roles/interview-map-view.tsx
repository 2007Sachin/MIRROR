import { ArrowRight, Check } from "@phosphor-icons/react";
import Link from "next/link";

import { Section } from "@/components/workspace/page-shell";
import type { InterviewMap } from "@/lib/api";
import { interviewMap as t } from "@/lib/copy";
import {
  areaActionLabel,
  areaHref,
  coverageClass,
  coverageLabel,
  experienceNotice,
  mapStrengths,
  pressureTestHref,
} from "@/lib/map-view";

export function InterviewMapView({ map }: { map: InterviewMap }) {
  if (map.state === "ROLE_PREPARING") return <p className="dh-review-empty">{t.states.preparing}</p>;
  if (map.state === "ROLE_UNREADABLE") return <p className="dh-review-empty">{t.states.unreadable}</p>;

  const strengths = mapStrengths(map);
  const notice = experienceNotice(map);

  return (
    <>
      <Section id="map-areas" label={t.eyebrow} title={t.areasTitle}>
        {map.preparation_areas.length ? (
          <ul className="dh-plain-list">
            {map.preparation_areas.map((area) => (
              <li key={area.key}>
                <strong>{area.title}</strong>
                <small>{area.body}</small>
                <Link className="dh-text-action" href={areaHref(map, area)}>
                  {areaActionLabel(area.action)} <ArrowRight size={15} aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="dh-review-empty">{t.areasEmpty}</p>
        )}
      </Section>

      <Section id="map-strengths" title={t.strengthsTitle}>
        {notice ? <p className="dh-guidance">{notice}</p> : null}
        {strengths.length ? (
          <ul className="dh-change-list">
            {strengths.map((theme) => (
              <li key={theme.key} className="is-improved">
                <Check size={17} aria-hidden="true" />
                <span>
                  <strong>{theme.name}</strong>
                  {theme.matches[0] ? (
                    <small className="dh-match">
                      {t.matchKinds[theme.matches[0].kind] ?? t.matchKinds.WORK}: {theme.matches[0].label}
                    </small>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="dh-review-empty">{t.strengthsEmpty}</p>
        )}
      </Section>

      <Section id="map-themes" title={t.themesTitle} body={map.role_from_job_description ? t.intro : t.inferred}>
        <ul className="dh-plain-list">
          {map.themes.map((theme) => (
            <li key={theme.key}>
              <strong>{theme.name}</strong>
              {theme.source_text ? <small className="dh-quiet">{`${t.fromJob}: “${theme.source_text}”`}</small> : null}
              <span className={`dh-row-state ${coverageClass(theme.coverage)}`}>{coverageLabel(theme.coverage)}</span>
            </li>
          ))}
        </ul>
        {map.also_expected.length ? (
          <div className="dh-tag-groups">
            <div className="dh-tag-group">
              <h3>{t.alsoExpected}</h3>
              <ul>
                {map.also_expected.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}
      </Section>

      <Section id="map-questions" title={t.questionsTitle} body={t.questionsNote}>
        <ul className="dh-quote-list">
          {map.questions.map((question) => (
            <li key={question.text}>
              <blockquote>{question.text}</blockquote>
              <p>{question.why}</p>
            </li>
          ))}
        </ul>
      </Section>

      {map.experience_state === "READY" ? (
        <section className="dh-continue" aria-labelledby="map-pressure">
          <div>
            <p className="dh-section-label">{t.pressureCta}</p>
            <h2 id="map-pressure" className="display">{t.pressureBody}</h2>
          </div>
          <div className="dh-continue-actions">
            <Link className="dh-primary-action" href={pressureTestHref(map.role_profile_id)}>
              {t.pressureCta} <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </section>
      ) : null}
    </>
  );
}
