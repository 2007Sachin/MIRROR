/**
 * My Stories presentation. Completeness is decided by the backend
 * (`story_models.story_completeness`); this file only picks words and builds inputs.
 * A story's text always comes from the candidate. Nothing here writes on their behalf.
 */
import type { RoleProfileSummary, Story, StoryInput, StoryPart, StoryPracticeRecord, StoryPracticeSummary, StorySuggestion, StoryVersion } from "@/lib/api";
import { stories as t } from "@/lib/copy";
import { formatShortDay, reviewHref } from "@/lib/dashboard-view";

export const STORY_PART_ORDER: StoryPart[] = [
  "situation",
  "ownership",
  "actions",
  "reasoning",
  "trade_offs",
  "outcome",
  "measurable_result",
  "learning",
  "do_differently",
];

/** The nine story parts, grouped the way an interviewer hears them, for the editor form. */
export const STORY_PART_GROUPS: Array<{ key: string; label: string; parts: StoryPart[] }> = [
  { key: "context", label: t.groups.context, parts: ["situation", "ownership"] },
  { key: "what-you-did", label: t.groups.whatYouDid, parts: ["actions", "reasoning", "trade_offs"] },
  { key: "what-changed", label: t.groups.whatChanged, parts: ["outcome", "measurable_result"] },
  { key: "reflection", label: t.groups.reflection, parts: ["learning", "do_differently"] },
];

export function partLabel(part: StoryPart) {
  return t.parts[part]?.label ?? part;
}

export function partPrompt(part: StoryPart) {
  return t.parts[part]?.prompt ?? "";
}

export function completenessLabel(story: Pick<Story, "completeness">) {
  return t.completeness[story.completeness];
}

export function completenessClass(story: Pick<Story, "completeness">) {
  if (story.completeness === "READY") return "is-ready";
  if (story.completeness === "DEVELOPING") return "is-active";
  return "is-attention";
}

/** The first missing part worth adding next, in the order an interviewer hears them. */
export function nextMissingPart(story: Pick<Story, "missing_parts">): StoryPart | null {
  return STORY_PART_ORDER.find((part) => story.missing_parts.includes(part)) ?? null;
}

/** Why a version exists and when, in the candidate's words. */
export function versionSummary(version: Pick<StoryVersion, "change_reason" | "restored_from_version">, day: string) {
  if (version.change_reason === "RESTORED") return t.history.reason.RESTORED(day, version.restored_from_version);
  if (version.change_reason === "CREATED") return t.history.reason.CREATED(day);
  return t.history.reason.MANUAL_EDIT(day);
}

/**
 * A role's name, told apart from another role with the same name by when it was added.
 * Roles are always found by id; the name is only for reading.
 */
export function roleLabel(roleProfileId: string, roles: RoleProfileSummary[]) {
  const role = roles.find((item) => item.id === roleProfileId);
  if (!role) return t.roles.unknown;
  const sameName = roles.filter((item) => item.target_role.trim().toLowerCase() === role.target_role.trim().toLowerCase());
  return sameName.length > 1 ? t.roles.addedOn(role.target_role, formatShortDay(role.created_at)) : role.target_role;
}

/** "Useful for Product Manager, Business Analyst", or "Useful across roles" when it has none. */
export function usefulFor(story: Pick<Story, "role_profile_ids">, roles: RoleProfileSummary[]) {
  if (!story.role_profile_ids.length) return t.roles.acrossRoles;
  return t.roles.usefulFor(story.role_profile_ids.map((id) => roleLabel(id, roles)).join(", "));
}

/** "Practised 3 times · last 12 Sep", counted by the backend from started practices only. */
export function practiceLine(summary: StoryPracticeSummary | undefined) {
  if (!summary?.practice_count) return t.practice.never;
  const last = summary.last_practiced_at ? ` · ${t.practice.last(formatShortDay(summary.last_practiced_at))}` : "";
  return `${t.practice.times(summary.practice_count)}${last}`;
}

/** Whether a practice was started, and where its review is once there is one. */
export function practiceState(record: Pick<StoryPracticeRecord, "session_id" | "session_status" | "session_started_at">) {
  const reviewed = record.session_status === "COMPLETED" || record.session_status === "ASSESSING";
  return {
    label: record.session_started_at ? t.practice.started : t.practice.notStarted,
    started: Boolean(record.session_started_at),
    reviewHref: reviewed ? reviewHref(record.session_id) : null,
  };
}

/** The practice-start link for one story: a short story practice, the role chosen there. */
export function practiseStoryHref(storyId: string) {
  return `/practice/start?${new URLSearchParams({ mode: "QUICK_DRILL", focus: "story", story: storyId }).toString()}`;
}

/** What a suggestion says, from fixed copy for its type. Never the reviewer's own wording. */
export function suggestionCopy(suggestion: Pick<StorySuggestion, "issue_type">) {
  return t.suggestions.issue[suggestion.issue_type];
}

/** Opens the story editor with this suggestion's context; nothing is saved by following it. */
export function improveHref(suggestion: Pick<StorySuggestion, "id" | "story_id">) {
  return `/stories/${suggestion.story_id}?${new URLSearchParams({ suggestion: suggestion.id }).toString()}`;
}

/** True when the story has changed since the version the suggestion is about. */
export function suggestionIsOlder(suggestion: Pick<StorySuggestion, "practised_version" | "current_version">) {
  return suggestion.current_version > suggestion.practised_version;
}

export type StoryStateKey = "ADD_DETAIL" | "READY" | "PRACTISED" | "SUGGESTED";

/**
 * One deterministic next action per story, from persisted state only — never a quality
 * judgement. An open suggestion always wins (it is the most specific, most actionable
 * thing to do); otherwise completeness, then whether it has ever been practised, decide.
 */
export function storyState(
  story: Pick<Story, "id" | "completeness">,
  info: { openSuggestionId?: string; hasBeenPracticed: boolean },
): { key: StoryStateKey; badge: string; badgeClass: string; action: { label: string; href: string } } {
  if (info.openSuggestionId) {
    return {
      key: "SUGGESTED",
      badge: t.state.suggested,
      badgeClass: "is-attention",
      action: { label: t.suggestions.improve, href: improveHref({ id: info.openSuggestionId, story_id: story.id }) },
    };
  }
  if (story.completeness !== "READY") {
    return {
      key: "ADD_DETAIL",
      badge: t.state.addDetail,
      badgeClass: "is-attention",
      action: { label: t.state.continueStory, href: `/stories/${story.id}` },
    };
  }
  if (!info.hasBeenPracticed) {
    return {
      key: "READY",
      badge: t.state.readyToPractise,
      badgeClass: "is-active",
      action: { label: t.practice.start, href: practiseStoryHref(story.id) },
    };
  }
  return {
    key: "PRACTISED",
    badge: t.state.practised,
    badgeClass: "is-ready",
    action: { label: t.state.practiseAgain, href: practiseStoryHref(story.id) },
  };
}

/** Comma-separated themes as the candidate typed them, cleaned the same way the backend does. */
export function themesFrom(text: string) {
  return text.split(",").map((theme) => theme.trim()).filter(Boolean);
}

function shortTitle(statement: string) {
  const clean = statement.replace(/\s+/g, " ").trim();
  return clean.length <= 80 ? clean : `${clean.slice(0, 79).trimEnd()}…`;
}

/**
 * A story made of the candidate's own pressure-test answers. Each answer goes into
 * the part its question was asking about; the resume statement is kept as the source,
 * never copied into the story as if it were an answer.
 */
export function storyFromAnswers({
  statement,
  claimId,
  roleProfileId,
  theme,
  answers,
}: {
  statement: string;
  claimId: string;
  roleProfileId: string | null;
  theme: string | null;
  answers: Array<{ part: StoryPart; answer: string }>;
}): StoryInput {
  const parts: Partial<Record<StoryPart, string>> = {};
  for (const { part, answer } of answers) {
    parts[part] = parts[part] ? `${parts[part]}\n\n${answer}` : answer;
  }
  return {
    title: shortTitle(statement),
    themes: theme ? [theme] : [],
    role_profile_id: roleProfileId,
    source_claim_id: claimId,
    source_text: statement,
    origin: "PRESSURE_TEST",
    ...parts,
  };
}
