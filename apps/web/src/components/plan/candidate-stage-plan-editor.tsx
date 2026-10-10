"use client";

import { useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api";
import { getBlueprint, saveCandidateStagePlan, type BlueprintView, type CandidateStageKind, type TargetView } from "@/lib/api-targets";
import { targetCopy } from "@/lib/copy-targets";
import { addStage, cloneStageDraft, moveStage, newStage, removeStage, setStageNote, setStageState, toStageSavePayload, updateStage, validateStageDraft, type StageDraft } from "@/lib/candidate-stage-editor-state";

export function CandidateStagePlanEditor({ target, view, onSaved, onDirtyChange, compact = false }: { target: TargetView; view: BlueprintView; onSaved: (view: BlueprintView) => void; onDirtyChange?: (dirty: boolean) => void; compact?: boolean }) {
  const copy = targetCopy.section.candidateStages;
  const initial = useMemo(() => cloneStageDraft(view.candidate_stage_plan), [view.candidate_stage_plan]);
  const [draft, setDraft] = useState<StageDraft>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [stale, setStale] = useState(false);
  const [archived, setArchived] = useState(target.status !== "ACTIVE");
  const [saved, setSaved] = useState(false);
  const [reloadBusy, setReloadBusy] = useState(false);
  const [baseline, setBaseline] = useState(JSON.stringify(initial));

  const dirty = JSON.stringify(draft) !== baseline;
  const validation = validateStageDraft(draft);
  const kinds = Object.keys(copy.stageKinds) as CandidateStageKind[];

  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => { const handler = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } }; window.addEventListener("beforeunload", handler); return () => window.removeEventListener("beforeunload", handler); }, [dirty]);
  useEffect(() => {
    const navigation = (window as unknown as { navigation?: EventTarget }).navigation;
    if (navigation) {
      const guard = (event: Event) => {
        const navigationEvent = event as Event & { canIntercept?: boolean; navigationType?: string };
        if (dirty && navigationEvent.navigationType === "traverse" && navigationEvent.canIntercept
          && !window.confirm(copy.leaveConfirm)) event.preventDefault();
      };
      navigation?.addEventListener("navigate", guard, true);
      return () => navigation?.removeEventListener("navigate", guard, true);
    }
    const guard = (event: PopStateEvent) => {
      if (!dirty || window.confirm(copy.leaveConfirm)) return;
      event.stopImmediatePropagation();
      window.history.forward();
    };
    window.addEventListener("popstate", guard, true);
    return () => window.removeEventListener("popstate", guard, true);
  }, [copy.leaveConfirm, dirty]);
  useEffect(() => {
    const guard = (event: MouseEvent) => {
      if (!dirty || saving || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest<HTMLAnchorElement>("a[href]");
      if (!anchor || anchor.target === "_blank" || new URL(anchor.href, window.location.href).origin !== window.location.origin) return;
      if (!window.confirm(copy.leaveConfirm)) { event.preventDefault(); event.stopPropagation(); }
    };
    document.addEventListener("click", guard, true);
    return () => document.removeEventListener("click", guard, true);
  }, [copy.leaveConfirm, dirty, saving]);
  useEffect(() => { if (dirty) setSaved(false); }, [dirty]);
  useEffect(() => { setArchived(target.status !== "ACTIVE"); }, [target.status]);

  async function save() {
    if (!validation.valid || saving || stale || archived || !view.blueprint || view.blueprint.version !== view.blueprint.latest_version || target.status !== "ACTIVE") return;
    setSaving(true); setError(""); setSaved(false);
    try {
      const result = await saveCandidateStagePlan(target.id, toStageSavePayload(draft, view.blueprint.version));
      if (!result.candidate_stage_plan || result.target?.id !== target.id || !result.blueprint) throw new Error("Stage plan response was incomplete.");
      const next = cloneStageDraft(result.candidate_stage_plan);
      setDraft(next); setBaseline(JSON.stringify(next)); setSaved(true); onSaved(result);
    }
    catch (reason) {
      if (reason instanceof ApiError && reason.code === "STAGE_PLAN_STALE") { setStale(true); setError(copy.stale); }
      else if (reason instanceof ApiError && reason.code === "TARGET_ARCHIVED") { setArchived(true); setError(copy.archived); }
      else setError(copy.saveError);
    } finally { setSaving(false); }
  }

  async function loadLatest() {
    if (!window.confirm(copy.reloadConfirm)) return;
    setReloadBusy(true); setError("");
    try {
      const latest = await getBlueprint(target.id);
      if (latest.availability !== "AVAILABLE") { setError(copy.error); return; }
      if (!latest.target || latest.target.id !== target.id || latest.target.status !== "ACTIVE") {
        setArchived(true); setError(copy.archived); return;
      }
      const next = cloneStageDraft(latest.candidate_stage_plan);
      setDraft(next); setBaseline(JSON.stringify(next)); setStale(false); setArchived(false); onSaved(latest);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "TARGET_ARCHIVED") { setArchived(true); setError(copy.archived); }
      else setError(copy.error);
    } finally { setReloadBusy(false); }
  }

  const locked = archived || target.status !== "ACTIVE" || stale || saving || !view.blueprint || view.blueprint.version !== view.blueprint.latest_version;
  const set = (fn: (old: StageDraft) => StageDraft) => setDraft((old) => fn(old));
  return <section className={`pl-stage-editor${compact ? " pl-stage-editor--compact" : ""}`} aria-label={compact ? copy.overviewTitle : undefined} aria-labelledby={compact ? undefined : "pl-stage-editor-title"}>
    {!compact && <h2 id="pl-stage-editor-title">{copy.promptTitle}</h2>}{!compact && <p>{copy.editorIntro}</p>}<p>{copy.privacy}</p>
    <fieldset disabled={locked}><legend>{copy.stateLabel}</legend>
      {([ ["NOT_ASKED", copy.notAsked], ["NOT_YET", copy.notYet], ["KNOWN", copy.known] ] as const).map(([value, label]) => <label key={value}><input type="radio" name="candidate-stage-state" checked={draft.state === value} onChange={() => set((d) => setStageState(d, value))} />{label}</label>)}
      {draft.state === "KNOWN" && <><label><input type="checkbox" checked={draft.orderKnown} onChange={(e) => set((d) => ({ ...d, orderKnown: e.target.checked }))} />{copy.orderKnown}</label>
        <ul>{draft.stages.map((stage, i) => <li key={stage.stage_id} className="pl-stage-editor__stage"><h3>{copy.stageLabel}{draft.orderKnown ? ` ${i + 1}` : ""}</h3>
          <label>{copy.kindLabel}<select value={stage.kind} onChange={(e) => { const kind = e.target.value as CandidateStageKind; set((d) => updateStage(d, stage.stage_id, { kind, custom_label: kind === "OTHER" ? stage.custom_label ?? "" : null })); }}>
            {kinds.map((kind) => <option key={kind} value={kind}>{copy.stageKinds[kind]}</option>)}</select></label>
          {stage.kind === "OTHER" && <label>{copy.customLabel}<input value={stage.custom_label ?? ""} maxLength={80} onChange={(e) => set((d) => updateStage(d, stage.stage_id, { custom_label: e.target.value }))} /></label>}
          <label>{copy.certaintyLabel}<select value={stage.certainty} onChange={(e) => set((d) => updateStage(d, stage.stage_id, { certainty: e.target.value as "SURE" | "UNCERTAIN" }))}><option value="SURE">{copy.certain}</option><option value="UNCERTAIN">{copy.uncertain}</option></select></label>
          <label>{copy.noteLabel}<textarea value={draft.notes[stage.stage_id] ?? ""} maxLength={500} aria-describedby={`pl-stage-note-help-${stage.stage_id}`} onChange={(e) => set((d) => setStageNote(d, stage.stage_id, e.target.value))} /></label><small id={`pl-stage-note-help-${stage.stage_id}`}>{copy.noteHelp}</small>
          {draft.orderKnown && <span><button type="button" aria-label={copy.moveUp} disabled={i === 0} onClick={() => set((d) => moveStage(d, stage.stage_id, i - 1))}>{copy.moveUp}</button><button type="button" aria-label={copy.moveDown} disabled={i === draft.stages.length - 1} onClick={() => set((d) => moveStage(d, stage.stage_id, i + 1))}>{copy.moveDown}</button></span>}
          <button type="button" onClick={() => set((d) => removeStage(d, stage.stage_id))}>{copy.remove}</button>
        </li>)}</ul>
        <button type="button" disabled={draft.stages.length >= 12} onClick={() => set((d) => addStage(d, newStage("OTHER")))}>{copy.addStage}</button>{draft.stages.length >= 12 && <p>{copy.atLimit}</p>}
      </>}
    </fieldset>
    {archived && !error && <p role="status">{copy.archived}</p>}{error && <p role="alert">{error}</p>}{saved && <p role="status">{copy.saved}</p>}
    {!validation.valid && draft.state === "KNOWN" && <p role="alert">{copy.invalid}</p>}
    {stale && <button type="button" disabled={reloadBusy} onClick={loadLatest}>{copy.reloadLatest}</button>}
    <button type="button" disabled={locked || !dirty || !validation.valid || !view.blueprint} onClick={save}>{saving ? copy.saving : copy.save}</button>
  </section>;
}
