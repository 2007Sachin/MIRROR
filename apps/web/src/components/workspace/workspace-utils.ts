import type { MirrorDocument } from "@/lib/api";
import { evidenceCategory, evidenceCategoryLabel } from "@/components/workspace/evidence-types";

export function formatWorkspaceDate(value: string | null) {
  if (!value) return "In progress";
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
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
