/**
 * Interview Map presentation. The map itself is computed by the backend
 * (`GET /api/v1/roles/{id}/interview-map`); this file only chooses words and links.
 */
import type { InterviewMap, MapAreaAction, MapCoverage } from "@/lib/api";
import { interviewMap as t } from "@/lib/copy";
import { startPracticeHref } from "@/lib/practice-view";

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
    PRACTICE: () => startPracticeHref(map.target_role, area.focus),
    ADD_EXPERIENCE: () => "/experience",
  };
  return actions[area.action]();
}

export function areaActionLabel(action: MapAreaAction) {
  return t.actions[action];
}

/** A notice about the candidate's side of the map, when it is not complete. */
export function experienceNotice(map: InterviewMap): string | null {
  if (map.experience_state === "READING") return t.states.reading;
  if (map.experience_state === "UNREADABLE") return t.states.unreadableResume;
  return null;
}
