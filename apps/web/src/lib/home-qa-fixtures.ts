/**
 * Synthetic Home scenarios for local browser QA only.
 *
 * They are rendered exclusively by /home-qa when MIRROR_HOME_QA=1 in a
 * non-production Next.js process. They are invented layout data, and they never change
 * the authenticated dashboard loader, Supabase session, API authorization, or RLS.
 */
import type { HomeActivityItem, HomeActivePractice, HomeNextStep, HomeResponse, HomeRole } from "@/lib/api";

export type HomeQaId = "active" | "review-ready" | "returning" | "new-role" | "early" | "cross-role-active" | "upcoming-interview";

export type HomeQaScenario = { id: HomeQaId; label: string; data: HomeResponse };

/** The clock every scenario is drawn against, so screenshots do not drift. */
export const HOME_QA_NOW = new Date("2026-09-29T09:00:00.000Z");
const ago = (minutes: number) => new Date(HOME_QA_NOW.getTime() - minutes * 60_000).toISOString();

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const ar: HomeRole = { role_profile_id: uuid(1), target_role: "AR Analyst" };
const data: HomeRole = { role_profile_id: uuid(2), target_role: "Data Analyst" };
const pm: HomeRole = { role_profile_id: uuid(3), target_role: "Product Manager" };
const ba: HomeRole = { role_profile_id: uuid(4), target_role: "Business Analyst" };

const focused = (role: HomeRole, minutes: number, number: number): HomeActivePractice => ({
  session_id: uuid(50), role_profile_id: role.role_profile_id, target_role: role.target_role, kind: "ACTIVE",
  practice_mode: "FOCUSED_PRACTICE", practice_focus: "decisions", practice_theme: null,
  question_number: number, question_total: 4, last_active_at: ago(minutes),
});

const step = (role: HomeRole): HomeNextStep => ({
  role_profile_id: role.role_profile_id, target_role: role.target_role, mode: "QUICK_DRILL", focus: "decisions", theme: null,
  reason: "Your recent answers describe what you did clearly, but the reasoning behind your choices appears less consistently.",
  dimension: "depth",
});

const activity: HomeActivityItem[] = [
  { kind: "PRACTICE", at: ago(120), session_id: uuid(51), story_id: null, title: "AR Analyst", session_kind: "REVIEW_READY", practice_mode: "FOCUSED_PRACTICE", practice_focus: "decisions", practice_theme: null },
  { kind: "PRACTICE", at: ago(60 * 48), session_id: uuid(52), story_id: null, title: "AR Analyst", session_kind: "REVIEW_READY", practice_mode: "FULL_INTERVIEW", practice_focus: null, practice_theme: null },
  { kind: "STORY", at: ago(60 * 24 * 5), session_id: null, story_id: uuid(60), title: "Pricing decision", session_kind: null, practice_mode: null, practice_focus: null, practice_theme: null },
];

const insights = [
  { dimension: "examples", trend: "MORE" as const, compared_with: ago(60 * 24 * 4) },
  { dimension: "depth", trend: "SIMILAR" as const, compared_with: ago(60 * 24 * 4) },
  { dimension: "role_understanding", trend: "MORE" as const, compared_with: ago(60 * 24 * 4) },
];

const established = {
  stage: "COMPARABLE" as const, practice_count: 4, last_practised_at: ago(120), insights, highlights: [],
};
const prep = {
  map: { state: "READY" as const, without_example: 2 },
  stories: { state: "READY" as const, ready: 5, developing: 2 },
};
const base = { roles: [ar, data, pm, ba], other_active: null, active: null, review: null, next_step: null };
const noPractice = { stage: "NONE" as const, practice_count: 0, last_practised_at: null, insights: [], highlights: [] };

export const homeQaScenarios: HomeQaScenario[] = [
  {
    id: "active", label: "Active practice",
    data: { ...base, state: "ACTIVE_PRACTICE", selected: ar, active: focused(ar, 18, 4), next_step: step(ar), progress: established, ...prep, activity },
  },
  {
    id: "review-ready", label: "Practice completed (review ready)",
    data: {
      ...base, state: "REVIEW_READY", selected: ar, next_step: step(ar), progress: established, ...prep, activity,
      review: { session_id: uuid(51), kind: "REVIEW_READY", target_role: "AR Analyst", practice_mode: "FOCUSED_PRACTICE", practice_focus: "decisions", practice_theme: null, question_count: 12, finished_at: ago(120) },
    },
  },
  {
    id: "returning", label: "No active practice (returning user)",
    data: {
      ...base, state: "RECOMMENDED_NEXT", selected: ar, next_step: step(ar), progress: established, ...prep,
      activity: activity.map((item, index) => (index === 0 ? { ...item, at: ago(60 * 24 * 2) } : item)),
    },
  },
  {
    id: "new-role", label: "New role (no practice yet)",
    data: {
      ...base, state: "FIRST_PRACTICE", selected: pm, progress: noPractice,
      map: { state: "READY", without_example: 3 }, stories: { state: "READY", ready: 5, developing: 2 }, activity: [],
    },
  },
  {
    id: "early", label: "Early user (one practice)",
    data: {
      ...base, state: "EARLY_BASELINE", selected: ba,
      next_step: { ...step(ba), focus: "story", dimension: "examples", reason: "Your answers included some good examples. Keep building detail and context." },
      progress: { stage: "BASELINE", practice_count: 1, last_practised_at: ago(60 * 24 * 3), insights: [], highlights: [{ dimension: "examples", state: "DEVELOPING", note: "Some examples came through, and others need more detail." }] },
      map: { state: "READY", without_example: 3 }, stories: { state: "READY", ready: 2, developing: 1 },
      activity: [{ ...activity[1], at: ago(60 * 24 * 3), title: "Business Analyst" }],
    },
  },
  {
    id: "cross-role-active", label: "Role switch while another role has an active practice",
    data: {
      ...base, state: "FIRST_PRACTICE", selected: data, other_active: focused(ar, 18, 4), progress: noPractice,
      map: { state: "READY", without_example: 2 }, stories: { state: "READY", ready: 5, developing: 2 }, activity: [],
    },
  },
  {
    id: "upcoming-interview", label: "Interview within two days (another role)",
    data: {
      ...base, state: "RECOMMENDED_NEXT", selected: ar, next_step: step(ar), progress: established, ...prep, activity,
      upcoming_interview: {
        event_id: uuid(70), role_profile_id: data.role_profile_id, target_role: data.target_role,
        scheduled_for: new Date(HOME_QA_NOW.getTime() + 26 * 60 * 60_000).toISOString(), round_kind: "TECHNICAL", company_label: "Acme",
      },
    },
  },
];

export function homeQaScenario(id: string | undefined) {
  return homeQaScenarios.find((scenario) => scenario.id === id) ?? homeQaScenarios[0];
}
