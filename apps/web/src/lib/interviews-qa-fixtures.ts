/**
 * Synthetic interview events, briefs and debriefs for local browser QA only.
 *
 * Served exclusively by /interviews-qa (and its /fixtures JSON) when MIRROR_HOME_QA=1 in a
 * non-production Next.js process. The Playwright script (scripts/qa/interviews_qa.mjs) stubs
 * the API with this data at the network layer; production code paths are unchanged.
 */
import type { InterviewBrief, InterviewDebriefView, InterviewEvent, Profile } from "@/lib/api";

export type InterviewsQaScreen = "list" | "brief-upcoming" | "brief-past" | "brief-past-debriefed";
export const INTERVIEWS_QA_SCREENS: InterviewsQaScreen[] = ["list", "brief-upcoming", "brief-past", "brief-past-debriefed"];

/** The clock every fixture is drawn against, so screenshots do not drift. */
export const INTERVIEWS_QA_NOW = new Date("2026-09-29T09:00:00.000Z");
const at = (hours: number) => new Date(INTERVIEWS_QA_NOW.getTime() + hours * 3_600_000).toISOString();
const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

export const QA_ROLE_ID = uuid(1);
const ROLE_TITLE = "AR Analyst";

const event = (n: number, hours: number, round: InterviewEvent["round_kind"], company: string | null, timing: InterviewEvent["timing"], hasDebrief = false): InterviewEvent => ({
  id: uuid(n), role_profile_id: QA_ROLE_ID, scheduled_for: at(hours), round_kind: round, company_label: company,
  has_debrief: hasDebrief, timing, created_at: at(-240), updated_at: at(-240),
});

const soon = event(11, 30, "SCREENING", "Northwind Traders", "SOON");
const later = event(12, 24 * 9, "TECHNICAL", null, "UPCOMING");
const past = event(13, -26, "BEHAVIOURAL", "Contoso Finance Shared Services (EMEA)", "PAST");
const debriefed = event(14, -24 * 6, "HR", "Fabrikam", "PAST", true);

const brief = (e: InterviewEvent): InterviewBrief => ({
  event: e, role_title: ROLE_TITLE, state: "READY",
  themes: [
    { key: "collections", label: "Collections follow-up", coverage: "PREPARED", support: "Story: Reducing overdue invoices", story_id: uuid(60), prompt: "Tell me about a time you brought an overdue account back on track." },
    { key: "reconciliation", label: "Reconciliation", coverage: "MENTIONED", support: null, story_id: null, prompt: "How do you find and resolve a mismatch between the ledger and the bank?" },
    { key: "stakeholders", label: "Working with sales", coverage: "MISSING", support: null, story_id: null, prompt: "Describe a disagreement with a sales colleague about a customer's credit." },
  ],
  recheck: [{ claim_id: uuid(70), statement: "Reduced days sales outstanding by 12 days in two quarters.", readiness: "NEEDS_PREPARATION", question: "What did you change, and how did you measure the 12 days?" }],
  focus: { title: "Explain the reasoning behind your choices", body: "In your latest practice you described what you did clearly; say why you chose it.", session_id: uuid(80) },
  questions_to_ask: ["How is the collections team measured?", "What does a typical month-end look like?"],
  limitations: ["Built from this role and your own stories and practice.", "It cannot know what this interviewer will ask."],
});

const debriefView: InterviewDebriefView = {
  debrief: {
    id: uuid(90), interview_event_id: debriefed.id, questions_asked: ["Why do you want to work here?", "Tell me about a disagreement with sales."],
    feeling: "MIXED", outcome: "NEXT_ROUND", notes: "Panel of two. Ask about team size next time.", created_at: at(-24 * 5), updated_at: at(-24 * 5),
  },
  follow_ups: [
    { question: "Why do you want to work here?", theme_key: null, theme_label: null, coverage: null, action: "NONE", action_href: null },
    { question: "Tell me about a disagreement with sales.", theme_key: "stakeholders", theme_label: "Working with sales", coverage: "MISSING", action: "ADD_STORY", action_href: "/stories/new?theme=Working%20with%20sales" },
  ],
};

export const interviewsQaFixtures = {
  now: INTERVIEWS_QA_NOW.toISOString(),
  roleId: QA_ROLE_ID,
  profile: { id: "qa-user", full_name: "Ankit Sunil", email: "ankit@example.test" } as Profile,
  events: [soon, later, past, debriefed],
  briefs: Object.fromEntries([soon, later, past, debriefed].map((e) => [e.id, brief(e)])) as Record<string, InterviewBrief>,
  debriefs: { [debriefed.id]: debriefView } as Record<string, InterviewDebriefView>,
  screens: { list: null, "brief-upcoming": soon.id, "brief-past": past.id, "brief-past-debriefed": debriefed.id } as Record<InterviewsQaScreen, string | null>,
};

export function interviewsQaScreen(value: string | undefined): InterviewsQaScreen {
  return INTERVIEWS_QA_SCREENS.includes(value as InterviewsQaScreen) ? (value as InterviewsQaScreen) : "list";
}
