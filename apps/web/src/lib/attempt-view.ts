/**
 * Try again presentation. The comparison is made on the server; every line here is
 * derived from its per-aspect PRESENT/ABSENT pairs, so nothing is claimed that the two
 * answers don't visibly show.
 */
import type { AnswerAspect, AnswerAttempt } from "@/lib/api";
import { tryAgain as t } from "@/lib/copy";

type Comparison = NonNullable<AnswerAttempt["comparison"]>;

export function gainedLines(comparison: Comparison) {
  return comparison.came_through_more_clearly.map((aspect) => t.gained[aspect]);
}

export function missingLines(comparison: Comparison) {
  return comparison.still_missing.map((aspect) => t.missing[aspect]);
}

export type AttemptColumn = { cameThrough: string[]; unclear: string[] };

/** The before/after view: what each attempt contained, in the same order. */
export function beforeAfter(comparison: Comparison): { first: AttemptColumn; latest: AttemptColumn } {
  const label = (aspect: AnswerAspect) => t.aspect[aspect];
  return {
    first: {
      cameThrough: comparison.changes.filter((c) => c.first === "PRESENT").map((c) => label(c.aspect)),
      unclear: comparison.changes.filter((c) => c.first === "ABSENT").map((c) => label(c.aspect)),
    },
    latest: {
      cameThrough: comparison.changes.filter((c) => c.latest === "PRESENT").map((c) => label(c.aspect)),
      unclear: comparison.changes.filter((c) => c.latest === "ABSENT").map((c) => label(c.aspect)),
    },
  };
}

/** Attempts grouped by the answer they retry, newest last. */
export function attemptsByAnswer(attempts: AnswerAttempt[]): Map<string, AnswerAttempt[]> {
  const grouped = new Map<string, AnswerAttempt[]>();
  for (const attempt of [...attempts].sort((left, right) => left.sequence - right.sequence)) {
    const list = grouped.get(attempt.original_turn_id) ?? [];
    list.push(attempt);
    grouped.set(attempt.original_turn_id, list);
  }
  return grouped;
}

export function latestAttempt(attempts: AnswerAttempt[] | undefined) {
  return attempts && attempts.length ? attempts[attempts.length - 1] : null;
}
