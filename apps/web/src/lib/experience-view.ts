/**
 * My Experience: what Mirror draws on, grouped the way someone thinks about it.
 *
 * Work, projects and achievements are read out of the resume by the resume agent,
 * so they are shown as belonging to the resume rather than as separate records that
 * could be edited on their own. Files people add themselves stay editable.
 */
import type { EvidenceDetail, MirrorDocument, ResumeAnalysis } from "@/lib/api";
import { evidenceCategory } from "@/components/workspace/evidence-types";
import { experience as t } from "@/lib/copy";
import { relativeDay } from "@/lib/dashboard-view";

export type ResumeOutput = NonNullable<ResumeAnalysis["output"]>;
export type WorkEntry = ResumeOutput["work_experience"][number];
export type ProjectEntry = ResumeOutput["projects"][number];

export type AchievementEntry = { title: string; detail: string | null };

export type ExperienceGroups = {
  resumes: EvidenceDetail[];
  projects: EvidenceDetail[];
  achievements: EvidenceDetail[];
  other: EvidenceDetail[];
};

/** Current items only, split into the four sections the page shows. */
export function groupExperience(items: EvidenceDetail[]): ExperienceGroups {
  const current = items.filter((item) => !item.document.archived_at);
  const groups: ExperienceGroups = { resumes: [], projects: [], achievements: [], other: [] };
  for (const item of current) {
    const category = evidenceCategory(item.document);
    if (category === "ROLE_BRIEF") continue; // a role brief belongs to a role, not to a person
    if (category === "RESUME") groups.resumes.push(item);
    else if (category === "PROJECT" || category === "CASE_STUDY" || category === "WORK_SAMPLE") groups.projects.push(item);
    else if (category === "ACHIEVEMENT" || category === "CERTIFICATE") groups.achievements.push(item);
    else groups.other.push(item);
  }
  return groups;
}

export function newestFirst(items: EvidenceDetail[]) {
  return [...items].sort(
    (left, right) =>
      new Date(right.document.updated_at || right.document.created_at).getTime()
      - new Date(left.document.updated_at || left.document.created_at).getTime(),
  );
}

export function addedOn(document: MirrorDocument) {
  return relativeDay(document.updated_at || document.created_at);
}

/** Achievements come back as loosely shaped records, so read them defensively. */
export function readAchievements(output: ResumeOutput | null): AchievementEntry[] {
  if (!output) return [];
  const entries: AchievementEntry[] = [];
  for (const raw of output.achievements) {
    if (typeof raw === "string") {
      if (raw.trim()) entries.push({ title: raw.trim(), detail: null });
      continue;
    }
    if (!raw || typeof raw !== "object") continue;
    const record = raw as Record<string, unknown>;
    const title = [record.title, record.achievement, record.name, record.description]
      .find((value): value is string => typeof value === "string" && value.trim().length > 0);
    if (!title) continue;
    const detail = [record.organization, record.context, record.source_reference]
      .find((value): value is string => typeof value === "string" && value.trim().length > 0);
    entries.push({ title: title.trim(), detail: detail?.trim() ?? null });
  }
  return entries;
}

export type ExperienceState = "EMPTY" | "READING" | "UNREADABLE" | "READY";

export function experienceState(groups: ExperienceGroups, analysis: ResumeAnalysis | null): ExperienceState {
  if (!groups.resumes.length && !groups.projects.length && !groups.achievements.length && !groups.other.length) {
    return "EMPTY";
  }
  if (!groups.resumes.length) return "READY";
  if (analysis === null || analysis.status === "PROCESSING") return "READING";
  if (analysis.status === "FAILED") return "UNREADABLE";
  return "READY";
}

/**
 * One honest sentence, and only where something is genuinely missing. No counts and
 * no completeness number: neither would tell anyone what to do next.
 */
export function experienceGuidance(
  groups: ExperienceGroups,
  output: ResumeOutput | null,
  state: ExperienceState,
): string | null {
  if (state === "EMPTY") return null; // the empty state already says it
  if (!groups.resumes.length) return t.addResume;
  if (state === "READING") return t.readingResume;
  if (state === "UNREADABLE") return t.resumeUnread;
  const projects = (output?.projects.length ?? 0) + groups.projects.length;
  if (projects === 0) return t.addProject;
  return t.enough;
}
