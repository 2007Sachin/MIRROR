"use client";

import { ArrowRight } from "@phosphor-icons/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { StepHeading, type Report } from "@/components/onboarding/shared";
import { ApiError, mirrorApi, type InterviewMap, type PracticeChoice } from "@/lib/api";
import { CandidateStagePlanEditor } from "@/components/plan/candidate-stage-plan-editor";
import { getBlueprint, targetsForRole, type BlueprintView, type TargetView } from "@/lib/api-targets";
import { getEvidence, type EvidenceItem } from "@/lib/api-evidence";
import { onboardingCopy } from "@/lib/copy-onboarding";
import { planHref, targetCopy, targetLine } from "@/lib/copy-targets";
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

const stageCopy = targetCopy.section.candidateStages;

type StageBlueprintState =
  | { kind: "loading"; target: TargetView }
  | { kind: "error"; target: TargetView }
  | { kind: "unavailable"; target: TargetView }
  | { kind: "archived"; target: TargetView }
  | { kind: "ready"; target: TargetView; view: BlueprintView };

function CandidateStagePrompt({ roleProfileId, onTargetSelected, onDirtyChange }: { roleProfileId: string; onTargetSelected: (targetId: string | null) => void; onDirtyChange: (dirty: boolean) => void }) {
  const [listState, setListState] = useState<"loading" | "ready" | "none" | "unavailable" | "error">("loading");
  const [targets, setTargets] = useState<TargetView[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [blueprintState, setBlueprintState] = useState<StageBlueprintState | null>(null);
  const [editorDirty, setEditorDirty] = useState(false);
  const requestId = useRef(0);

  const loadBlueprint = useCallback(async (target: TargetView) => {
    const id = ++requestId.current;
    setBlueprintState({ kind: "loading", target });
    try {
      const view = await getBlueprint(target.id);
      if (id !== requestId.current) return;
      if (view.availability !== "AVAILABLE" || !view.target || view.target.id !== target.id || view.target.status !== "ACTIVE") {
        setBlueprintState({ kind: "unavailable", target });
        return;
      }
      setBlueprintState({ kind: "ready", target, view });
    } catch (reason) {
      if (id !== requestId.current) return;
      if (reason instanceof ApiError && reason.code === "TARGET_ARCHIVED") setBlueprintState({ kind: "archived", target });
      else setBlueprintState({ kind: "error", target });
    }
  }, []);

  const loadTargets = useCallback(async () => {
    const id = ++requestId.current;
    setListState("loading");
    setTargets([]);
    setSelectedId("");
    setBlueprintState(null);
    onTargetSelected(null);
    onDirtyChange(false);
    try {
      const found = await targetsForRole(roleProfileId);
      if (id !== requestId.current) return;
      if (found.kind === "UNAVAILABLE") {
        setListState("unavailable");
        return;
      }
      if (found.kind === "NONE") {
        setListState("none");
        return;
      }
      setTargets(found.targets);
      setListState("ready");
      if (found.targets.length === 1) {
        const target = found.targets[0];
        setSelectedId(target.id);
        onTargetSelected(target.id);
        void loadBlueprint(target);
      }
    } catch {
      if (id === requestId.current) setListState("error");
    }
  }, [loadBlueprint, onDirtyChange, onTargetSelected, roleProfileId]);

  useEffect(() => {
    void loadTargets();
    return () => { requestId.current += 1; };
  }, [loadTargets]);

  const selectedTarget = targets.find((target) => target.id === selectedId) ?? null;
  function chooseTarget(id: string) {
    if (id === selectedId) return;
    if (editorDirty && !window.confirm(stageCopy.switchConfirm)) return;
    setEditorDirty(false);
    onDirtyChange(false);
    setSelectedId(id);
    onTargetSelected(id || null);
    setBlueprintState(null);
    const target = targets.find((item) => item.id === id);
    if (target) void loadBlueprint(target);
  }

  if (listState === "none") return null;

  return (
    <details className="op-card op-stage-prompt">
      <summary>{stageCopy.promptTitle}</summary>
      <p className="op-muted">{stageCopy.editorIntro}</p>
      {listState === "loading" ? <p role="status" className="op-muted">{targetCopy.section.loading}</p> : null}


      {listState === "unavailable" ? <p className="op-muted">{stageCopy.unavailable} <button type="button" className="op-text" onClick={() => void loadTargets()}>{stageCopy.retry}</button></p> : null}
      {listState === "error" ? <p role="alert" className="op-muted">{stageCopy.error} <button type="button" className="op-text" onClick={() => void loadTargets()}>{stageCopy.retry}</button></p> : null}
      {listState === "ready" && targets.length > 1 ? (
        <label className="op-stage-target">
          <span>{stageCopy.selectTarget}</span>
          <span className="op-muted">{stageCopy.selectTargetHelp}</span>
          <select className="field" value={selectedId} onChange={(event) => chooseTarget(event.target.value)}>
            <option value="">{stageCopy.selectTarget}</option>
            {targets.map((target) => <option key={target.id} value={target.id}>{targetLine(target)}</option>)}
          </select>
        </label>
      ) : null}
      {selectedTarget && blueprintState?.target.id === selectedTarget.id ? (
        blueprintState.kind === "loading" ? <p role="status" className="op-muted">{targetCopy.section.loading}</p>
        : blueprintState.kind === "ready" ? <CandidateStagePlanEditor target={selectedTarget} view={blueprintState.view} compact onSaved={(view) => setBlueprintState({ kind: "ready", target: selectedTarget, view })} onDirtyChange={(dirty) => { setEditorDirty(dirty); onDirtyChange(dirty); }} />
        : blueprintState.kind === "archived" ? <p role="status" className="op-muted">{stageCopy.archived}</p>
        : <p role="alert" className="op-muted">{blueprintState.kind === "unavailable" ? stageCopy.unavailable : stageCopy.error} <button type="button" className="op-text" onClick={() => void loadBlueprint(selectedTarget)}>{stageCopy.retry}</button></p>
      ) : null}
    </details>
  );
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
  const [stageTargetId, setStageTargetId] = useState<string | undefined>();
  const [stageEditorDirty, setStageEditorDirty] = useState(false);
  const onStageTargetSelected = useCallback((targetId: string | null) => setStageTargetId(targetId ?? undefined), []);
  const onStageEditorDirtyChange = useCallback((dirty: boolean) => setStageEditorDirty(dirty), []);

  useEffect(() => { setStageTargetId(undefined); setStageEditorDirty(false); }, [roleProfileId]);

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
    if (stageEditorDirty && !window.confirm(stageCopy.leaveConfirm)) return;
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
      <CandidateStagePrompt roleProfileId={roleProfileId} onTargetSelected={onStageTargetSelected} onDirtyChange={onStageEditorDirtyChange} />
      <div className="op-exit-row">
        <button type="button" className="button-primary op-target" disabled={leaving} onClick={() => void leave(planHref(roleProfileId, stageTargetId))}>
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
