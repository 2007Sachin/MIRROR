"use client";

import { ArrowRight, Check, FileText, LockKey } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ApiError, mirrorApi, uploadResumeDocument } from "@/lib/api";
import {
  describeFileRejection,
  friendlyAnalysisError,
  friendlyDocumentError,
  maximumFileSizeMb,
} from "@/lib/documents";
import { Reveal } from "@/components/motion/reveal";
import "@/styles/sessions.css";

/**
 * Preparing a diagnostic needs role intelligence and resume intelligence in place
 * before the planner will accept the session, so this page runs the same pipeline
 * the onboarding flow does rather than creating a session the planner must reject.
 */
const pipelineStages = [
  "Reading the job description",
  "Benchmarking the role",
  "Uploading your resume",
  "Mapping your evidence",
  "Preparing your diagnostic",
] as const;

type StageIndex = 0 | 1 | 2 | 3 | 4;

export default function NewSessionPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<StageIndex | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [targetRole, setTargetRole] = useState("");

  useEffect(() => {
    const role = new URLSearchParams(window.location.search).get("role");
    if (role) setTargetRole(role);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const resume = form.get("resume");
    const role = String(form.get("target_role")).trim();
    const jdText = String(form.get("jd_text")).trim();

    if (!(resume instanceof File) || resume.size === 0) {
      setError("Choose a PDF or DOCX resume.");
      return;
    }
    const rejection = describeFileRejection(resume, "resume");
    if (rejection) {
      setError(rejection);
      return;
    }

    setBusy(true);
    try {
      // Role intelligence: the planner requires a completed analysis whose target
      // role matches this session, and completing one repoints the profile at it.
      setStage(0);
      const roleBrief = await mirrorApi.createJobDescription(jdText);

      setStage(1);
      let roleAnalysis;
      try {
        roleAnalysis = await mirrorApi.analyzeRole({
          target_role: role,
          job_description_document_id: roleBrief.id,
        });
      } catch (reason) {
        throw new PipelineError(friendlyAnalysisError(reason, "role"), reason);
      }
      if (roleAnalysis.latest_analysis?.status !== "COMPLETED") {
        throw new PipelineError("Mirror could not finish the role benchmark. Try again in a moment.");
      }

      // Resume intelligence: the session-scoped upload only stores a file, so the
      // resume has to become a real document before it can be analysed.
      setStage(2);
      setUploadProgress(0);
      let resumeDocument;
      try {
        resumeDocument = await uploadResumeDocument(resume, setUploadProgress);
      } catch (reason) {
        throw new PipelineError(friendlyDocumentError(reason, "resume"), reason);
      } finally {
        setUploadProgress(null);
      }

      setStage(3);
      let resumeAnalysis;
      try {
        resumeAnalysis = await mirrorApi.analyzeResume(resumeDocument.id);
      } catch (reason) {
        throw new PipelineError(friendlyAnalysisError(reason, "resume"), reason);
      }
      if (resumeAnalysis.status === "FAILED") {
        throw new PipelineError(
          resumeAnalysis.error_type === "document_parsing_failure"
            ? "Mirror could not extract enough text from this resume. Try a text-based PDF or DOCX file."
            : "Mirror could not build the evidence map from this resume. Try again in a moment.",
        );
      }
      if (resumeAnalysis.status !== "COMPLETED") {
        throw new PipelineError("Evidence mapping is still in progress. Try again in a moment.");
      }

      setStage(4);
      const session = await mirrorApi.createSession(role, jdText);
      await mirrorApi.linkSessionDocuments(session.id, [resumeDocument.id, roleBrief.id]);
      await mirrorApi.prepare(session.id);
      router.push(`/sessions/${session.id}/brief`);
    } catch (caught) {
      if (caught instanceof PipelineError) setError(caught.message);
      else if (caught instanceof ApiError && caught.status === 401) setError("Your session expired. Please sign in again.");
      else setError(caught instanceof Error ? caught.message : "The session could not be created.");
      setBusy(false);
      setStage(null);
      setUploadProgress(null);
    }
  }

  return (
    <main id="main-content" className="shell py-12 sm:py-16">
      <div className="grid gap-12 lg:grid-cols-[.72fr_1.28fr]">
        <Reveal as="section">
          <p className="text-sm text-[var(--silver)]">New diagnostic</p>
          <h1 className="display mt-4 text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">Give Mirror the evidence it needs.</h1>
          <p className="mt-6 max-w-[42ch] leading-7 text-[var(--silver)]">Your resume sets the claims to examine. The job description sets the competencies to investigate.</p>
          <div className="sn-intro-note">
            <LockKey size={20} className="mt-0.5 shrink-0 text-[var(--pulse)]" />
            <p>Resumes and interview data are isolated per candidate and are not intentionally used to train third-party models.</p>
          </div>
        </Reveal>

        <form onSubmit={submit} className="space-y-7 border-t hairline pt-7" aria-busy={busy}>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Target role</span>
            <input className="field" name="target_role" value={targetRole} onChange={(event) => setTargetRole(event.target.value)} required minLength={2} maxLength={160} placeholder="Data Analyst" disabled={busy} />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Resume</span>
            <span className="field flex cursor-pointer items-center gap-3 text-[var(--silver)]">
              <FileText size={20} /> <span>PDF or DOCX, up to {maximumFileSizeMb} MB</span>
              <input className="sr-only" name="resume" type="file" required accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" disabled={busy} />
            </span>
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Job description</span>
            <textarea className="field min-h-56 resize-y" name="jd_text" required minLength={50} maxLength={80000} placeholder="Paste the responsibilities, requirements, and role context." disabled={busy} />
          </label>

          {stage !== null && (
            <div className="sn-pipeline" role="status" aria-live="polite">
              <div className="sn-pipeline-headline">
                <span>
                  {pipelineStages[stage]}
                  {stage === 2 && uploadProgress !== null ? ` — ${uploadProgress}%` : null}
                </span>
                <span className="sn-pipeline-progress">
                  Step {stage + 1} of {pipelineStages.length}
                </span>
              </div>
              <p className="sn-pipeline-note">
                Mirror is benchmarking the role and mapping your evidence against it. This usually takes under a minute.
              </p>
              <ol className="sn-pipeline-stages">
                {pipelineStages.map((label, index) => (
                  <li
                    key={label}
                    className={`sn-pipeline-stage ${index < stage ? "is-done" : index === stage ? "is-current" : ""}`}
                  >
                    {index < stage ? (
                      <span className="sn-pipeline-marker"><Check size={15} className="text-[var(--pulse)]" /></span>
                    ) : index === stage ? (
                      <span className="sn-pipeline-marker"><span className="sn-pipeline-dot live-dot" aria-hidden="true" /></span>
                    ) : (
                      <span className="sn-pipeline-marker">{String(index + 1).padStart(2, "0")}</span>
                    )}
                    {label}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {error ? <p role="alert" className="border-l-2 border-red-400 pl-3 text-sm text-red-200">{error}</p> : null}
          <button className="button-primary w-full sm:w-auto" disabled={busy}>
            {busy ? "Preparing diagnostic..." : "Continue to pre-brief"} {!busy && <ArrowRight size={18} />}
          </button>
        </form>
      </div>
    </main>
  );
}

/** Carries an already-humanised message so the submit handler does not re-map it. */
class PipelineError extends Error {
  constructor(message: string, readonly reason?: unknown) {
    super(message);
    this.name = "PipelineError";
  }
}
