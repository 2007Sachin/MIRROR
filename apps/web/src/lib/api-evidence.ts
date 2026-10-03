/**
 * Career Evidence: the reviewed list of your work that every guidance surface reads
 * (contract in docs/architecture/REDESIGN_BUILD.md). Built on the one authenticated `request`.
 */
import { request } from "@/lib/api";

export type EvidenceKind = "ACHIEVEMENT" | "PROJECT" | "RESPONSIBILITY" | "SKILL";
export type EvidenceStatus = "PENDING" | "APPROVED" | "REMOVED";
export type EvidenceState = "NO_RESUME" | "READING" | "UNREADABLE" | "READY";

export type EvidenceItem = {
  id: string;
  kind: EvidenceKind;
  title: string;
  detail: string | null;
  outcome: string | null;
  metric: string | null;
  tools: string[];
  source_label: string | null;
  status: EvidenceStatus;
  edited: boolean;
  updated_at: string;
};

export type EvidenceList = { state: EvidenceState; items: EvidenceItem[] };
export type EvidenceEdit = Partial<Pick<EvidenceItem, "status" | "title" | "detail" | "outcome" | "metric">>;

export function getEvidence() {
  return request<EvidenceList>("/api/v1/career-evidence");
}

export function updateEvidence(id: string, values: EvidenceEdit) {
  return request<EvidenceItem>(`/api/v1/career-evidence/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
}

export function approveEvidence(ids: string[]) {
  return request<unknown>("/api/v1/career-evidence/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
}
