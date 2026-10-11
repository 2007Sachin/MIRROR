/**
 * Review presentation helpers with no runtime imports, so they can be unit-tested directly
 * (apps/web/tests/review-groups.test.mjs). Grouping and time formatting only: every value
 * comes from the report as the backend returned it.
 */
import type { ReportResponse } from "@/lib/api";

// ------------------------------------------------------------------- what came through

/** The report's own groups, in the order a person reads them: what landed first, open questions last. */
const CLAIM_GROUP_ORDER = ["held", "partially_held", "walked_back", "contradicted", "insufficient_evidence", "unverified"] as const;
export type ClaimGroupKey = (typeof CLAIM_GROUP_ORDER)[number];
export type ClaimGroup = { key: ClaimGroupKey; claims: ReportResponse["claims_audit"][ClaimGroupKey] };

/**
 * What the person shared and how it came through, grouped exactly as the backend grouped it.
 * Empty groups are left out; "not enough to say yet" stays its own group and is never merged away.
 */
export function claimGroups(report: ReportResponse | null): ClaimGroup[] {
  if (!report) return [];
  return CLAIM_GROUP_ORDER.map((key) => ({ key, claims: report.claims_audit[key] ?? [] })).filter((group) => group.claims.length > 0);
}

/** A quote's moment in the conversation as m:ss, or null when the backend recorded no time. */
export function timecode(ms: number | null): string | null {
  if (ms === null || !Number.isFinite(ms) || ms < 0) return null;
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
