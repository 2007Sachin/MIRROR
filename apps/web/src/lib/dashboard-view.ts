/**
 * Pure helpers that turn the existing dashboard data into what the Home page shows.
 * Nothing here computes readiness: the review numbers and labels come from the API
 * (`/api/v1/dashboard/summary`). This file only classifies sessions, groups and formats.
 */
import type { DashboardDiagnostic, DashboardSummary, Onboarding } from "@/lib/api";
import { home } from "@/lib/copy";

export type SessionKind =
  | "review_ready"
  | "review_processing"
  | "review_failed"
  | "in_progress"
  | "ready"
  | "setup"
  | "failed";

/** Which stage a session is really at. A review is only "ready" when the report exists. */
export function sessionKind(session: DashboardDiagnostic): SessionKind {
  if (session.diagnostic_available) return "review_ready";
  const status = session.interview_status;
  if (status === "ACTIVE") return "in_progress";
  if (status === "READY") return "ready";
  if (status === "FAILED") return "failed";
  if (status === "COMPLETED" || status === "ASSESSING") {
    return session.assessment?.status === "FAILED" ? "review_failed" : "review_processing";
  }
  return "setup";
}

export function reviewIsPending(session: DashboardDiagnostic | null) {
  return session !== null && sessionKind(session) === "review_processing";
}

export function newSessionHref(role?: string) {
  return role ? `/sessions/new?role=${encodeURIComponent(role)}` : "/sessions/new";
}

export function reviewHref(sessionId: string, anchor?: string) {
  return `/app/report/${sessionId}${anchor ? `#${anchor}` : ""}`;
}

export function formatDay(value: string | null) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" }).format(new Date(value));
}

export function formatShortDay(value: string | null, now = new Date()) {
  if (!value) return "";
  const date = new Date(value);
  const options: Intl.DateTimeFormatOptions =
    date.getFullYear() === now.getFullYear() ? { day: "numeric", month: "short" } : { day: "numeric", month: "short", year: "numeric" };
  return new Intl.DateTimeFormat("en-GB", options).format(date);
}

export function relativeDay(value: string | null, now = new Date()) {
  if (!value) return null;
  const days = Math.floor((now.getTime() - new Date(value).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days} days ago`;
}

export function firstNameOf(fullName: string | null | undefined, email: string | null | undefined) {
  const value = fullName?.trim() || email?.split("@")[0] || "there";
  return value.split(/\s+/)[0];
}

export function greetingForHour(hour: number) {
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

// ------------------------------------------------------- candidate-facing Home view

type Review = NonNullable<DashboardSummary["latest_review"]>;

export type DevelopmentState =
  | "Coming through clearly"
  | "Developing"
  | "Needs more practice"
  | "Not explored yet";

export type DevelopmentArea = {
  key: string;
  label: string;
  state: DevelopmentState;
  note: string;
  href: string;
};

const developmentLabels: Record<string, string> = {
  role_understanding: "Connecting your experience to the role",
  examples: "Using real examples",
  depth: "Explaining your decisions",
  impact: "Showing your impact",
};

const notExploredNotes: Record<string, string> = {
  role_understanding: "We haven't explored enough about how your experience connects to this role yet.",
  examples: "We heard too little to understand how consistently you use real examples.",
  depth: "We haven't asked enough about the decisions behind your work yet.",
  impact: "We haven't heard enough about what changed because of your work yet.",
};

export function developmentState(value: string): DevelopmentState {
  if (value === "Strong" || value === "Clear") return "Coming through clearly";
  if (value === "Developing" || value === "Could go further") return "Developing";
  if (value === "Needs attention") return "Needs more practice";
  return "Not explored yet";
}

export function developmentAreas(review: Review): DevelopmentArea[] {
  const byKey = new Map(review.dimensions.map((dimension) => [dimension.key, dimension]));
  return Object.entries(developmentLabels).map(([key, label]) => {
    const dimension = byKey.get(key);
    const state = developmentState(dimension?.state ?? "");
    return {
      key,
      label,
      state,
      note: state === "Not explored yet"
        ? notExploredNotes[key]
        : dimension?.note || "Complete another practice to learn more about this area.",
      href: `/progress/${encodeURIComponent(key)}`,
    };
  });
}

export type PracticeOption = {
  role: string;
  description: string;
  href: string | null;
  quickStart: boolean;
};

/** One truthful action per role. An unfinished practice always wins over creating another one. */
export function practiceOptions(sessions: DashboardDiagnostic[], onboarding: Onboarding): PracticeOption[] {
  const options: PracticeOption[] = [];
  const seen = new Set<string>();
  for (const session of sessions) {
    const key = session.target_role.trim().toLocaleLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const kind = sessionKind(session);
    if (kind === "in_progress") {
      options.push({ role: session.target_role, description: "Continue your saved practice", href: `/app/interview/${session.id}`, quickStart: false });
      continue;
    }
    if (kind === "ready") {
      options.push({ role: session.target_role, description: "Your practice is ready", href: `/app/interview/${session.id}`, quickStart: false });
      continue;
    }
    if (kind === "setup") {
      options.push({ role: session.target_role, description: "Finish preparing this role", href: newSessionHref(session.target_role), quickStart: false });
      continue;
    }
    const canReuseSetup =
      onboarding.target_role?.trim().toLocaleLowerCase() === key
      && Boolean(onboarding.onboarding_resume_document_id)
      && Boolean(onboarding.onboarding_role_profile_id);
    options.push({
      role: session.target_role,
      description: canReuseSetup ? "Ready for another practice" : "A little setup is needed",
      href: canReuseSetup ? null : newSessionHref(session.target_role),
      quickStart: canReuseSetup,
    });
  }

  const configuredRole = onboarding.target_role?.trim();
  if (configuredRole && !seen.has(configuredRole.toLocaleLowerCase())) {
    const canReuseSetup = Boolean(onboarding.onboarding_resume_document_id && onboarding.onboarding_role_profile_id);
    options.push({
      role: configuredRole,
      description: canReuseSetup ? "Ready to practice" : "Finish preparing this role",
      href: canReuseSetup ? null : newSessionHref(configuredRole),
      quickStart: canReuseSetup,
    });
  }
  return options;
}

// ------------------------------------------------------------------- recent sessions

export type SessionRow = {
  id: string;
  role: string;
  date: string;
  state: string;
  summary: string;
  action: string;
  href: string;
  kind: SessionKind;
};

export function summaryLine(counts: NonNullable<DashboardSummary["latest_review"]>["counts"]) {
  if (!counts) return home.recent.previous;
  const toImprove = counts.could_be_stronger + counts.worth_revisiting;
  return `${counts.clear} clear · ${toImprove} to improve`;
}

export function sessionRow(session: DashboardDiagnostic, summary: DashboardSummary["latest_review"] | null): SessionRow {
  const kind = sessionKind(session);
  const base = {
    id: session.id,
    role: session.target_role,
    date: formatShortDay(session.completed_at || session.updated_at),
    kind,
  };
  switch (kind) {
    case "review_ready":
      return {
        ...base,
        state: "Review ready",
        summary: summary && summary.session_id === session.id ? summaryLine(summary.counts) : home.recent.previous,
        action: "Open",
        href: reviewHref(session.id),
      };
    case "review_processing":
      return { ...base, state: "Preparing your review", summary: "Your conversation is saved", action: "Open", href: reviewHref(session.id) };
    case "review_failed":
      return { ...base, state: "Review didn't finish", summary: "Your conversation is saved", action: "Try again", href: reviewHref(session.id) };
    case "in_progress":
      return { ...base, state: "Conversation saved", summary: "Pick up where you left off", action: "Continue", href: `/app/interview/${session.id}` };
    case "ready":
      return { ...base, state: "Ready to begin", summary: "Role added · Experience ready", action: "Begin", href: `/app/interview/${session.id}` };
    case "failed":
      return { ...base, state: "Didn't finish", summary: "You can start again whenever you like", action: "Start again", href: newSessionHref(session.target_role) };
    default:
      return { ...base, state: "Setup in progress", summary: "Role added", action: "Continue", href: newSessionHref(session.target_role) };
  }
}
