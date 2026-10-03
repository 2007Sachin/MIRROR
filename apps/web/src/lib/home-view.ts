/**
 * Home: words and links for what the server decided.
 *
 * `GET /api/v1/home` chooses the state, the role and every number. Nothing here decides
 * what comes first, compares practices or counts anything. It only turns those decisions
 * into text and addresses.
 */
import type { HomeActivityItem, HomeNextStep, HomeResponse, HomeUpcomingInterview, PracticeFocusKey } from "@/lib/api";
import { homeNow as t, interviews as interviewCopy } from "@/lib/copy";
import { formatShortDay, reviewHref } from "@/lib/dashboard-view";
import { focusFor, modeCopy, practiceLabel, startPracticeHref } from "@/lib/practice-view";
import { dimensionAnswersHref, dimensionHref, roleProgressHref } from "@/lib/progress-view";

export function continueHref(sessionId: string) {
  return `/app/interview/${sessionId}`;
}

/** "18 minutes ago", "2 hours ago", "yesterday", then a date. */
export function timeAgo(value: string, now = new Date()) {
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(value).getTime()) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} ${minutes === 1 ? "minute" : "minutes"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? "hour" : "hours"} ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return formatShortDay(value, now);
}

/** What was practised: the way of practising, and the area for a short one. */
export function practiceHeading(role: string, mode: Parameters<typeof modeCopy>[0]) {
  return `${role} · ${modeCopy(mode).title}`;
}

export function practiceArea(mode: string, focus: string | null, theme: string | null) {
  if (mode === "FULL_INTERVIEW") return null;
  return theme || focusFor(focus)?.title || null;
}

export function recommendedTitle(step: HomeNextStep) {
  if (step.theme) return t.recommended.titleForTheme(step.theme);
  return t.recommended.title[step.focus] ?? t.recommended.title.role;
}

export function startStepHref(step: HomeNextStep) {
  return startPracticeHref(
    step.target_role,
    { mode: step.mode, focus: step.focus as PracticeFocusKey, theme: step.theme },
    step.role_profile_id,
  );
}

export function whyHref(step: HomeNextStep) {
  return step.dimension ? dimensionHref(step.role_profile_id, step.dimension) : roleProgressHref(step.role_profile_id);
}

export function answersHref(step: HomeNextStep) {
  return step.dimension ? dimensionAnswersHref(step.role_profile_id, step.dimension) : roleProgressHref(step.role_profile_id, "answers");
}

export function subline(data: HomeResponse) {
  // "or work on what matters next" is only said when there is something to work on next.
  if (data.state === "ACTIVE_PRACTICE" && !data.next_step) return t.sub.ACTIVE_PRACTICE_ONLY;
  const line = t.sub[data.state];
  return typeof line === "function" ? line(data.selected?.target_role ?? "") : line;
}

export type ActivityRow = { key: string; at: string; date: string; text: string; action: string; href: string };

export function activityDate(value: string, now = new Date()) {
  return new Date(value).toDateString() === now.toDateString() ? t.recent.today : formatShortDay(value, now);
}

export function activityRow(item: HomeActivityItem, now = new Date()): ActivityRow {
  const date = activityDate(item.at, now);
  if (item.kind === "STORY" && item.story_id) {
    return { key: `story-${item.story_id}`, at: item.at, date, text: t.recent.storyUpdated(item.title), action: t.recent.openStory, href: `/stories/${item.story_id}` };
  }
  const label = practiceLabel(item.practice_mode ?? "FULL_INTERVIEW", item.practice_focus, item.practice_theme);
  const id = item.session_id ?? "";
  const ready = item.session_kind === "REVIEW_READY";
  const live = item.session_kind === "ACTIVE";
  return {
    key: `session-${id}`,
    at: item.at,
    date,
    text: `${label} · ${item.title}`,
    action: ready ? t.recent.viewReview : live ? t.recent.continue : t.recent.open,
    href: live ? continueHref(id) : reviewHref(id),
  };
}

/** "Your technical interview for Data Analyst is tomorrow at 2:00 PM." The server chose the interview. */
export function upcomingLine(event: HomeUpcomingInterview, now = new Date()) {
  const at = new Date(event.scheduled_for);
  const time = new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(at);
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  const when =
    at.toDateString() === now.toDateString() ? t.upcoming.today(time)
    : at.toDateString() === tomorrow.toDateString() ? t.upcoming.tomorrow(time)
    : t.upcoming.later(new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(at), time);
  // "Other" says nothing about the round, so it is left out; "HR" keeps its capitals.
  const label = event.round_kind === "OTHER" ? "" : interviewCopy.rounds[event.round_kind] ?? "";
  return t.upcoming.line(event.round_kind === "HR" ? label : label.toLowerCase(), event.target_role, when);
}

export function briefHref(event: HomeUpcomingInterview) {
  return `/roles/${event.role_profile_id}/interviews/${event.event_id}`;
}
