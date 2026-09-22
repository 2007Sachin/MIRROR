/**
 * Roles: the candidate-facing view of a role profile and the practice attached to it.
 *
 * What a role expects, and how the candidate's experience covers it, is computed by
 * the backend Interview Map (`GET /api/v1/roles/{id}/interview-map`), not here.
 */
import type { DashboardDiagnostic, RoleProfileSummary } from "@/lib/api";
import { roles as t } from "@/lib/copy";
import { formatShortDay, newSessionHref, sessionKind } from "@/lib/dashboard-view";

export type RoleStatus = "ACTIVE" | "SETUP_INCOMPLETE" | "NOT_PRACTISED";

export type RoleCard = {
  key: string;
  profileId: string | null;
  role: string;
  status: RoleStatus;
  statusLabel: string;
  meta: string | null;
  action: string;
  href: string;
  detailHref: string | null;
};

const roleKey = (role: string) => role.trim().toLocaleLowerCase();

/**
 * One card per role. Role profiles are the source of truth for which roles exist;
 * practice adds the "last practised" line and can surface a role set up before
 * role profiles were recorded.
 */
export function roleCards(
  profiles: RoleProfileSummary[],
  sessions: DashboardDiagnostic[],
  onboardingRole?: string | null,
): RoleCard[] {
  const latestFor = new Map<string, DashboardDiagnostic>();
  const finishedFor = new Map<string, DashboardDiagnostic>();
  for (const session of sessions) {
    const key = roleKey(session.target_role);
    if (!latestFor.has(key)) latestFor.set(key, session);
    if (!finishedFor.has(key) && sessionKind(session) === "review_ready") finishedFor.set(key, session);
  }

  const cards: RoleCard[] = [];
  const seen = new Set<string>();
  const add = (role: string, profileId: string | null) => {
    const key = roleKey(role);
    if (!key || seen.has(key)) return;
    seen.add(key);
    const latest = latestFor.get(key) ?? null;
    const finished = finishedFor.get(key) ?? null;
    const kind = latest ? sessionKind(latest) : null;
    const incomplete = kind === "setup" || (latest === null && profileId === null);
    const status: RoleStatus = incomplete ? "SETUP_INCOMPLETE" : finished || kind ? "ACTIVE" : "NOT_PRACTISED";
    const practisedOn = finished?.completed_at ?? finished?.updated_at ?? null;
    cards.push({
      key,
      profileId,
      role,
      status,
      statusLabel: status === "SETUP_INCOMPLETE" ? t.setupIncomplete : status === "ACTIVE" ? t.active : t.notPractisedYet,
      meta: practisedOn ? t.lastPractised(formatShortDay(practisedOn)) : null,
      action: status === "SETUP_INCOMPLETE" ? t.finishSetup : t.continuePreparing,
      // A role with a profile opens its workspace; the Interview Map is where preparing continues.
      href: status === "SETUP_INCOMPLETE"
        ? newSessionHref(role)
        : profileId
          ? `/roles/${profileId}`
          : `/practice/start?role=${encodeURIComponent(role)}`,
      detailHref: profileId ? `/roles/${profileId}` : null,
    });
  };

  for (const profile of profiles) add(profile.target_role, profile.id);
  for (const session of sessions) add(session.target_role, null);
  if (onboardingRole?.trim()) add(onboardingRole.trim(), null);
  return cards;
}

export function sessionsForRole(sessions: DashboardDiagnostic[], role: string) {
  const key = roleKey(role);
  return sessions.filter((session) => roleKey(session.target_role) === key);
}
