"use client";

import { ArrowRight } from "@phosphor-icons/react";
import { useCallback, useEffect, useState } from "react";

import { StepHeading, type Report } from "@/components/onboarding/shared";
import { mirrorApi, type InterviewMap, type PracticeChoice } from "@/lib/api";
import { getEvidence, type EvidenceItem } from "@/lib/api-evidence";
import { onboardingCopy } from "@/lib/copy-onboarding";
import { planHref } from "@/lib/copy-targets";
import { isFocusKey, startPracticeHref } from "@/lib/practice-view";

const t = onboardingCopy.plan;
type Area = { key: string; title: string; body: string; choice: PracticeChoice };

/** The three areas to start with: the role's preparation areas first, topped up from its themes. */
function priorityAreas(map: InterviewMap): Area[] {
  const themeName = (key: string | null) => map.themes.find((theme) => theme.key === key)?.name ?? null;
  const areas: Area[] = map.preparation_areas.map((area) => {
    const focus = isFocusKey(area.focus) && area.focus !== "full" ? area.focus : "role";
    const theme = focus === "role" ? themeName(area.theme_key) ?? area.title : null;
    return { key: area.key, title: area.title, body: area.body, choice: { mode: "QUICK_DRILL", focus, theme } };
  });
  for (const theme of map.themes) {
    if (areas.length >= 3) break;
    if (areas.some((area) => area.choice.theme === theme.name)) continue;
    areas.push({ key: theme.key, title: theme.name, body: theme.source_text ?? "", choice: { mode: "QUICK_DRILL", focus: "role", theme: theme.name } });
  }
  return areas.slice(0, 3);
}

/** Approved examples, those with an outcome in numbers first. */
function strongest(items: EvidenceItem[]) {
  const rank = (item: EvidenceItem) => (item.metric ? 0 : 2) + (item.kind === "ACHIEVEMENT" ? 0 : 1);
  return items.filter((item) => item.status === "APPROVED" && item.kind !== "SKILL").sort((a, b) => rank(a) - rank(b)).slice(0, 3);
}

export function PlanReadyStep({
  roleProfileId,
  roleName,
  eyebrow,
  note,
  report,
  onExit,
}: {
  roleProfileId: string;
  roleName: string;
  eyebrow?: string;
  note?: string;
  report: Report;
  /** Both exits are equal: the parent saves anything it needs, then goes to `href`. */
  onExit: (href: string) => Promise<void>;
}) {
  const [map, setMap] = useState<InterviewMap | null>(null);
  const [examples, setExamples] = useState<EvidenceItem[]>([]);
  const [failed, setFailed] = useState(false);
  const [leaving, setLeaving] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const [loadedMap, evidence] = await Promise.all([mirrorApi.interviewMap(roleProfileId), getEvidence().catch(() => null)]);
      setMap(loadedMap);
      setExamples(strongest(evidence?.items ?? []));
      report("");
    } catch (reason) {
      setFailed(true);
      report(t.loadError, reason);
    }
  }, [roleProfileId, report]);

  useEffect(() => {
    void load();
  }, [load]);

  async function leave(href: string) {
    setLeaving(true);
    try {
      await onExit(href);
    } finally {
      setLeaving(false);
    }
  }

  const areas = map ? priorityAreas(map) : [];
  const first = areas[0];
  const practiceHref = startPracticeHref(roleName, first?.choice ?? { mode: "QUICK_DRILL" }, roleProfileId);

  return (
    <section className="ob-step" aria-busy={!map && !failed}>
      <StepHeading eyebrow={eyebrow} title={t.title(roleName)} intro={t.intro} />
      {note && <p className="op-confirm">{note}</p>}
      {!map && !failed && <p role="status" className="op-muted">{t.loading}</p>}
      {failed && <button type="button" className="button-secondary op-target" onClick={() => void load()}>{t.retry}</button>}
      {map && (
        <div className="op-plan">
          <section aria-labelledby="op-areas">
            <h2 id="op-areas">{t.areasTitle}</h2>
            <ol className="op-areas">
              {areas.map((area) => (
                <li key={area.key} className="op-card">
                  <p className="op-strong">{area.title}</p>
                  {area.body && <p className="op-muted">{area.body}</p>}
                </li>
              ))}
            </ol>
          </section>
          <section aria-labelledby="op-examples">
            <h2 id="op-examples">{t.examplesTitle}</h2>
            {examples.length ? (
              <ul className="op-list">
                {examples.map((item) => (
                  <li key={item.id} className="op-item">
                    <div className="op-item-body">
                      <p className="op-strong">{item.title}</p>
                      {item.metric && <p className="op-muted">{item.metric}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            ) : <p className="op-muted">{t.noExamples}</p>}
          </section>
          <section aria-labelledby="op-first" className="op-card op-first">
            <h2 id="op-first">{t.firstTitle}</h2>
            <p>{first ? t.first(first.title) : t.firstFallback}</p>
          </section>
        </div>
      )}
      <div className="op-exit-row">
        <button type="button" className="button-primary op-target" disabled={leaving} onClick={() => void leave(planHref(roleProfileId))}>
          {leaving ? t.opening : t.seePlan} <ArrowRight size={16} aria-hidden="true" />
        </button>
        <button type="button" className="op-text op-target" disabled={leaving} onClick={() => void leave(practiceHref)}>
          {t.startInstead}
        </button>
      </div>
      <p className="op-muted">{t.exitsNote}</p>
    </section>
  );
}
