import type { CandidateStage, CandidateStageKind, CandidateStagePlan, CandidateStagePlanSave, CandidateStageState } from "@/lib/api-targets";

export type StageDraft = { state: CandidateStageState; orderKnown: boolean; stages: CandidateStage[]; notes: Record<string, string> };

export function cloneStageDraft(plan: CandidateStagePlan | null): StageDraft {
  return { state: plan?.candidate_stage_state ?? "NOT_ASKED", orderKnown: plan?.candidate_stage_order_known ?? false, stages: (plan?.candidate_stages ?? []).map((s) => ({ ...s })), notes: { ...(plan?.notes ?? {}) } };
}

export function newStage(kind: CandidateStageKind = "OTHER"): CandidateStage {
  return { stage_id: globalThis.crypto.randomUUID(), kind, custom_label: kind === "OTHER" ? "" : null, certainty: "UNCERTAIN", sequence: null };
}

export function addStage(draft: StageDraft, stage = newStage()): StageDraft {
  return draft.stages.length >= 12 ? draft : { ...draft, state: "KNOWN", stages: [...draft.stages, { ...stage }], notes: { ...draft.notes } };
}

export function updateStage(draft: StageDraft, stageId: string, changes: Partial<CandidateStage>): StageDraft {
  return { ...draft, stages: draft.stages.map((s) => s.stage_id === stageId ? { ...s, ...changes } : s), notes: { ...draft.notes } };
}

export function removeStage(draft: StageDraft, stageId: string): StageDraft {
  const notes = { ...draft.notes }; delete notes[stageId];
  const stages = draft.stages.filter((s) => s.stage_id !== stageId);
  return { ...draft, stages, notes, state: stages.length ? "KNOWN" : draft.state };
}

export function setStageNote(draft: StageDraft, stageId: string, note: string): StageDraft {
  const notes = { ...draft.notes };
  if (note) notes[stageId] = note.slice(0, 500); else delete notes[stageId];
  return { ...draft, notes };
}

export function moveStage(draft: StageDraft, stageId: string, toIndex: number): StageDraft {
  if (!draft.orderKnown) return draft;
  const from = draft.stages.findIndex((s) => s.stage_id === stageId);
  if (from < 0 || toIndex < 0 || toIndex >= draft.stages.length) return draft;
  const stages = draft.stages.slice(); const [item] = stages.splice(from, 1); stages.splice(toIndex, 0, item);
  return { ...draft, stages };
}

export function setStageState(draft: StageDraft, state: CandidateStageState): StageDraft {
  return state === "KNOWN" ? { ...draft, state } : { ...draft, state, orderKnown: false, stages: [], notes: {} };
}

export function validateStageDraft(draft: Pick<StageDraft, "state" | "stages">): { valid: boolean; reason?: "stages_required" | "too_many_stages" | "custom_label_required" } {
  if (draft.state === "KNOWN" && draft.stages.length === 0) return { valid: false, reason: "stages_required" };
  if (draft.stages.length > 12) return { valid: false, reason: "too_many_stages" };
  if (draft.stages.some((s) => s.kind === "OTHER" && (!s.custom_label?.trim() || s.custom_label.trim().length > 80))) return { valid: false, reason: "custom_label_required" };
  return { valid: true };
}

export function toStageSavePayload(draft: StageDraft, expectedBlueprintVersion: number): CandidateStagePlanSave {
  const stageIds = new Set(draft.stages.map((stage) => stage.stage_id));
  const notes = Object.fromEntries(Object.entries(draft.notes)
    .filter(([stageId, note]) => stageIds.has(stageId) && Boolean(note.trim()))
    .map(([stageId, note]) => [stageId, note.trim()]));
  return {
    expected_blueprint_version: expectedBlueprintVersion,
    state: draft.state,
    order_known: draft.state === "KNOWN" && draft.orderKnown,
    stages: draft.state === "KNOWN" ? draft.stages.map((stage, index) => ({
      ...stage,
      custom_label: stage.kind === "OTHER" ? stage.custom_label?.trim() ?? "" : null,
      sequence: draft.orderKnown ? index + 1 : null,
    })) : [],
    notes: draft.state === "KNOWN" ? notes : {},
  };
}
