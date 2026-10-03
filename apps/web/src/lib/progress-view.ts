/**
 * Progress: the words and links for the role-based Progress pages.
 *
 * The backend (`GET /api/v1/progress/roles...`) decides every state, trend and count.
 * This file only turns those decisions into the words people see and the addresses
 * they go to. It never computes a trend, a state or a number of its own.
 */
import type {
  DevState,
  PracticeFocusKey,
  ProgressAnswer,
  ProgressAnswerSignal,
  ProgressAnswerState,
  ProgressDimension,
  ProgressInsight,
  ProgressPracticeItem,
  ProgressRoleTile,
  RoleProgress,
} from "@/lib/api";
import { progress as t } from "@/lib/copy";
import { formatDay, formatShortDay, relativeDay } from "@/lib/dashboard-view";
import { practiceLabel, startPracticeHref } from "@/lib/practice-view";

/** The same four areas as the Home page, in the same words. */
export const AREA_LABELS: Record<string, string> = {
  role_understanding: "Connecting your experience to the role",
  examples: "Using real examples",
  depth: "Explaining your decisions",
  impact: "Showing your impact",
};

export const AREA_KEYS = Object.keys(AREA_LABELS);

export function areaLabel(key: string) {
  return AREA_LABELS[key] ?? key;
}

/** Used by the review page's development states; unchanged. */
export function stateClass(state: string) {
  return `is-${state.toLocaleLowerCase().replaceAll(" ", "-")}`;
}

// ------------------------------------------------------------------- addresses

export type RoleTab = "overview" | "answers" | "history" | "connection";
export const ROLE_TABS: RoleTab[] = ["overview", "answers", "history", "connection"];

export function isRoleTab(value: string | null | undefined): value is RoleTab {
  return ROLE_TABS.includes(value as RoleTab);
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Routes only ask the API about ids that look like ids; anything else is simply not found. */
export function isUuid(value: string) {
  return UUID.test(value);
}

export function roleProgressHref(roleProfileId: string, tab?: RoleTab) {
  return `/progress/${roleProfileId}${tab && tab !== "overview" ? `?tab=${tab}` : ""}`;
}

export function dimensionHref(roleProfileId: string, key: string) {
  return `/progress/${roleProfileId}/${key}`;
}

export function dimensionAnswersHref(roleProfileId: string, key: string, sessionId?: string) {
  const base = `/progress/${roleProfileId}/${key}/answers`;
  return sessionId ? `${base}?practice=${sessionId}` : base;
}

export function answerHref(roleProfileId: string, sessionId: string, turnId: string, dimension?: string | null) {
  const base = `/progress/${roleProfileId}/answers/${sessionId}/${turnId}`;
  return dimension ? `${base}?dimension=${encodeURIComponent(dimension)}` : base;
}

/** A focused practice on one area, for exactly this role. */
export function focusedPracticeHref(role: string, roleProfileId: string, dimension: ProgressDimension) {
  return startPracticeHref(
    role,
    { mode: "FOCUSED_PRACTICE", focus: dimension.practice_focus as PracticeFocusKey, theme: null },
    roleProfileId,
  );
}

export function startRoleHref(role: string, roleProfileId: string) {
  return startPracticeHref(role, undefined, roleProfileId);
}

// ------------------------------------------------------------------- words

/** "2 days ago" for the last couple of weeks, a date after that. */
export function whenLabel(value: string | null) {
  if (!value) return "";
  const days = Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000);
  return days <= 14 ? relativeDay(value) ?? "" : formatShortDay(value);
}

export function practiceTitle(item: Pick<ProgressPracticeItem, "practice_mode" | "practice_focus" | "practice_theme">) {
  return practiceLabel(item.practice_mode, item.practice_focus, item.practice_theme);
}

export function stateLabel(state: DevState) {
  return t.timeline.states[state];
}

export function dimensionFor(progress: RoleProgress | null, key: string): ProgressDimension | null {
  return progress?.dimensions.find((dimension) => dimension.key === key) ?? null;
}

// ------------------------------------------------------------------- the hub

export type TileLine = { tone: "positive" | "attention"; heading: string; area: string };

export type TileView = {
  meta: string;
  stage: ProgressRoleTile["stage"];
  lines: TileLine[];
};

export function tileView(tile: ProgressRoleTile): TileView {
  const lines: TileLine[] = [];
  if (tile.positive) {
    lines.push({ tone: "positive", heading: t.hub.positive[tile.positive.kind], area: areaLabel(tile.positive.dimension) });
  }
  if (tile.attention) {
    lines.push({ tone: "attention", heading: t.hub.attention[tile.attention.kind], area: areaLabel(tile.attention.dimension) });
  }
  const last = tile.last_practised_at ? t.hub.lastPractised(whenLabel(tile.last_practised_at)) : "";
  return {
    meta: tile.practice_count ? [t.hub.practices(tile.practice_count), last].filter(Boolean).join(" · ") : t.hub.none,
    stage: tile.stage,
    lines,
  };
}

export function roleMeta(progress: RoleProgress) {
  if (!progress.practice_count) return t.hub.none;
  const last = progress.last_practised_at ? `Last practised ${formatShortDay(progress.last_practised_at)}` : "";
  return [t.hub.practices(progress.practice_count), last].filter(Boolean).join(" · ");
}

// ------------------------------------------------------------------- overview

export type InsightView = { key: string; dimension: string; trend: ProgressInsight["trend"]; title: string; body: string };

export function insightViews(insights: ProgressInsight[]): InsightView[] {
  return insights.map((insight) => {
    const copy = t.insights[insight.dimension]?.[insight.trend];
    return {
      key: `${insight.dimension}-${insight.trend}`,
      dimension: insight.dimension,
      trend: insight.trend,
      title: copy?.title ?? areaLabel(insight.dimension),
      body: copy?.body ?? t.trend[insight.trend],
    };
  });
}

/** Names the earlier practice only when every insight was measured against the same one. */
export function comparedWith(insights: ProgressInsight[]) {
  const days = new Set(insights.map((insight) => formatDay(insight.compared_with)));
  return days.size === 1 ? t.overview.sinceOn([...days][0]) : t.overview.sinceEarlier;
}

/** What one practice showed, for the baseline: only areas with something to say. */
export function baselineSeen(progress: RoleProgress) {
  return progress.dimensions
    .filter((dimension) => dimension.state !== "NOT_EXPLORED")
    .map((dimension) => ({
      key: dimension.key,
      label: areaLabel(dimension.key),
      state: dimension.state,
      note: dimension.note,
    }));
}

// ------------------------------------------------------------------- timeline and pattern

export function markerLabel(cell: ProgressDimension["cells"][number], key: string) {
  return t.timeline.marker(cell.number, formatDay(cell.completed_at), areaLabel(key), stateLabel(cell.state));
}

export function patternLine(dimension: ProgressDimension) {
  if (dimension.trend && dimension.current) return t.dimension.pattern[dimension.trend];
  return t.dimension.byState[dimension.state];
}

export function notExploredCount(dimension: ProgressDimension) {
  return dimension.cells.filter((cell) => cell.state === "NOT_EXPLORED").length;
}

export function strengthenSteps(key: string) {
  return (t.meanings[key]?.steps ?? []).slice(0, 3);
}

// ------------------------------------------------------------------- answers

export type AnswerFilter = "ALL" | "STRONG" | "NEEDS_PRACTICE";
export const ANSWER_FILTERS: AnswerFilter[] = ["ALL", "STRONG", "NEEDS_PRACTICE"];

export type AnswerRow = {
  answer: ProgressAnswer;
  /** The signal for the requested area, or the most useful one when listing every area. */
  signal: ProgressAnswerSignal;
};

const ORDER: Record<ProgressAnswerState, number> = { NEEDS_PRACTICE: 0, PRESENT: 1, STRONG: 2 };

/** Rows for one area, or for every area (one row per answer) when none is given. */
export function answerRows(answers: ProgressAnswer[], dimension: string | null, filter: AnswerFilter = "ALL"): AnswerRow[] {
  const rows: AnswerRow[] = [];
  for (const answer of answers) {
    const signal = dimension
      ? answer.signals.find((item) => item.dimension === dimension)
      : [...answer.signals].sort((a, b) => ORDER[a.state] - ORDER[b.state])[0];
    if (!signal) continue;
    if (filter !== "ALL" && signal.state !== filter) continue;
    rows.push({ answer, signal });
  }
  return rows;
}

export function answerKey(answer: { session_id: string; answer_turn_id: string }) {
  return `${answer.session_id}:${answer.answer_turn_id}`;
}
