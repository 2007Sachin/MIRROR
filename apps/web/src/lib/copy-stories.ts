/** Words for guided stories, the story library and Dig Deeper feedback (see docs/copy-guide.md). */
import type { StoryPart } from "@/lib/api";

export type GuidedStep = {
  key: string;
  name: string;
  part: StoryPart;
  question: (theme: string) => string;
  hint: string;
  /** An optional second detail on the same step, never a second question. */
  extra?: { part: StoryPart; label: string };
};

export const storiesGuided = {
  title: "Build a story",
  titleFor: (theme: string) => `A story about ${theme.toLowerCase()}`,
  intro: "One question at a time. Only what you write goes into the story, and you can save and stop whenever you like.",
  progress: (step: number, total: number) => `${step} of ${total}`,
  nameLabel: "Story name",
  nameHint: "Optional. A short name you'll recognise later.",
  untitled: "My story",
  why: {
    roleTheme: (role: string, theme: string) =>
      `Interviewers for ${role} often ask about ${theme.toLowerCase()}. One real example you can tell clearly covers it.`,
    theme: (theme: string) =>
      `Interviewers often ask about ${theme.toLowerCase()}. One real example you can tell clearly covers it.`,
    experience: "You approved this in My experience, so it is a real example you can speak about with confidence.",
    notApproved: "That example isn't approved yet, so this story starts blank. You can approve it in My experience.",
  },
  basedOn: "Based on",
  steps: [
    {
      key: "context",
      name: "Context",
      part: "situation",
      question: (theme) =>
        theme ? `Think of a time ${theme.toLowerCase()} really mattered. Where were you, and what was going on?` : "Where were you, and what was going on?",
      hint: "Nothing comes to mind? Try a different project, a class, or work outside a job.",
    },
    {
      key: "challenge",
      name: "Challenge",
      part: "ownership",
      question: () => "What was the hard part, and which part of it was yours to handle?",
      hint: "Say what you owned, as opposed to the team.",
    },
    {
      key: "action",
      name: "Action",
      part: "actions",
      question: () => "What did you do? Walk through the steps.",
      hint: "Use “I” for your own steps.",
      extra: { part: "reasoning", label: "Why that way rather than another? (optional)" },
    },
    {
      key: "result",
      name: "Result",
      part: "outcome",
      question: () => "What happened in the end?",
      hint: "What was different afterwards?",
      extra: { part: "measurable_result", label: "Anything you can measure? A rough size is fine, if you say so. (optional)" },
    },
    {
      key: "learning",
      name: "Learning",
      part: "learning",
      question: () => "What did you learn that you would take into your next role?",
      hint: "One honest sentence is enough.",
    },
  ] satisfies readonly GuidedStep[],
  back: "Back",
  next: "Next",
  saveForLater: "Save for later",
  finish: "Save story",
  saving: "Saving…",
  saved: "Saved. You can return to this whenever you are ready.",
  backToStories: "Back to My stories",
  errors: {
    save: "We couldn't save your story just now. Your writing is still here.",
    retry: "Try again",
  },
} as const;

export const storyLibrary = {
  add: "Add a story",
  readiness: {
    READY: "Ready to tell",
    DEVELOPING: "Needs more detail",
    STARTED: "Just started",
  } as Record<string, string>,
  purpose: (themes: string) => `For ${themes}`,
  noPurpose: "Not linked to a role need yet",
  version: (n: number) => `Version ${n}`,
  /** One verb per outcome. */
  actions: {
    edit: "Edit story",
    addDetail: "Add detail",
    practice: "Practice this story",
  },
  archivedBody: "Your archived stories live here.",
  notFound: "This story cannot be found.",
} as const;

export const digDeeperFeedback = {
  clear: "What came through clearly",
  nothingClearYet: "Keep going. Add the detail below and check again.",
  missing: "What detail is missing",
  nextSentence: "Try saying next",
  retry: "Try again",
} as const;
