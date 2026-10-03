/**
 * Synthetic Progress scenarios for local browser QA only.
 *
 * Rendered exclusively by /progress-qa when MIRROR_HOME_QA=1 in a non-production
 * Next.js process. They are invented layout data, never real practice results, and they
 * never touch the authenticated pages, the API, Supabase or RLS.
 */
import type {
  AnswerAttempt,
  DevState,
  ProgressAnswer,
  ProgressAnswerDetail,
  ProgressAnswerSignal,
  ProgressAnswerState,
  ProgressCell,
  ProgressConnectionArea,
  ProgressDimension,
  ProgressRoleTile,
  ProgressTrend,
  RoleProgress,
} from "@/lib/api";

export type ProgressQaScenario = "comparable" | "baseline" | "none";

const ROLE = "00000000-0000-4000-8000-0000000000d1";
const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const DAYS = [
  "2026-09-12T10:00:00.000Z",
  "2026-09-18T10:00:00.000Z",
  "2026-09-25T10:00:00.000Z",
  "2026-09-27T10:00:00.000Z",
];
const SESSIONS = [uuid(101), uuid(102), uuid(103), uuid(104)];

function cell(index: number, state: DevState, seen = 0, strong = 0): ProgressCell {
  return { session_id: SESSIONS[index], number: index + 1, completed_at: DAYS[index], state, answers_seen: seen, answers_strong: strong };
}

function dimension(
  key: string,
  focus: string,
  cells: ProgressCell[],
  trend: ProgressTrend | null,
  note: string | null,
): ProgressDimension {
  const explored = cells.filter((item) => item.state !== "NOT_EXPLORED");
  const latest = explored[explored.length - 1];
  return {
    key,
    state: latest?.state ?? "NOT_EXPLORED",
    note,
    trend,
    compared_with: trend && explored.length > 1 ? explored[explored.length - 2].completed_at : null,
    current: Boolean(trend),
    practice_focus: focus,
    cells,
  };
}

function signal(dimensionKey: string, state: ProgressAnswerState, observation: string, quote: string | null = null): ProgressAnswerSignal {
  return { dimension: dimensionKey, state, observation, quote };
}

function answer(n: number, practice: number, question: string, position: number, signals: ProgressAnswerSignal[]): ProgressAnswer {
  return {
    session_id: SESSIONS[practice - 1],
    answer_turn_id: uuid(200 + n),
    question,
    practice_number: practice,
    completed_at: DAYS[practice - 1],
    question_position: position,
    question_total: 6,
    signals,
  };
}

const ANSWERS: ProgressAnswer[] = [
  answer(1, 4, "How did you decide which metrics to focus on?", 3, [
    signal("depth", "NEEDS_PRACTICE", "Reporting: You described the metrics you selected, but not why those metrics were more useful than the alternatives.", "I looked at engagement since it was decreasing."),
    signal("role_understanding", "PRESENT", "Reporting: This answer spoke to what the role looks for."),
  ]),
  answer(2, 4, "Walk me through a report you built end to end.", 2, [
    signal("examples", "STRONG", "About “Cut reporting time by half”: This came through clearly in your conversation.", "I rebuilt the weekly report in SQL and scheduled it."),
  ]),
  answer(3, 3, "Tell me about a time you had to choose between two approaches.", 4, [
    signal("depth", "NEEDS_PRACTICE", "Reporting: You explained what you did, and the reasons behind the choice were brief."),
    signal("impact", "NEEDS_PRACTICE", "The scale you mentioned wasn't backed by a number or a source."),
  ]),
  answer(4, 3, "What changed because of your reports?", 5, [
    signal("impact", "STRONG", "You made clear which parts were yours and which were the team's."),
    signal("examples", "STRONG", "About “Built a churn dashboard”: This came through clearly in your conversation."),
  ]),
  answer(5, 2, "How do you prioritise requests when you have limited time?", 3, [
    signal("depth", "PRESENT", "Reporting: Some of the detail came through, and some was brief."),
    signal("role_understanding", "STRONG", "Stakeholder management: This came through clearly."),
  ]),
  answer(6, 1, "Describe a project where you made a trade-off.", 2, [
    signal("depth", "STRONG", "You explained the options you had and why you chose one."),
  ]),
];

const AREAS: ProgressConnectionArea[] = [
  { key: "reporting", name: "Reporting", seen: "REPEATEDLY", practices_seen: 3, answers: [ANSWERS[0], ANSWERS[4]].map((a) => ({ session_id: a.session_id, answer_turn_id: a.answer_turn_id })) },
  { key: "stakeholder-management", name: "Stakeholder management", seen: "SOMETIMES", practices_seen: 1, answers: [{ session_id: ANSWERS[4].session_id, answer_turn_id: ANSWERS[4].answer_turn_id }] },
  { key: "experimentation", name: "Experimentation", seen: "NOT_EXPLORED", practices_seen: 0, answers: [] },
  { key: "sql", name: "SQL", seen: "REPEATEDLY", practices_seen: 2, answers: [{ session_id: ANSWERS[1].session_id, answer_turn_id: ANSWERS[1].answer_turn_id }] },
];

function practices(count: number): RoleProgress["practices"] {
  const kinds: Array<[RoleProgress["practices"][number]["practice_mode"], string | null]> = [
    ["FULL_INTERVIEW", null],
    ["QUICK_DRILL", "impact"],
    ["FULL_INTERVIEW", null],
    ["FOCUSED_PRACTICE", "decisions"],
  ];
  return kinds
    .slice(0, count)
    .map(([mode, focus], index) => ({
      session_id: SESSIONS[index],
      number: index + 1,
      completed_at: DAYS[index],
      practice_mode: mode,
      practice_focus: focus,
      practice_theme: null,
      question_count: mode === "QUICK_DRILL" ? 4 : mode === "FOCUSED_PRACTICE" ? 6 : 12,
      shorter_conversation: index === 1,
    }))
    .reverse();
}

export function roleProgressFixture(scenario: ProgressQaScenario): RoleProgress {
  const base = { role_profile_id: ROLE, target_role: "Data Analyst" };
  if (scenario === "none") {
    return {
      ...base, stage: "NONE", practice_count: 0, last_practised_at: null, practices: [], answers: [],
      dimensions: ["role_understanding", "examples", "depth", "impact"].map((key) => dimension(key, "story", [], null, null)),
      insights: [], connection: { state: "READY", areas: AREAS.map((area) => ({ ...area, seen: "NOT_EXPLORED", practices_seen: 0, answers: [] })) },
    };
  }
  if (scenario === "baseline") {
    return {
      ...base, stage: "BASELINE", practice_count: 1, last_practised_at: DAYS[0], practices: practices(1),
      answers: ANSWERS.filter((item) => item.practice_number === 1),
      dimensions: [
        dimension("role_understanding", "role", [cell(0, "COMING_THROUGH", 2, 2)], null, "You understood what the role is looking for."),
        dimension("examples", "story", [cell(0, "DEVELOPING", 3, 1)], null, "Some examples came through, and others need more detail."),
        dimension("depth", "decisions", [cell(0, "NEEDS_PRACTICE", 2, 0)], null, "Most answers stayed at a high level."),
        dimension("impact", "impact", [cell(0, "NOT_EXPLORED")], null, null),
      ],
      insights: [],
      connection: { state: "READY", areas: AREAS.map((area) => ({ ...area, seen: area.practices_seen ? "SOMETIMES" : "NOT_EXPLORED", practices_seen: Math.min(area.practices_seen, 1) })) },
    };
  }
  return {
    ...base, stage: "COMPARABLE", practice_count: 4, last_practised_at: DAYS[3], practices: practices(4), answers: ANSWERS,
    dimensions: [
      dimension("role_understanding", "role", [cell(0, "COMING_THROUGH", 3, 3), cell(1, "DEVELOPING", 2, 1), cell(2, "COMING_THROUGH", 3, 2), cell(3, "DEVELOPING", 4, 2)], "LESS", "Some of what the role looks for didn't come up yet."),
      dimension("examples", "story", [cell(0, "DEVELOPING", 4, 2), cell(1, "DEVELOPING", 3, 1), cell(2, "DEVELOPING", 4, 2), cell(3, "COMING_THROUGH", 4, 4)], "MORE", "You had relevant situations to draw from."),
      dimension("depth", "decisions", [cell(0, "DEVELOPING", 3, 2), cell(1, "NEEDS_PRACTICE", 2, 0), cell(2, "NEEDS_PRACTICE", 4, 1), cell(3, "NEEDS_PRACTICE", 4, 2)], "SIMILAR", "Most answers stayed at a high level."),
      dimension("impact", "impact", [cell(0, "NOT_EXPLORED"), cell(1, "DEVELOPING", 2, 1), cell(2, "NOT_EXPLORED"), cell(3, "DEVELOPING", 2, 1)], "SIMILAR", "The results of your work weren't always easy to see."),
    ],
    insights: [
      { dimension: "examples", trend: "MORE", compared_with: DAYS[2] },
      { dimension: "role_understanding", trend: "LESS", compared_with: DAYS[2] },
      { dimension: "depth", trend: "SIMILAR", compared_with: DAYS[2] },
    ],
    connection: { state: "READY", areas: AREAS },
  };
}

export function tilesFixture(): ProgressRoleTile[] {
  return [
    { role_profile_id: ROLE, target_role: "Data Analyst", stage: "COMPARABLE", practice_count: 4, last_practised_at: DAYS[3], positive: { dimension: "examples", kind: "IMPROVING" }, attention: { dimension: "depth", kind: "NEEDS_ATTENTION" } },
    { role_profile_id: uuid(2), target_role: "Product Analyst", stage: "COMPARABLE", practice_count: 3, last_practised_at: DAYS[2], positive: { dimension: "role_understanding", kind: "CLEAR" }, attention: { dimension: "impact", kind: "LESS" } },
    { role_profile_id: uuid(3), target_role: "Business Analyst", stage: "BASELINE", practice_count: 1, last_practised_at: DAYS[1], positive: { dimension: "examples", kind: "CLEAR" }, attention: { dimension: "depth", kind: "NEEDS_ATTENTION" } },
    { role_profile_id: uuid(4), target_role: "Product Manager", stage: "NONE", practice_count: 0, last_practised_at: null, positive: null, attention: null },
  ];
}

export function answerFixture(): ProgressAnswerDetail {
  const first = ANSWERS[0];
  const attempt: AnswerAttempt = {
    id: uuid(900), session_id: first.session_id, question_turn_id: uuid(901), original_turn_id: first.answer_turn_id, sequence: 1,
    question_text: first.question, original_answer: "x", answer_text: "I chose conversion and retention because they tied directly to the goal of reducing churn, and I passed on raw engagement because it moved without changing revenue.",
    area_key: null, area_title: "Explaining your decisions", created_at: DAYS[3],
    comparison: {
      source: "MODEL",
      changes: [
        { aspect: "REASONING", first: "ABSENT", latest: "PRESENT" },
        { aspect: "RESULT", first: "ABSENT", latest: "ABSENT" },
      ],
      summary: "Your latest answer gives a reason for your choice.",
      next_suggestion: "Next time, finish with what happened afterwards.",
      came_through_more_clearly: ["REASONING"], still_missing: ["RESULT"], first_present: [], latest_present: ["REASONING"],
    },
  };
  return {
    role_profile_id: ROLE, target_role: "Data Analyst", session_id: first.session_id, answer_turn_id: first.answer_turn_id,
    question: first.question, answer: "I started by looking at engagement since it was decreasing. I looked into the conversion funnel and focused on activation and retention metrics because they seemed most relevant to the business goals at the time.",
    practice_number: first.practice_number, completed_at: first.completed_at, practice_mode: "FOCUSED_PRACTICE",
    question_position: first.question_position, question_total: first.question_total, signals: first.signals, attempts: [attempt],
  };
}
