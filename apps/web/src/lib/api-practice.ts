import { request, type Session } from "@/lib/api";

/**
 * Discards a practice that has not finished (a draft or an active one). It gets no review
 * and never appears as previous practice. Owner-only and idempotent on the server; a practice
 * that already reached its review answers 409.
 */
export function abandonPractice(sessionId: string) {
  return request<Session>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/abandon`, { method: "POST" });
}
