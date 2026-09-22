/**
 * Practice: the candidate-facing view of interview sessions.
 *
 * Shares its vocabulary with the Home page (`lib/dashboard-view.ts`) rather than
 * repeating it. Nothing here starts, plans or scores a conversation: it only decides
 * what a row says and where its one action goes.
 */
import type { DashboardDiagnostic, DashboardSummary } from "@/lib/api";
import { practiceFocus } from "@/lib/copy";
import { newSessionHref, sessionKind, sessionRow, type SessionRow } from "@/lib/dashboard-view";

export type PracticeFocus = (typeof practiceFocus.options)[number];
export type PracticeFocusKey = PracticeFocus["key"];

export const DEFAULT_FOCUS: PracticeFocusKey = "full";

export function focusFor(key: string | null | undefined): PracticeFocus {
  return practiceFocus.options.find((option) => option.key === key) ?? practiceFocus.options[0];
}

export function isFocusKey(value: string | null | undefined): value is PracticeFocusKey {
  return practiceFocus.options.some((option) => option.key === value);
}

/** The recommended option first, then the rest, exactly as the copy lists them. */
export function recommendedFocus(): PracticeFocus {
  return practiceFocus.options.find((option) => "recommended" in option && option.recommended) ?? practiceFocus.options[0];
}

export function otherFocusOptions(): PracticeFocus[] {
  const recommended = recommendedFocus();
  return practiceFocus.options.filter((option) => option.key !== recommended.key);
}

/** Where "Start practice" goes. Role and focus are carried, never invented. */
export function startPracticeHref(role?: string | null, focus?: string | null) {
  const params = new URLSearchParams();
  if (role?.trim()) params.set("role", role.trim());
  if (focus && focus !== DEFAULT_FOCUS && isFocusKey(focus)) params.set("focus", focus);
  const query = params.toString();
  return `/practice/start${query ? `?${query}` : ""}`;
}

/** The setup flow, with the chosen focus kept so it survives the round trip. */
export function setupHref(role: string, focus?: string | null) {
  const base = newSessionHref(role);
  if (!focus || focus === DEFAULT_FOCUS || !isFocusKey(focus)) return base;
  return `${base}${base.includes("?") ? "&" : "?"}focus=${encodeURIComponent(focus)}`;
}

export function briefHref(sessionId: string, focus?: string | null) {
  if (!focus || focus === DEFAULT_FOCUS || !isFocusKey(focus)) return `/sessions/${sessionId}/brief`;
  return `/sessions/${sessionId}/brief?focus=${encodeURIComponent(focus)}`;
}

/**
 * Every practice, newest first. Unlike the Home page this keeps each one, because
 * this is the page people come to when they want the whole list.
 */
export function practiceHistory(
  sessions: DashboardDiagnostic[],
  summary: DashboardSummary["latest_review"] | null,
): SessionRow[] {
  return sessions.map((session) => sessionRow(session, summary));
}

/** The one practice worth continuing: unfinished first, then the newest finished one. */
export function continuePractice(sessions: DashboardDiagnostic[]): DashboardDiagnostic | null {
  const unfinished = sessions.find((session) => {
    const kind = sessionKind(session);
    return kind === "in_progress" || kind === "ready" || kind === "setup";
  });
  return unfinished ?? sessions[0] ?? null;
}
