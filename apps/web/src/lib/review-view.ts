/**
 * The full review of one practice.
 *
 * The plain-language reading of a review (what came through, what to improve, what
 * to practice next) is produced once by the backend and fetched from
 * `GET /api/v1/sessions/{id}/review`, so this page and the Home page always agree.
 * What is left here is presentation: pairing questions with answers, and attaching
 * the report's own notes to the answer they came from.
 */
import type { PracticeChoice, PublicInterviewTurn, ReportEvidence, ReportResponse, SessionReview } from "@/lib/api";
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

/**
 * The one practice a review points to next: a quick drill on the review's own growth
 * area (decided on the server). Null when the review names no area, and the page then
 * lets the person choose instead of inventing one.
 */
export function practiceNext(review: SessionReview | null): PracticeChoice | null {
  const focus = review?.practice_focus;
  return focus ? { mode: "QUICK_DRILL", focus, theme: null } : null;
}

// ------------------------------------------------------------------- your answers

export type AnswerBlock = {
  id: string;
  answerTurnId: string | null;
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
      answerTurnId: answer?.id ?? null,
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

// ------------------------------------------------------------------- review -> retry

export type RetryTarget = { answerTurnId: string; question: string; answer: string };

/**
 * Which answer each "needs more work" item can be retried on. An item is matched to an
 * answer the review itself marked as "could be clearer", in order, one answer per item.
 * When no such answer exists the item gets no retry, and offers practice instead.
 */
export function retryTargets(itemCount: number, blocks: AnswerBlock[]): Array<RetryTarget | null> {
  const candidates = blocks.filter((block) => block.answerTurnId && block.answer && block.couldBeClearer.length);
  return Array.from({ length: itemCount }, (_, index) => {
    const block = candidates[index];
    return block && block.answerTurnId && block.answer
      ? { answerTurnId: block.answerTurnId, question: block.question, answer: block.answer }
      : null;
  });
}
