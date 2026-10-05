/**
 * Words for interview targets (My plan's "Your interview target", round pages
 * and practice start), plus the pure helpers that turn backend keys into those words.
 *
 * The backend sends keys (round, competency, reason, research state) and catalog claim ids. Raw
 * catalog text is never rendered: a claim, unknown or conflict only shows when it has reviewed,
 * copy-lint-clean words here (tests/unit/test_loop2_web_target_copy.py keeps this complete).
 * This module has no runtime imports so it can be checked directly with `node --test`.
 */
import type { BlueprintView, ClaimView, TargetView } from "@/lib/api-targets";

const OA = "online coding round";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-10-04" -> "4 Oct 2026" (no locale guessing). */
export function shortDate(value: string | null | undefined) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? "");
  if (!match) return "";
  return `${Number(match[3])} ${MONTHS[Number(match[2]) - 1]} ${match[1]}`;
}

export const targetCopy = {
  section: {
    title: "Your interview target",
    loading: "Loading your interview target",
    unavailable: "Your interview target isn't available right now. Your plan below still works.",
    error: "This part didn't load. Nothing is lost.",
    retry: "Try again",
    notYetResearchedTitle: "Not yet researched",
    notYetResearched: (company: string, country: string | null) =>
      `Mirror hasn't researched how ${company} interviews run ${country ? `in ${country}` : "where you're applying"} yet. It won't guess or show guidance written for other countries.`,
    noNotes: (company: string) =>
      `Mirror doesn't have interview notes for ${company} yet. Your plan below builds from the job description, as before.`,
    generalOnly: "Only general guidance covers this so far. Your recruiter's emails are the best guide to your own process.",
    researchedScope: "From published guidance for where you're applying. Your recruiter's emails are the best guide to your own process.",
    stagesTitle: "What published guidance describes",
    publishedGuidanceTitle: "Published guidance",
    mirrorCoverageTitle: "Mirror practice coverage",
    conflictTitle: "These sources disagree",
    conflictNote: "Both are shown as they are. Your invitation email will say how yours works.",
    unknownsTitle: "What Mirror doesn't know yet",
    sourcesToggle: "Where this comes from",
    roundsTitle: "Rounds you can practise in Mirror",
    roundsIntroSuggested: "Mirror practice rounds suggested from the role itself, not the company's process.",
    roundsIntroLinked: "Mirror practice coverage is linked to published guidance where a reviewed mapping exists.",
    practiseFirst: (round: string) => `Practise the ${round.toLocaleLowerCase()}`,
    nothingYet: "Not enough to say yet.",
  },
  level: {
    sde_i: "SDE I",
    sde_ii: "SDE II",
    sde_iii: "SDE III",
    university: "University hire",
    not_sure: "Level not set yet",
  } as Record<string, string>,
  countryNotSet: "Country not set yet",
  levelNotSet: "Level not set yet",
  basis: {
    MIRROR_SUGGESTED: "Mirror's suggestion",
    PUBLISHED_GUIDANCE: "Linked to published guidance",
  } as Record<string, string>,
  rounds: {
    coding_reasoning: {
      title: "Coding conversation",
      covers: "Talking through how you'd solve a coding problem, out loud.",
    },
    system_design: {
      title: "System design conversation",
      covers: "Sketching how a system fits together, in words, and the choices you'd weigh.",
    },
    behavioural: {
      title: "Examples from your own work",
      covers: "Telling real examples from your work, clearly and in order.",
    },
  } as Record<string, { title: string; covers: string }>,
  cannotDo: {
    coding_reasoning: (amazon: boolean) =>
      `Mirror practises the talking part: explaining your approach, the trade-offs you weigh and the inputs you'd try first. It doesn't run your code or time an ${amazon ? OA : "online coding round"}.`,
    system_design: () => "Mirror practises explaining a design out loud. It can't see a drawing or a whiteboard, so describe the parts in words.",
    behavioural: () => "Mirror practises telling real examples from your work. It only names stories you've written yourself.",
  } as Record<string, (amazon: boolean) => string>,
  competency: {
    algorithmic_problem_solving: "Solving problems step by step",
    coding_quality: "Writing careful code and handling edge cases",
    technical_communication: "Explaining technical choices clearly",
    system_design: "Designing systems",
    behavioural_examples: "Telling examples from your own work",
  } as Record<string, string>,
  reason: {
    IN_MANY_ROUNDS: "Part of more than one practice round in Mirror",
    IN_ONE_ROUND: "Part of one practice round in Mirror",
    NO_CONFIRMED_EXAMPLE: "No example confirmed for it yet",
    SOME_EXAMPLES: "You have some examples for it",
    NOT_LINKED_TO_YOUR_PLAN: "Not linked to your plan yet",
    NOT_PRACTISED_YET: "Not practised yet",
    PRACTISED_RECENTLY: "Practised in the last two days",
    INTERVIEW_SOON: "Your interview is soon",
  } as Record<string, string>,
  rationale: {
    YOUR_STORY: "Uses one of your stories",
    MIRROR_SUGGESTED: "Written by Mirror",
    PUBLISHED_GUIDANCE_AREA: "Written by Mirror for an area the guidance mentions",
  } as Record<string, string>,
  claims: {
    "amazon.all.process_differs_by_role": "Amazon says its application and interview process differs from role to role.",
    "amazon.sde.sde_ii.process_sequence": `For SDE II, Amazon describes an application, then an ${OA}, then a loop of four interviews of about 55 minutes, then an outcome. At least one system design question is expected.`,
    "amazon.sde.sde_ii.system_design_expectation": "Amazon's SDE II guidance says to expect at least one software systems design question.",
    "amazon.sde.sde_ii.oa_components": `For SDE II, the ${OA} has a 90-minute coding part with two questions, a system design part and a work style part.`,
    "amazon.sde.sde_ii.oa_section_timing.interview_prep_page": "Amazon's interview prep page gives 20 minutes for the system design part and 8 minutes for the work style part.",
    "amazon.sde.sde_ii.oa_section_timing.oa_prep_page": "Amazon's OA prep page gives about 15 minutes for the system design part and about 10 minutes for the work style part.",
    "amazon.sde.sde_iii.process_sequence": "For SDE III, Amazon describes a 60-minute phone interview with a senior leader (half Leadership Principles, half coding and system design), then a loop of five interviews of about 55 minutes.",
    "amazon.sde.university.online_assessment": `For university hires, Amazon says the ${OA} is the first step and comes in one or two parts depending on the country. Its times are averages.`,
    "amazon.sde.all.interview_topics": "Amazon lists possible topics and says most technical interviews include coding and system design on a whiteboard. It asks you to confirm subjects with your recruiter.",
    "amazon.all.interview_loop_format": "Amazon says the interview loop is a set of separate conversations with current employees, each looking at different parts of your skills and experience.",
    "amazon.sde.sde_ii.oa_required": `Amazon says “everyone who wants to work as an SDE II at Amazon must complete an OA”. The completion window is seven days.`,
    "amazon.sde.sde_ii.loop_behavioural_questions": "For SDE II, Amazon says each interviewer typically asks two or three questions about past situations, tied to its Leadership Principles.",
    "amazon.sde.sde_iii.loop_behavioural_questions": "For SDE III, Amazon says each interviewer typically asks two or three questions about past situations, tied to its Leadership Principles.",
    "amazon.sde.sde_ii.coding_expectations": "For SDE II, Amazon asks for code written in its proper syntax (not pseudo code), and looks for code that is scalable, robust and carefully checked.",
    "amazon.sde.sde_iii.coding_expectations": "For SDE III, Amazon asks for code written in its proper syntax (not pseudo code), and looks for code that is scalable, robust and carefully checked.",
  } as Record<string, string>,
  conflicts: {
    "amazon.sde.sde_ii.oa_section_timing": "Two Amazon pages give different times for the system design and work style parts.",
  } as Record<string, string>,
  unknowns: {
    "amazon.sde.india_specific_process": "Mirror hasn't found published guidance on how these interviews run in India, so it won't borrow guidance written for other countries.",
    "amazon.sde.sde_i.experienced_process": "There's no published guide for an experienced SDE I process, so Mirror won't borrow one from another level.",
    "amazon.publication_dates": "None of these pages shows when it was published or updated. Each was checked on 4 Oct 2026.",
    "amazon.sde.sde_ii.oa_section_timing": "Amazon's pages disagree on the minutes for the system design and work style parts.",
    "amazon.sde.sde_ii.current_oa_format": "Reports of a different online coding round are unverified. Check your invitation email.",
    "amazon.bar_raiser": "Mirror has no approved source on bar raisers, so it says nothing about them.",
  } as Record<string, string>,
  source: {
    published: (company: string) => `From ${company}'s published guidance`,
    pattern: "Several people who interviewed recently describe this",
    inference: "Mirror's suggestion",
    forCountry: (country: string) => `for ${country}`,
    allCountries: "for all countries",
    allLevels: "for all levels",
    checked: (date: string) => `checked ${date}`,
    noPublishDate: "publication date not shown",
  },
  round: {
    back: "My plan",
    backToPlan: "Back to My plan",
    coversTitle: "What this Mirror practice covers",
    publishedGuidanceTitle: "What the published guidance says about this area",
    mirrorCoverageTitle: "Mirror practice coverage",
    coversSuggested: "Not yet researched for this target. Mirror suggests practising these parts:",
    cannotTitle: "What Mirror can and can't do here",
    practise: "Practise this round",
    practiseNote: "About 9 minutes, focused on this round.",
    prioritiesTitle: "Your priorities for this round",
    prioritiesEmpty: "Nothing from your plan maps to this round yet.",
    themesTitle: "Practice themes",
    themesLabel: "Mirror chooses original prompts when you start. Exact wording appears only during that practice.",
    shortPack: "You've seen every practice question Mirror has for this round in the last 30 days. New ones open up after that, or try another round.",
    packUnavailable: "Practice for this round isn't available right now. Your plan still works.",
    historyTitle: "Your practice for this round",
    historyEmpty: "You haven't practised this round yet.",
    practisedCount: (count: number) => (count === 1 ? "Practised once" : `Practised ${count} times`),
    readReflection: "Read your reflection",
    progressLink: "See your progress for this role",
    notFoundTitle: "We couldn't find that round.",
    notFoundBody: "It may not be part of this role's plan.",
    noTarget: "This role doesn't have a company and country set, so there's no round plan for it yet.",
    loadError: "This round didn't load. Nothing is lost. Please try again.",
  },
  practice: {
    roundLabel: "Round",
    roundFocus: (round: string, target: string | null) => (target ? `Mirror practice round: ${round} — for ${target}` : `Mirror practice round: ${round}`),
    shortPack: "You've seen every practice question Mirror has for this round in the last 30 days. Try another round, or come back later.",
    unavailable: "Round practice isn't available right now. You can still start a practice from My plan.",
  },
  setup: {
    summary: "Add where and what level (optional)",
    intro: "This helps Mirror show how interviews for this role usually run. Your practice works without it.",
    company: "Company",
    familyConfirm: "This is a Software Development Engineer (SDE) role",
    familyHelp: "Mirror only has interview notes for SDE roles so far.",
    level: "Level",
    levelHelp: "Your offer letter or recruiter email usually says. You can set it again later by adding the role again.",
    levelOptions: [
      { key: "sde_i", label: "SDE I" },
      { key: "sde_ii", label: "SDE II" },
      { key: "sde_iii", label: "SDE III" },
      { key: "not_sure", label: "Not sure yet" },
    ],
    country: "Country",
    countryOptions: [
      { key: "in", label: "India" },
      { key: "other", label: "Other" },
      { key: "not_sure", label: "Not sure yet" },
    ],
  },
} as const;

export type ResearchState = "RESEARCHED" | "GENERAL_ONLY" | "NOT_YET_RESEARCHED" | "NO_NOTES_FOR_COMPANY" | "UNAVAILABLE";

/** Which state the research part of a blueprint is in; anything not clearly served is unavailable. */
export function researchState(view: Pick<BlueprintView, "availability"> & Partial<BlueprintView>): ResearchState {
  if (view.availability !== "AVAILABLE" || !view.target || view.content_state !== "SERVED" || !view.match_state) return "UNAVAILABLE";
  if (view.match_state === "RESEARCHED") return "RESEARCHED";
  if (view.match_state === "GENERAL_ONLY") return "GENERAL_ONLY";
  return view.target.company_key ? "NOT_YET_RESEARCHED" : "NO_NOTES_FOR_COMPANY";
}

/** A missing or switched-off target service is quiet; anything else is a real error. */
export function failureKind(status: number): "UNAVAILABLE" | "ERROR" {
  return status === 404 || status === 501 || status === 503 ? "UNAVAILABLE" : "ERROR";
}

export function levelLabel(key: string | null | undefined) {
  return (key && targetCopy.level[key]) || targetCopy.levelNotSet;
}

export function countryLabel(target: Pick<TargetView, "geography_key" | "geography_label">) {
  if (target.geography_key === "in") return "India";
  if (target.geography_key === "other" || !target.geography_key) return null;
  return target.geography_label || null;
}

/** "Amazon · India · SDE II" — plain text, never a guessed level. */
export function targetLine(target: TargetView) {
  return [target.company_label, countryLabel(target) ?? targetCopy.countryNotSet, levelLabel(target.level_key)].join(" · ");
}

const roundKeyOf = (key: string) => key.replace(/^round\./, "");

export function roundLabel(labelOrKey: string): string | null {
  return targetCopy.rounds[roundKeyOf(labelOrKey)]?.title ?? null;
}

export function roundCovers(labelOrKey: string): string | null {
  return targetCopy.rounds[roundKeyOf(labelOrKey)]?.covers ?? null;
}

export function cannotDo(roundKey: string, amazon: boolean): string | null {
  return targetCopy.cannotDo[roundKeyOf(roundKey)]?.(amazon) ?? null;
}

export function competencyLabel(key: string): string | null {
  return targetCopy.competency[key] ?? null;
}

export function reasonLabel(code: string): string | null {
  return targetCopy.reason[code] ?? null;
}

export function claimMatchesTargetScope(claim: Pick<ClaimView, "scope">, target: TargetView): boolean {
  const scope = claim.scope;
  return Boolean(
    target.company_key && target.geography_key &&
    scope.company === target.company_key &&
    (scope.role_family === "all" || scope.role_family === target.role_family_key) &&
    (scope.level === "all" || scope.level === target.level_key) &&
    scope.geography === target.geography_key
  );
}

export function claimCopy(key: string, version: number, roundKey?: string): string | null {
  if (!Number.isInteger(version) || version !== 1) return null;
  if (key === "amazon.sde.sde_ii.process_sequence" && roundKey === "system_design") {
    return targetCopy.claims["amazon.sde.sde_ii.system_design_expectation"];
  }
  return targetCopy.claims[key] ?? null;
}

export function unknownCopy(key: string): string | null {
  return targetCopy.unknowns[key] ?? null;
}

export function conflictCopy(key: string): string | null {
  return targetCopy.conflicts[key] ?? null;
}

const COUNTRY: Record<string, string> = { in: "India" };

/** Source label as text: publisher, place, level, and how it is dated. */
export function sourceLabel(
  claim: Pick<ClaimView, "provenance_class" | "scope" | "dating" | "retrieved_at" | "published_at">,
  company: string,
) {
  const s = targetCopy.source;
  const parts: string[] = [];
  const geography = claim.scope?.geography;
  if (claim.provenance_class === "FACT") {
    parts.push(geography && geography !== "global" ? `${s.published(company)} ${s.forCountry(COUNTRY[geography] ?? geography.toUpperCase())}` : s.published(company));
    if (!geography || geography === "global") parts.push(s.allCountries);
  } else if (claim.provenance_class === "SUPPORTED_PATTERN") {
    parts.push(s.pattern);
  } else {
    parts.push(s.inference);
  }
  const level = claim.scope?.level;
  parts.push(level && level !== "all" ? `for ${levelLabel(level)}` : s.allLevels);
  if (claim.retrieved_at) parts.push(s.checked(shortDate(claim.retrieved_at)));
  if (!claim.published_at) parts.push(s.noPublishDate);
  return parts.join(" · ");
}

export function planHref(roleProfileId: string) {
  return `/plan?role=${encodeURIComponent(roleProfileId)}`;
}

export function roundHref(roleProfileId: string, roundKey: string) {
  return `/plan/rounds/${encodeURIComponent(roundKey)}?role=${encodeURIComponent(roleProfileId)}`;
}

/** Into the existing practice start, with the role, target and round pinned in the URL. */
export function roundPracticeHref({
  roleName,
  roleProfileId,
  targetId,
  roundKey,
}: {
  roleName: string;
  roleProfileId: string;
  targetId: string;
  roundKey: string;
}) {
  const params = new URLSearchParams({
    role: roleName,
    mode: "FOCUSED_PRACTICE",
    focus: "role",
    role_profile_id: roleProfileId,
    target: targetId,
    round: roundKey,
  });
  return `/practice/start?${params.toString()}`;
}
