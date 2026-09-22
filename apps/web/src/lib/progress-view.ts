/**
 * Progress: the candidate-facing reading of `GET /api/v1/progress`.
 *
 * The backend decides what is comparable and what direction an area moved in. This
 * file only turns those decisions into the words people see, and refuses to show a
 * direction the backend did not give it.
 */
import type { ProgressDimension, ProgressResponse } from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { developmentState, type DevelopmentState } from "@/lib/dashboard-view";

/** The same four areas as the Home page, in the same words. */
export const AREA_LABELS: Record<string, string> = {
  role_understanding: "Connecting your experience to the role",
  examples: "Using real examples",
  depth: "Explaining your decisions",
  impact: "Showing your impact",
};

export const AREA_KEYS = Object.keys(AREA_LABELS);

/** The focus someone would choose to work on each area. */
const AREA_FOCUS: Record<string, string> = {
  role_understanding: "role",
  examples: "story",
  depth: "decisions",
  impact: "impact",
};

export type ProgressArea = {
  key: string;
  label: string;
  state: DevelopmentState;
  note: string;
  direction: string | null;
  directionLabel: string | null;
  href: string;
  focus: string;
  excerpts: Array<{ quote: string; note: string }>;
};

export function areaLabel(key: string) {
  return AREA_LABELS[key] ?? key;
}

export function areaFocus(key: string) {
  return AREA_FOCUS[key] ?? "full";
}

export function progressAreas(dimensions: ProgressDimension[]): ProgressArea[] {
  return dimensions.map((dimension) => {
    const state = developmentState(dimension.state);
    return {
      key: dimension.key,
      label: areaLabel(dimension.key),
      state,
      note: dimension.note,
      direction: dimension.direction,
      // A direction is only ever shown when the backend found two practices to compare.
      directionLabel: dimension.direction ? t.directions[dimension.direction] ?? null : null,
      href: `/progress/${dimension.key}`,
      focus: areaFocus(dimension.key),
      excerpts: state === "Not explored yet" ? [] : dimension.excerpts,
    };
  });
}

export function findArea(result: ProgressResponse | null, key: string): ProgressArea | null {
  if (!result) return null;
  return progressAreas(result.dimensions).find((area) => area.key === key) ?? null;
}

/** Up to three things to work on next, taken from the newest practice. */
export function currentPriorities(result: ProgressResponse | null, limit = 3) {
  return (result?.practices[0]?.improvements ?? []).slice(0, limit);
}

export type ProgressState = "EMPTY" | "ONE_PRACTICE" | "COMPARABLE";

export function progressState(result: ProgressResponse | null): ProgressState {
  if (!result || result.practices.length === 0) return "EMPTY";
  return result.comparable_count >= 2 ? "COMPARABLE" : "ONE_PRACTICE";
}

export function stateClass(state: DevelopmentState) {
  return `is-${state.toLocaleLowerCase().replaceAll(" ", "-")}`;
}

export function directionClass(direction: string | null) {
  if (direction === "IMPROVING") return "is-improving";
  if (direction === "NEEDS_MORE_PRACTICE") return "is-needs-more";
  return "is-steady";
}
