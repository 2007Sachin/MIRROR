/**
 * The full review of one practice.
 *
 * The plain-language reading of a review (what came through, what to improve, what
 * to practice next) is produced once by the backend and fetched from
 * `GET /api/v1/sessions/{id}/review`, so this page and the Home page always agree.
 * What is left here is presentation: pairing questions with answers, and attaching
 * the report's own notes to the answer they came from.
 */
import type { PublicInterviewTurn, ReportEvidence, ReportResponse, SessionReview } from "@/lib/api";
import { developmentState } from "@/lib/dashboard-view";
import { areaLabel } from "@/lib/progress-view";

export type ReviewStrength = { key: string; label: string; note: string };

/** Areas the review says came through clearly, in the same words as everywhere else. */
export function reviewStrengths(review: SessionReview | null, limit = 3): ReviewStrength[] {
  if (!review) return [];
  return review.dimensions
    .filter((dimension) => developmentState(dimension.state) === "Coming through clearly")
    .slice(0, limit)
    .map((dimension) => ({ key: dimension.key, label: areaLabel(dimension.key), note: dimension.note }));
}

/** Which focus the "practice this" action should carry, from the review's own area. */
const FOCUS_FOR_ROOT_CAUSE: Record<string, string> = {
  OWNERSHIP_SPECIFICITY: "impact",
  OUTCOME_EVIDENCE: "impact",
  TECHNICAL_DEPTH: "decisions",
  ANSWER_STRUCTURE: "story",
  COMPOSURE_UNDER_PROBE: "full",
  ROLE_SKILL_GAP: "role",
};

export function focusForReview(report: ReportResponse | null) {
  return (report && FOCUS_FOR_ROOT_CAUSE[report.root_cause]) || "full";
}

// ------------------------------------------------------------------- your answers

export type AnswerBlock = {
  id: string;
  question: string;
  answer: string | null;
  cameThrough: ReportEvidence[];
  couldBeClearer: ReportEvidence[];
};

/**
 * Each interviewer question with the answer that followed it, in order. Notes come
 * from the report's own quotes: a quote is attached to the answer it was taken from,
 * and nothing is attached that the report did not record.
 */
export function answerBlocks(turns: PublicInterviewTurn[], report: ReportResponse | null): AnswerBlock[] {
  const byTurn = new Map<string, ReportEvidence[]>();
  if (report) {
    const everyQuote = [
      ...Object.values(report.claims_audit).flatMap((claims) => claims.flatMap((claim) => claim.evidence)),
      ...report.skill_assessments.flatMap((skill) => skill.evidence),
    ];
    for (const quote of everyQuote) {
      if (!quote.turn_id) continue;
      const bucket = byTurn.get(quote.turn_id);
      if (bucket) bucket.push(quote);
      else byTurn.set(quote.turn_id, [quote]);
    }
  }

  const ordered = [...turns].sort((left, right) => left.turn_index - right.turn_index);
  const blocks: AnswerBlock[] = [];
  for (let index = 0; index < ordered.length; index += 1) {
    const turn = ordered[index];
    if (turn.speaker !== "INTERVIEWER" || !turn.text.trim()) continue;
    const next = ordered[index + 1];
    const answer = next && next.speaker === "CANDIDATE" ? next : null;
    const quotes = answer ? byTurn.get(answer.id) ?? [] : [];
    blocks.push({
      id: turn.id,
      question: turn.text,
      answer: answer?.text?.trim() || null,
      cameThrough: dedupe(quotes.filter((quote) => quote.direction === "SUPPORTS")),
      couldBeClearer: dedupe(quotes.filter((quote) => quote.direction === "WEAKENS")),
    });
  }
  return blocks;
}

function dedupe(quotes: ReportEvidence[]) {
  const seen = new Set<string>();
  return quotes.filter((quote) => {
    if (seen.has(quote.quote)) return false;
    seen.add(quote.quote);
    return true;
  });
}
