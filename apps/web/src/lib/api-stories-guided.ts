/**
 * Guided stories and Dig Deeper feedback. Built on the one authenticated `request`.
 */
import { request, type PressureQuestionKind } from "@/lib/api";
import { getEvidence, type EvidenceItem } from "@/lib/api-evidence";

/** The answer checks, told as three parts. Deterministic on the server; never a grade. */
export type AnswerFeedback = {
  checks: Array<{ key: string; present: boolean; text: string }>;
  follow_up: string | null;
  clear: string[];
  missing: string | null;
  next_sentence: string;
};

export function answerFeedback(kind: PressureQuestionKind, answer: string) {
  return request<AnswerFeedback>("/api/v1/answer-checks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, answer }),
  });
}

/** One of your experience items, only if you have approved it. Anything else is null. */
export async function approvedEvidenceItem(id: string): Promise<EvidenceItem | null> {
  const { items } = await getEvidence();
  return items.find((item) => item.id === id && item.status === "APPROVED") ?? null;
}
