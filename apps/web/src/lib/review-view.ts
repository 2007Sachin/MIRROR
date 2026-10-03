/**
 * The full review of one practice.
 *
 * The plain-language reading of a review (what landed well, the one thing to strengthen,
 * what to try next) is produced once by the backend and fetched from
 * `GET /api/v1/sessions/{id}/review`, so this page and the Home page always agree.
 * What is left here is presentation: pairing questions with answers, and attaching
 * the report's own notes to the answer they came from.
 */
import type { PracticeChoice, PublicInterviewTurn, ReportEvidence, ReportResponse, SessionReview } from "@/lib/api";
import { developmentState } from "@/lib/dashboard-view";
import { focusFor } from "@/lib/practice-view";
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

export type Strengthen = { title: string; note: string; from: string | null; need: string | null };

/**
 * The one thing to strengthen: the review's first improvement, which is its growth area when
 * it has one. The role need is the practice area the server matched to that growth area.
 */
export function strengthenItem(review: SessionReview | null): Strengthen | null {
  const first = review?.improvements[0];
  if (!first) return null;
  return { title: first.title, note: first.note, from: first.from_label, need: focusFor(review.practice_focus)?.title ?? null };
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

// ------------------------------------------------------------------- review -> answers

export type AnswerTarget = { answerTurnId: string; question: string; answer: string; quote: string | null };

/**
 * Which answer each reflection item came from. Items are matched, in order and one answer
 * each, to answers the review itself marked the same way: "cameThrough" for what landed well,
 * "couldBeClearer" for what to strengthen (and retry). With no such answer the item stands
 * on its own; nothing is attached that the review did not record.
 */
export function answerTargets(itemCount: number, blocks: AnswerBlock[], notes: "cameThrough" | "couldBeClearer"): Array<AnswerTarget | null> {
  const matching = blocks.filter((block) => block.answerTurnId && block.answer && block[notes].length);
  return Array.from({ length: itemCount }, (_, index) => {
    const block = matching[index];
    return block && block.answerTurnId && block.answer
      ? { answerTurnId: block.answerTurnId, question: block.question, answer: block.answer, quote: block[notes][0]?.quote ?? null }
      : null;
  });
}
