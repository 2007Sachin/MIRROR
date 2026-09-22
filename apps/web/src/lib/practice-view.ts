/**
 * Practice: the candidate-facing view of practice sessions and practice choices.
 *
 * The shape of each mode (how many questions, how long) is decided by the backend
 * (`practice_modes.py`); the words for it live in `copy.ts`. This file only turns a
 * choice into a link or a label. It never starts, plans or scores a conversation.
 */
import type { DashboardDiagnostic, DashboardSummary, PracticeChoice, PracticeFocusKey, PracticeMode } from "@/lib/api";
import { practiceFocus, practiceModes } from "@/lib/copy";
import { newSessionHref, sessionKind, sessionRow, type SessionRow } from "@/lib/dashboard-view";

export type PracticeFocus = (typeof practiceFocus.options)[number];

export const MODES: PracticeMode[] = ["QUICK_DRILL", "FOCUSED_PRACTICE", "FULL_INTERVIEW"];

export function isMode(value: string | null | undefined): value is PracticeMode {
  return MODES.includes(value as PracticeMode);
}

export function isFocusKey(value: string | null | undefined): value is PracticeFocusKey {
  return value === "full" || practiceFocus.options.some((option) => option.key === value);
}

export function focusFor(key: string | null | undefined): PracticeFocus | null {
  return practiceFocus.options.find((option) => option.key === key) ?? null;
}

export function modeCopy(mode: PracticeMode) {
  return practiceModes[mode];
}

/** What a practice is called in lists: "Quick drill · Show your impact". */
export function practiceLabel(mode: PracticeMode, focus: string | null, theme?: string | null) {
  if (mode === "FULL_INTERVIEW") return modeCopy(mode).title;
  const area = theme || focusFor(focus)?.title;
  return area ? `${modeCopy(mode).title} · ${area}` : modeCopy(mode).title;
}

/** Normalise whatever arrived in a URL into a choice the API will accept. */
export function choiceFrom(mode: string | null, focus: string | null, theme: string | null): PracticeChoice {
  const safeMode: PracticeMode = isMode(mode) ? mode : "FULL_INTERVIEW";
  const safeFocus = isFocusKey(focus) && focus !== "full" ? focus : null;
  if (safeMode !== "FULL_INTERVIEW" && !safeFocus) return { mode: safeMode, focus: null, theme: null };
  return { mode: safeMode, focus: safeFocus, theme: safeFocus === "role" && theme?.trim() ? theme.trim() : null };
}

/** A short practice cannot start without an area; a full interview never needs one. */
export function choiceIsComplete(choice: PracticeChoice) {
  return choice.mode === "FULL_INTERVIEW" || Boolean(choice.focus);
}

function query(role: string | null | undefined, choice?: Partial<PracticeChoice>) {
  const params = new URLSearchParams();
  if (role?.trim()) params.set("role", role.trim());
  if (choice?.mode && choice.mode !== "FULL_INTERVIEW") params.set("mode", choice.mode);
  if (choice?.focus && choice.focus !== "full") params.set("focus", choice.focus);
  if (choice?.theme) params.set("theme", choice.theme);
  return params.toString();
}

/** Where "Start practice" goes. Role and choice are carried, never invented. */
export function startPracticeHref(role?: string | null, choice?: Partial<PracticeChoice> | string | null) {
  const normalised = typeof choice === "string" ? { mode: "QUICK_DRILL" as const, focus: choice as PracticeFocusKey } : choice ?? undefined;
  const text = query(role, normalised ?? undefined);
  return `/practice/start${text ? `?${text}` : ""}`;
}

/** The full setup flow, keeping the choice so it survives the round trip. */
export function setupHref(role: string, choice?: PracticeChoice) {
  const base = newSessionHref(role);
  const extra = query(null, choice);
  return extra ? `${base}&${extra}` : base;
}

export function briefHref(sessionId: string) {
  return `/sessions/${sessionId}/brief`;
}

/** Every practice, newest first, each labelled with how it was practised. */
export function practiceHistory(
  sessions: DashboardDiagnostic[],
  summary: DashboardSummary["latest_review"] | null,
): Array<SessionRow & { label: string }> {
  return sessions.map((session) => ({
    ...sessionRow(session, summary),
    label: practiceLabel(session.practice_mode ?? "FULL_INTERVIEW", session.practice_focus, session.practice_theme),
  }));
}

/** The one practice worth continuing: an unfinished one, if there is one. */
export function continuePractice(sessions: DashboardDiagnostic[]): DashboardDiagnostic | null {
  return (
    sessions.find((session) => {
      const kind = sessionKind(session);
      return kind === "in_progress" || kind === "ready";
    }) ?? null
  );
}
