/**
 * Words for Practice, the pre-practice check, the reflection after a practice, Reflect,
 * and the few labels in the practice room. Words only: no logic lives here.
 */
import type { PracticeMode } from "@/lib/api";

/** The three ways to practise, each named by what it leaves you with and how long it takes. */
export const practiceFormats: Record<PracticeMode, { title: string; body: string; length: string }> = {
  QUICK_DRILL: {
    title: "5-minute drill",
    body: "Three questions on one area. You leave with one answer you can say more clearly.",
    length: "3 questions · about 5 minutes",
  },
  FOCUSED_PRACTICE: {
    title: "Focused practice",
    body: "Four questions and a few follow-ups on one area, so one part of your story gets sharper.",
    length: "4 questions · about 9 minutes",
  },
  FULL_INTERVIEW: {
    title: "Full interview",
    body: "A realistic conversation from start to finish, so you know how the whole interview feels.",
    length: "About 20 minutes",
  },
};

export const practiceHome = {
  intro: "Choose one thing to rehearse. You can pause any practice and come back to it later.",
  start: "Start practice",
  formatsTitle: "Three ways to practise",
  formatsBody: "Pick the one that fits the time you have. You choose on the next screen, before anything starts.",
  unfinishedTitle: "Continue where you left off",
  unfinishedBody: "These practices aren't finished. Continue one, or discard it if you'd rather start fresh.",
  continue: "Continue",
  setupUnfinished: "Setup didn't finish. You can discard it and start a new practice.",
  suggestionTitle: "A suggestion",
  useSuggestion: "Set up this practice",
} as const;

export const discardPractice = {
  action: "Discard this practice",
  title: "Discard this practice?",
  body: "It won't get a review and won't appear in your history. This can't be undone.",
  confirm: "Discard",
  busy: "Discarding…",
  cancel: "Keep it",
  error: "We couldn't discard that practice just now. Nothing has changed, so you can try again.",
} as const;

/** The pre-practice check: everything is shown before anything is created. */
export const preCheck = {
  title: "Before you start",
  body: "Nothing is set up until you select Start practice.",
  role: "Role",
  format: "Format",
  focus: "Focus",
  length: "Expected length",
  wholeInterview: "The whole interview",
  chooseFocus: "Choose a focus above",
  changeRole: "Change role",
} as const;

/** The reflection after one practice. */
export const reflection = {
  landedTitle: "What landed well",
  landedEmpty: "This conversation was short, so nothing stood out clearly yet. That's normal early on.",
  strengthenTitle: "One thing to strengthen",
  strengthenEmpty: "Nothing specific stood out to strengthen this time.",
  nextTitle: "Try this next",
  nextChoose: "Choose what you'd like to practise next.",
  nextChooseAction: "Choose a practice",
  nextAction: "Set up this practice",
  roleNeed: "Role need",
  fromAnswer: "From your answer to",
  relatesTo: "Relates to",
  repeatTitle: "What would you like to do now?",
  repeat: {
    sameAnswer: "Practise the same answer",
    sameAnswerBody: "Say it again and see what changed.",
    editStory: "Update the story",
    editStoryBody: "Keep what worked for next time.",
    anotherTheme: "Work on another theme",
    anotherThemeBody: "Choose a different area for this role.",
    finish: "Finish for now",
    finishBody: "Everything here is saved.",
  },
} as const;

/** Reflect: reviews, retries, practice history and how practice is developing. */
export const reflect = {
  eyebrow: "Reflect",
  title: "Reflect",
  intro: "Your reviews, your retries, and how your practice is developing for each role.",
  recentTitle: (role: string) => `Recent reviews · ${role}`,
  recentAllTitle: "Recent reviews",
  recentEmpty: "Your finished practice and its review will appear here.",
  otherTitle: "Other roles",
  developingTitle: "How your practice is developing",
  developingBody: "Each role you're preparing for, with what's coming through and what needs more practice.",
  developingUnavailable: "We couldn't load how your practice is developing just now. Your reviews are still here.",
  load: "We couldn't load your reflections just now. Nothing you've done has been removed.",
} as const;

/** The practice room: names for its controls, and what the microphone is used for. */
export const practiceRoom = {
  pauseOrEnd: "Pause or end",
  micPrivacy: "Your microphone is only used while this practice is open. Mute it any time.",
} as const;
