/**
 * Interview Map presentation. The map itself is computed by the backend
 * (`GET /api/v1/roles/{id}/interview-map`); this file only chooses words and links.
 */
import type { InterviewMap, MapAreaAction, MapCoverage, PracticeRecommendation } from "@/lib/api";
import { interviewMap as t } from "@/lib/copy";
import { focusFor, modeCopy, startPracticeHref } from "@/lib/practice-view";
import { practiseStoryHref } from "@/lib/story-view";

type Theme = InterviewMap["themes"][number];
type Area = InterviewMap["preparation_areas"][number];

export function coverageLabel(coverage: MapCoverage) {
  return t.coverage[coverage] ?? t.coverage.MISSING;
}

export function coverageClass(coverage: MapCoverage) {
  if (coverage === "PREPARED") return "is-ready";
  if (coverage === "EXPERIENCE") return "is-active";
  if (coverage === "MENTIONED") return "is-attention";
  return "is-muted";
}

/** Themes the candidate already has something real for, strongest first. */
export function mapStrengths(map: InterviewMap, limit = 4): Theme[] {
  const rank: Record<MapCoverage, number> = { PREPARED: 0, EXPERIENCE: 1, MENTIONED: 2, MISSING: 3 };
  return map.themes
    .filter((theme) => theme.coverage === "PREPARED" || theme.coverage === "EXPERIENCE")
    .sort((left, right) => rank[left.coverage] - rank[right.coverage])
    .slice(0, limit);
}

export function themeName(map: InterviewMap, key: string | null) {
  return map.themes.find((theme) => theme.key === key)?.name ?? null;
}

export function findStoryHref(roleProfileId: string, theme: string | null) {
  const params = new URLSearchParams({ guided: "1", role: roleProfileId });
  if (theme) params.set("theme", theme);
  return `/stories/new?${params.toString()}`;
}

export function pressureTestHref(roleProfileId: string) {
  return `/roles/${roleProfileId}/pressure-test`;
}

/** The one place a preparation area turns into a link. */
export function areaHref(map: InterviewMap, area: Area): string {
  const actions: Record<MapAreaAction, () => string> = {
    FIND_STORY: () => findStoryHref(map.role_profile_id, themeName(map, area.theme_key) ?? area.title),
    PRESSURE_TEST: () => pressureTestHref(map.role_profile_id),
    // The exact role practised is carried through, not re-derived from the account's
    // current role: a practice started from one role's map must stay on that role,
    // even if it differs from the role the account currently points at elsewhere.
    PRACTICE: () => startPracticeHref(map.target_role, area.focus, map.role_profile_id),
    ADD_EXPERIENCE: () => "/experience",
  };
  return actions[area.action]();
}

export function areaActionLabel(action: MapAreaAction) {
  return t.actions[action];
}

/** A theme's top match, if it is a story the candidate can practise directly. */
export function storyToPractise(theme: Theme): string | null {
  const first = theme.matches[0];
  return first && first.kind === "STORY" && first.story_id ? first.story_id : null;
}

/** Where the map's own "Recommended for you" banner sends the candidate. Reuses the
 * generic practice entry so the exact role, mode, focus and theme all survive the trip. */
export function recommendationHref(recommendation: PracticeRecommendation): string {
  return startPracticeHref(recommendation.target_role, {
    mode: recommendation.mode,
    focus: recommendation.focus,
    theme: recommendation.theme,
  }, recommendation.role_profile_id);
}

/** What to call the recommendation: its theme, its focus area, or its mode. */
export function recommendationTitle(recommendation: PracticeRecommendation): string {
  return recommendation.theme ?? focusFor(recommendation.focus)?.title ?? modeCopy(recommendation.mode).title;
}

/** A notice about the candidate's side of the map, when it is not complete. */
export function experienceNotice(map: InterviewMap): string | null {
  if (map.experience_state === "READING") return t.states.reading;
  if (map.experience_state === "UNREADABLE") return t.states.unreadableResume;
  return null;
}
