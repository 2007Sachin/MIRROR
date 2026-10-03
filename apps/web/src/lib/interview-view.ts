/**
 * Interview events presentation. Timing (UPCOMING / SOON / PAST) and every brief line
 * come from the backend; this file only groups, formats and prepares form input.
 */
import type { InterviewEvent } from "@/lib/api";
import { interviews as t } from "@/lib/copy";

export const MAX_QUESTIONS = 15;
export const MAX_QUESTION_LENGTH = 500;
export const MAX_COMPANY_LENGTH = 120;
export const MAX_NOTES_LENGTH = 2000;

/** Upcoming soonest first, then past most recent first. */
export function groupEvents(events: InterviewEvent[]) {
  const at = (event: InterviewEvent) => new Date(event.scheduled_for).getTime();
  return {
    upcoming: events.filter((event) => event.timing !== "PAST").sort((a, b) => at(a) - at(b)),
    past: events.filter((event) => event.timing === "PAST").sort((a, b) => at(b) - at(a)),
  };
}

export function timingLabel(event: InterviewEvent) {
  return t.timing[event.timing] ?? t.timing.UPCOMING;
}

export function roundLabel(event: InterviewEvent) {
  return t.rounds[event.round_kind] ?? t.rounds.OTHER;
}

export function formatWhen(iso: string, locale?: string) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "full", timeStyle: "short" }).format(new Date(iso));
}

/** The debrief form shows once the interview has happened, or when something was already written. */
export function showDebrief(event: InterviewEvent) {
  return event.timing === "PAST" || event.has_debrief;
}

/** The list only nudges for a debrief after the interview, and only until one exists. */
export function promptDebrief(event: InterviewEvent) {
  return event.timing === "PAST" && !event.has_debrief;
}

/** A `datetime-local` value ("2026-10-01T09:30") as a tz-aware ISO string in the browser's offset. */
export function localInputToIso(value: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [year, month, day, hour, minute] = match.slice(1).map(Number);
  const date = new Date(year, month - 1, day, hour, minute);
  if (Number.isNaN(date.getTime())) return null;
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.abs(n)).padStart(2, "0");
  return `${value}:00${sign}${pad(Math.trunc(offset / 60))}:${pad(offset % 60)}`;
}

/** The inverse of `localInputToIso`: any ISO instant as a `datetime-local` value in the browser's wall time. */
export function isoToLocalInput(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Mirrors the API rule: split lines, trim, drop blanks, dedupe case-insensitively (first wins), cap. */
export function normaliseQuestions(text: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim().slice(0, MAX_QUESTION_LENGTH);
    const key = line.toLowerCase();
    if (!line || seen.has(key)) continue;
    seen.add(key);
    out.push(line);
    if (out.length === MAX_QUESTIONS) break;
  }
  return out;
}
