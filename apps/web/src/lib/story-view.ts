/**
 * My Stories presentation. Completeness is decided by the backend
 * (`story_models.story_completeness`); this file only picks words and builds inputs.
 * A story's text always comes from the candidate. Nothing here writes on their behalf.
 */
import type { Story, StoryInput, StoryPart } from "@/lib/api";
import { stories as t } from "@/lib/copy";

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
