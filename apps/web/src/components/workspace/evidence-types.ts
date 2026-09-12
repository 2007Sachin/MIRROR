import type { DocumentType, EvidenceCategory, MirrorDocument } from "@/lib/api";

export const EVIDENCE_CATEGORIES: ReadonlyArray<{
  value: EvidenceCategory;
  label: string;
  plural: string;
}> = [
  { value: "RESUME", label: "Resume", plural: "Resumes" },
  { value: "PROJECT", label: "Project", plural: "Projects" },
  { value: "CASE_STUDY", label: "Case study", plural: "Case studies" },
  { value: "CERTIFICATE", label: "Certificate", plural: "Certificates" },
  { value: "PORTFOLIO", label: "Portfolio", plural: "Portfolios" },
  { value: "COVER_LETTER", label: "Cover letter", plural: "Cover letters" },
  { value: "ACHIEVEMENT", label: "Achievement", plural: "Achievements" },
  { value: "WORK_SAMPLE", label: "Work sample", plural: "Work samples" },
  { value: "ROLE_BRIEF", label: "Role brief", plural: "Role briefs" },
  { value: "OTHER", label: "Other", plural: "Other" },
] as const;

export function evidenceCategory(document: MirrorDocument): EvidenceCategory {
  if (document.evidence_category) return document.evidence_category;
  const legacy: Record<DocumentType, EvidenceCategory> = {
    RESUME: "RESUME",
    JOB_DESCRIPTION: "ROLE_BRIEF",
    PROJECT: "PROJECT",
  };
  return legacy[document.document_type];
}

export function evidenceCategoryLabel(category: EvidenceCategory) {
  return EVIDENCE_CATEGORIES.find((option) => option.value === category)?.label ?? "Other";
}
