import { ApiError } from "@/lib/api";

export const PDF_MIME = "application/pdf";
export const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
export const allowedMimeTypes = new Set([PDF_MIME, DOCX_MIME]);

const configuredMaximum = Number(process.env.NEXT_PUBLIC_RESUME_MAX_FILE_SIZE_BYTES ?? 8 * 1024 * 1024);
export const maximumFileSize =
  Number.isFinite(configuredMaximum) && configuredMaximum > 0 ? configuredMaximum : 8 * 1024 * 1024;

export const maximumFileSizeMb = Math.round(maximumFileSize / 1024 / 1024);

export type DocumentKind = "resume" | "role brief";
export type AnalysisKind = "resume" | "role";

/** Returns an empty string when the file is acceptable, otherwise the reason it is not. */
export function describeFileRejection(file: File, kind: DocumentKind): string {
  if (!allowedMimeTypes.has(file.type)) return `Choose a PDF or DOCX ${kind} file.`;
  if (file.size > maximumFileSize) return `The ${kind} is larger than the ${maximumFileSizeMb} MB limit.`;
  return "";
}

export function friendlyDocumentError(reason: unknown, kind: DocumentKind) {
  if (reason instanceof ApiError) {
    if (reason.status === 413) return `The ${kind} is larger than the ${maximumFileSizeMb} MB limit.`;
    if (reason.status === 415) return `Choose a genuine PDF or DOCX ${kind} file.`;
    if (reason.status === 422 && kind === "role brief") return "Mirror could not extract text from that role brief. Try a text-based PDF or DOCX file.";
    if (reason.status === 401) return "Your session expired. Please sign in again.";
  }
  return `Mirror could not upload your ${kind}. Check your connection and try again.`;
}

export function friendlyAnalysisError(reason: unknown, kind: AnalysisKind) {
  if (reason instanceof ApiError) {
    if (reason.status === 409) return `Mirror could not use the selected ${kind} context. Review it and try again.`;
    if (reason.status === 422) return `Mirror could not read enough usable ${kind} information. Review the source and try again.`;
    if (reason.status === 503) return `${kind === "resume" ? "Evidence mapping" : "Role analysis"} is temporarily unavailable. Your saved information is safe.`;
  }
  return `Mirror could not complete the ${kind} analysis. Check your connection and try again.`;
}
