"use client";

import { ArrowLeft, FileText, UploadSimple } from "@phosphor-icons/react";
import { ChangeEvent, useRef, useState } from "react";

import { StepHeading, type Report } from "@/components/onboarding/shared";
import { ApiError, mirrorApi, uploadResumeDocument, type MirrorDocument } from "@/lib/api";
import { onboardingCopy } from "@/lib/copy-onboarding";
import { describeFileRejection, friendlyAnalysisError, friendlyDocumentError, maximumFileSize } from "@/lib/documents";

const t = onboardingCopy.experience;

/** Makes sure the resume has been read once; a resume that cannot be read still moves on (the review step explains). */
async function readOnce(documentId: string) {
  const existing = await mirrorApi.resumeAnalysis(documentId).catch((reason: unknown) => {
    if (reason instanceof ApiError && reason.status === 404) return null;
    throw reason;
  });
  if (existing?.status === "COMPLETED" || existing?.status === "PROCESSING") return;
  await mirrorApi.analyzeResume(documentId);
}

export function ExperienceStep({
  saved,
  report,
  onBack,
  onReady,
}: {
  saved: MirrorDocument | null;
  report: Report;
  onBack: () => void;
  onReady: (resume: MirrorDocument) => Promise<void>;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [reading, setReading] = useState(false);
  const busy = reading || progress !== null;

  async function choose(resume: MirrorDocument) {
    report("");
    setReading(true);
    try {
      await readOnce(resume.id);
      await onReady(resume);
    } catch (reason) {
      report(friendlyAnalysisError(reason, "resume"), reason);
    } finally {
      setReading(false);
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const rejection = describeFileRejection(file, "resume");
    if (rejection) return report(rejection);
    report("");
    setProgress(0);
    let document: MirrorDocument;
    try {
      document = await uploadResumeDocument(file, setProgress);
    } catch (reason) {
      return report(friendlyDocumentError(reason, "resume"), reason);
    } finally {
      setProgress(null);
    }
    await choose(document);
  }

  const pick = () => fileInput.current?.click();

  return (
    <section className="ob-step" aria-busy={busy}>
      <StepHeading title={t.title} intro={t.intro} />
      {saved ? (
        <div className="op-card op-saved">
          <FileText size={22} aria-hidden="true" />
          <div>
            <p className="op-muted">{t.savedLabel}</p>
            <p className="op-strong">{saved.original_filename ?? saved.title ?? t.savedLabel}</p>
          </div>
        </div>
      ) : (
        <p className="op-muted">{t.fileHint(Math.round(maximumFileSize / 1024 / 1024))}</p>
      )}
      <input ref={fileInput} className="sr-only" type="file" tabIndex={-1} aria-hidden="true" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={upload} />
      {progress !== null && (
        <>
          <p role="status" aria-live="polite" className="op-muted">{t.uploading(progress)}</p>
          <div className="ob-upload-progress" role="progressbar" aria-label={t.uploadProgress} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
            <span style={{ width: `${progress}%` }} />
          </div>
        </>
      )}
      {reading && (
        <div className="op-card" role="status" aria-live="polite">
          <p className="op-strong">{t.reading}</p>
          <p className="op-muted">{t.readingNote}</p>
        </div>
      )}
      <div className="ob-actions">
        <button type="button" className="ob-back op-target" onClick={onBack} disabled={busy}>
          <ArrowLeft size={17} aria-hidden="true" /> {t.back}
        </button>
        <div className="op-action-group">
          {saved ? (
            <>
              <button type="button" className="button-secondary op-target" onClick={pick} disabled={busy}>
                <UploadSimple size={18} aria-hidden="true" /> {t.replace}
              </button>
              <button type="button" className="button-primary op-target" onClick={() => void choose(saved)} disabled={busy}>
                {reading ? t.reading : t.useSaved}
              </button>
            </>
          ) : (
            <button type="button" className="button-primary op-target" onClick={pick} disabled={busy}>
              <UploadSimple size={18} aria-hidden="true" /> {reading ? t.reading : t.upload}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
