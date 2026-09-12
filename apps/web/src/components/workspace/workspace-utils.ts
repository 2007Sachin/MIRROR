import type { DashboardDiagnostic, MirrorDocument } from "@/lib/api";
import { evidenceCategory, evidenceCategoryLabel } from "@/components/workspace/evidence-types";

export type DiagnosticTone = "active" | "complete" | "failed" | "neutral";

export function formatWorkspaceDate(value: string | null) {
  if (!value) return "In progress";
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function diagnosticStatus(diagnostic: DashboardDiagnostic) {
  if (diagnostic.diagnostic_available) return "Completed";
  if (diagnostic.assessment?.status === "FAILED") return "Failed";
  if (diagnostic.assessment?.status === "PROCESSING" || diagnostic.assessment?.status === "PENDING") {
    return "Evaluating";
  }
  if (diagnostic.interview_status === "ACTIVE") return "Interview in progress";
  if (diagnostic.interview_status === "READY") return "Interview ready";
  if (diagnostic.interview_status === "COMPLETED" || diagnostic.interview_status === "ASSESSING") {
    return "Evaluating";
  }
  if (diagnostic.interview_status === "FAILED") return "Failed";
  return "Setup in progress";
}

export function diagnosticTone(diagnostic: DashboardDiagnostic): DiagnosticTone {
  if (diagnostic.diagnostic_available) return "complete";
  if (diagnostic.assessment?.status === "FAILED" || diagnostic.interview_status === "FAILED") return "failed";
  if (["ACTIVE", "READY", "ASSESSING", "COMPLETED"].includes(diagnostic.interview_status)) return "active";
  return "neutral";
}

export function diagnosticDestination(diagnostic: DashboardDiagnostic) {
  if (diagnostic.diagnostic_available) return `/app/report/${diagnostic.id}`;
  if (diagnostic.interview_status === "READY" || diagnostic.interview_status === "ACTIVE") {
    return `/app/interview/${diagnostic.id}`;
  }
  return `/sessions/${diagnostic.id}/brief`;
}

export function documentLabel(document: MirrorDocument) {
  return evidenceCategoryLabel(evidenceCategory(document));
}

export function displayDocumentName(document: MirrorDocument) {
  if (document.title) return document.title;
  if (document.original_filename) return document.original_filename;
  if (document.document_type === "JOB_DESCRIPTION") return "Pasted role brief";
  return documentLabel(document);
}
