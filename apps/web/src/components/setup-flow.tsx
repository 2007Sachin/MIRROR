"use client";

import { ArrowRight, Check, CheckCircle, FileText, PencilSimple, UploadSimple } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { ChangeEvent, useEffect, useRef, useState } from "react";
import {
  ApiError,
  mirrorApi,
  uploadResumeDocument,
  type MirrorDocument,
  type ResumeAnalysis,
  type RoleAnalysis,
} from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase";

const PDF_MIME = "application/pdf";
const DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const allowedMimeTypes = new Set([PDF_MIME, DOCX_MIME]);
const configuredMaximum = Number(process.env.NEXT_PUBLIC_RESUME_MAX_FILE_SIZE_BYTES ?? 8 * 1024 * 1024);
const maximumFileSize = Number.isFinite(configuredMaximum) && configuredMaximum > 0 ? configuredMaximum : 8 * 1024 * 1024;
const selectionKey = "mirror.setup.document-selection";

type JdMode = "paste" | "none" | null;
type Selection = {
  resumeDocumentId?: string;
  jobDescriptionDocumentId?: string;
  jobDescriptionSkipped?: boolean;
  roleProfileId?: string;
};

function loadSelection(): Selection {
  try {
    return JSON.parse(window.localStorage.getItem(selectionKey) ?? "{}") as Selection;
  } catch {
    return {};
  }
}

function saveSelection(selection: Selection) {
  window.localStorage.setItem(selectionKey, JSON.stringify(selection));
}

function friendlyUploadError(reason: unknown) {
  if (reason instanceof ApiError) {
    if (reason.status === 413) return `Your resume is larger than the ${Math.round(maximumFileSize / 1024 / 1024)} MB limit.`;
    if (reason.status === 415) return "Choose a genuine PDF or DOCX resume file.";
    if (reason.status === 401) return "Your session expired. Please sign in again.";
  }
  return "Mirror could not upload your resume. Check your connection and try again.";
}

export function SetupFlow({ targetRole }: { targetRole: string }) {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<MirrorDocument[]>([]);
  const [resumeDocumentId, setResumeDocumentId] = useState<string | null>(null);
  const [jobDescriptionDocumentId, setJobDescriptionDocumentId] = useState<string | null>(null);
  const [resumeName, setResumeName] = useState("");
  const [jdMode, setJdMode] = useState<JdMode>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [savedJobDescription, setSavedJobDescription] = useState("");
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [savingJd, setSavingJd] = useState(false);
  const [loading, setLoading] = useState(true);
  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null);
  const [roleProfileId, setRoleProfileId] = useState<string | null>(null);
  const [roleAnalysis, setRoleAnalysis] = useState<RoleAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [reviewingClaim, setReviewingClaim] = useState<string | null>(null);
  const [correctionDrafts, setCorrectionDrafts] = useState<Record<string, string>>({});
  const [savingClaim, setSavingClaim] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    mirrorApi.documents()
      .then((rows) => {
        if (!active) return;
        setDocuments(rows);
        const stored = loadSelection();
        setRoleProfileId(stored.roleProfileId ?? null);
        const selectedResume = rows.find((row) => row.id === stored.resumeDocumentId && row.document_type === "RESUME" && row.status !== "FAILED")
          ?? rows.find((row) => row.document_type === "RESUME" && row.status !== "FAILED");
        const selectedJd = stored.jobDescriptionSkipped
          ? undefined
          : rows.find((row) => row.id === stored.jobDescriptionDocumentId && row.document_type === "JOB_DESCRIPTION" && row.status === "PROCESSED")
            ?? rows.find((row) => row.document_type === "JOB_DESCRIPTION" && row.status === "PROCESSED");
        if (selectedResume) {
          setResumeDocumentId(selectedResume.id);
          setResumeName(selectedResume.original_filename ?? "Uploaded resume");
        }
        if (selectedJd) {
          setJobDescriptionDocumentId(selectedJd.id);
          setJobDescription(selectedJd.raw_text ?? "");
          setSavedJobDescription(selectedJd.raw_text ?? "");
          setJdMode("paste");
        } else if (stored.jobDescriptionSkipped) {
          setJdMode("none");
        }
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiError && reason.status === 401) {
          router.replace("/login?reason=session_expired");
        } else if (active) {
          setError("Mirror could not load your saved documents. Refresh to try again.");
        }
      })
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [router]);

  useEffect(() => {
    if (!resumeDocumentId) {
      setAnalysis(null);
      return;
    }
    let active = true;
    mirrorApi.resumeAnalysis(resumeDocumentId)
      .then((value) => active && setAnalysis(value))
      .catch((reason: unknown) => {
        if (active && reason instanceof ApiError && reason.status === 401) {
          router.replace("/login?reason=session_expired");
        }
      });
    return () => { active = false; };
  }, [resumeDocumentId, router]);

  useEffect(() => {
    if (!roleProfileId) {
      setRoleAnalysis(null);
      return;
    }
    let active = true;
    mirrorApi.role(roleProfileId)
      .then((value) => active && setRoleAnalysis(value))
      .catch((reason: unknown) => {
        if (active && reason instanceof ApiError && reason.status === 401) {
          router.replace("/login?reason=session_expired");
        }
      });
    return () => { active = false; };
  }, [roleProfileId, router]);

  async function uploadResume(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    if (!allowedMimeTypes.has(file.type)) {
      setError("Choose a PDF or DOCX resume file.");
      event.target.value = "";
      return;
    }
    if (file.size > maximumFileSize) {
      setError(`Your resume is larger than the ${Math.round(maximumFileSize / 1024 / 1024)} MB limit.`);
      event.target.value = "";
      return;
    }

    setUploadProgress(0);
    try {
      const document = await uploadResumeDocument(file, setUploadProgress);
      setDocuments((current) => [document, ...current]);
      setResumeDocumentId(document.id);
      setAnalysis(null);
      setResumeName(document.original_filename ?? file.name);
      const stored = loadSelection();
      saveSelection({ ...stored, resumeDocumentId: document.id });
    } catch (reason) {
      setError(friendlyUploadError(reason));
      if (reason instanceof ApiError && reason.status === 401) {
        await getSupabaseBrowserClient().auth.signOut();
        router.replace("/login?reason=session_expired");
      }
    } finally {
      setUploadProgress(null);
      event.target.value = "";
    }
  }

  async function continueSetup() {
    if (!resumeDocumentId) return;
    let selectedJobDescriptionId = jobDescriptionDocumentId;
    setError("");
    if (jdMode === "paste") {
      const cleaned = jobDescription.trim();
      if (!cleaned) {
        setError("Paste a job description or choose “I don't have one”.");
        return;
      }
      setSavingJd(true);
      try {
        let selectedId = jobDescriptionDocumentId;
        if (!selectedId || cleaned !== savedJobDescription) {
          const document = await mirrorApi.createJobDescription(cleaned);
          selectedId = document.id;
          setDocuments((current) => [document, ...current]);
          setJobDescriptionDocumentId(document.id);
          setSavedJobDescription(document.raw_text ?? cleaned);
        }
        selectedJobDescriptionId = selectedId;
        saveSelection({ resumeDocumentId, jobDescriptionDocumentId: selectedId, jobDescriptionSkipped: false });
      } catch (reason) {
        if (reason instanceof ApiError && reason.status === 401) {
          await getSupabaseBrowserClient().auth.signOut();
          router.replace("/login?reason=session_expired");
        } else {
          setError("Mirror could not save that job description. Check your connection and try again.");
        }
        return;
      } finally {
        setSavingJd(false);
      }
    } else if (jdMode === "none") {
      saveSelection({ resumeDocumentId, jobDescriptionSkipped: true });
    } else {
      setError("Choose how you want to handle the target job description.");
      return;
    }
    setAnalyzing(true);
    try {
      const result = await mirrorApi.analyzeResume(resumeDocumentId);
      setAnalysis(result);
      if (result.status === "FAILED") {
        setError("Mirror could not read this resume yet. Try a text-based PDF or DOCX file.");
      } else if (result.status === "PROCESSING") {
        setError("This resume is already being analyzed. Check again in a moment.");
      } else {
        const role = await mirrorApi.analyzeRole({
          target_role: targetRole,
          ...(selectedJobDescriptionId ? { job_description_document_id: selectedJobDescriptionId } : {}),
          ...(roleProfileId ? { role_profile_id: roleProfileId } : {}),
        });
        setRoleAnalysis(role);
        setRoleProfileId(role.id);
        const stored = loadSelection();
        saveSelection({ ...stored, roleProfileId: role.id });
        if (role.latest_analysis?.status === "FAILED") {
          setError("Mirror could not build the role focus yet. Try again.");
        } else if (role.latest_analysis?.status === "PROCESSING") {
          setError("This role is already being analyzed. Check again in a moment.");
        }
      }
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        await getSupabaseBrowserClient().auth.signOut();
        router.replace("/login?reason=session_expired");
      } else {
        setError("Mirror could not analyze this resume. Check your connection and try again.");
      }
    } finally {
      setAnalyzing(false);
    }
  }

  async function reviewClaim(claimId: string, status: "CORRECT" | "NEEDS_CORRECTION") {
    if (!resumeDocumentId) return;
    const correction = correctionDrafts[claimId]?.trim();
    if (status === "NEEDS_CORRECTION" && (!correction || correction.length < 3)) {
      setError("Describe the correction before saving it.");
      return;
    }
    setError("");
    setSavingClaim(claimId);
    try {
      const updated = await mirrorApi.correctResumeClaim(
        resumeDocumentId,
        claimId,
        status,
        status === "NEEDS_CORRECTION" ? correction : undefined,
      );
      setAnalysis(updated);
      setReviewingClaim(null);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        await getSupabaseBrowserClient().auth.signOut();
        router.replace("/login?reason=session_expired");
      } else {
        setError("Mirror could not save that review. Try again.");
      }
    } finally {
      setSavingClaim(null);
    }
  }

  const selectedResume = documents.find((document) => document.id === resumeDocumentId);
  return (
    <main className="shell py-12 sm:py-20">
      <div className="mx-auto max-w-3xl">
        <p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--silver)]">Interview setup</p>
        <section className="mt-6 border-t hairline pt-8">
          <h1 className="display text-4xl font-semibold tracking-[-0.045em]">Resume</h1>
          <p className="mt-4 max-w-xl leading-7 text-[var(--silver)]">Let&apos;s understand what an interviewer will see before meeting you.</p>
          <input ref={fileInput} className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={uploadResume} />
          <button type="button" className="button-primary mt-7" onClick={() => fileInput.current?.click()} disabled={uploadProgress !== null || loading}>
            <UploadSimple size={18} /> {uploadProgress !== null ? `Uploading ${uploadProgress}%` : resumeDocumentId ? "Replace resume" : "Upload resume"}
          </button>
          {uploadProgress !== null && (
            <div className="mt-4 h-1 overflow-hidden rounded-full bg-[var(--line)]" role="progressbar" aria-valuenow={uploadProgress} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full bg-[var(--pulse)] transition-[width]" style={{ width: `${uploadProgress}%` }} />
            </div>
          )}
          {selectedResume && <p className="mt-4 flex items-center gap-2 text-sm text-[var(--silver)]"><Check size={17} className="text-[var(--pulse)]" /> {resumeName}</p>}
        </section>

        <section className={`mt-14 border-t hairline pt-8 transition-opacity ${resumeDocumentId ? "opacity-100" : "pointer-events-none opacity-40"}`} aria-disabled={!resumeDocumentId}>
          <h2 className="display text-3xl font-semibold tracking-[-0.04em]">Target job description</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--silver)]">Add the role you are preparing for, or continue without one.</p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <button type="button" aria-pressed={jdMode === "paste"} onClick={() => setJdMode("paste")} className={`flex min-h-16 items-center gap-3 rounded-lg border px-4 text-left font-semibold ${jdMode === "paste" ? "border-[var(--pulse)] bg-[rgba(79,209,165,.08)]" : "hairline"}`}><FileText size={20} /> Paste job description</button>
            <button type="button" aria-pressed={jdMode === "none"} onClick={() => setJdMode("none")} className={`min-h-16 rounded-lg border px-4 text-left font-semibold ${jdMode === "none" ? "border-[var(--pulse)] bg-[rgba(79,209,165,.08)]" : "hairline"}`}>I don&apos;t have one</button>
          </div>
          {jdMode === "paste" && <label className="mt-6 block"><span className="mb-2 block text-sm font-semibold">Job description</span><textarea className="field min-h-52 resize-y" value={jobDescription} onChange={(event) => setJobDescription(event.target.value)} maxLength={100000} placeholder="Paste the job description here…" /></label>}
        </section>

        {analysis?.status === "COMPLETED" && analysis.output && (
          <section className="mt-14 border-t hairline pt-8" aria-labelledby="mirror-found-title">
            <p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--pulse)]">Resume analysis · version {analysis.version}</p>
            <h2 id="mirror-found-title" className="display mt-4 text-4xl font-semibold tracking-[-0.045em]">Mirror found</h2>
            <div className="mt-6 grid grid-cols-3 gap-px overflow-hidden rounded-lg bg-[var(--line)]">
              {[
                [analysis.output.skills.length, "Skills"],
                [analysis.output.projects.length, "Projects"],
                [analysis.claims.length, "Claims"],
              ].map(([count, label]) => (
                <div key={label} className="bg-[var(--ink)] p-4 sm:p-6">
                  <p className="display text-3xl font-semibold">{count}</p>
                  <p className="mt-1 text-xs text-[var(--silver)]">{label}</p>
                </div>
              ))}
            </div>

            <div className="mt-8">
              <h3 className="text-sm font-semibold">Skills</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {analysis.output.skills.map((skill) => (
                  <span key={`${skill.name}-${skill.source_reference}`} className="rounded-full border hairline px-3 py-1.5 text-xs text-[var(--silver)]">{skill.name}</span>
                ))}
                {!analysis.output.skills.length && <p className="text-sm text-[var(--silver)]">No explicit skills were found.</p>}
              </div>
            </div>

            <div className="mt-8">
              <h3 className="text-sm font-semibold">Projects</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {analysis.output.projects.map((project) => (
                  <article key={`${project.project_name}-${project.source_reference}`} className="rounded-lg border hairline p-4">
                    <h4 className="font-semibold">{project.project_name}</h4>
                    <p className="mt-2 text-sm leading-6 text-[var(--silver)]">{project.description}</p>
                  </article>
                ))}
                {!analysis.output.projects.length && <p className="text-sm text-[var(--silver)]">No named projects were found.</p>}
              </div>
            </div>

            <div className="mt-8">
              <h3 className="text-sm font-semibold">Claims</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--silver)]">These are neutral statements found in your resume, not judgments about truthfulness.</p>
              <div className="mt-4 space-y-3">
                {analysis.claims.map((claim) => (
                  <article key={claim.id} className="rounded-lg border hairline p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="max-w-xl">
                        <p className="text-sm leading-6">{claim.claim_text}</p>
                        <p className="mono mt-2 text-[10px] uppercase tracking-[0.12em] text-[var(--silver)]">{claim.claim_type.replaceAll("_", " ")} · {claim.source_reference}</p>
                        {claim.review_status && (
                          <p className="mt-2 text-xs text-[var(--pulse)]">
                            {claim.review_status === "CORRECT" ? "Marked correct" : `Correction saved: ${claim.corrected_claim_text}`}
                          </p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <button type="button" className="button-secondary px-3 py-2 text-xs" disabled={savingClaim === claim.id} onClick={() => reviewClaim(claim.id, "CORRECT")}><CheckCircle size={15} /> Correct</button>
                        <button type="button" className="button-secondary px-3 py-2 text-xs" disabled={savingClaim === claim.id} onClick={() => setReviewingClaim(claim.id)}><PencilSimple size={15} /> Needs correction</button>
                      </div>
                    </div>
                    {reviewingClaim === claim.id && (
                      <div className="mt-4 border-t hairline pt-4">
                        <label className="block text-xs font-semibold" htmlFor={`correction-${claim.id}`}>What should this say?</label>
                        <textarea id={`correction-${claim.id}`} className="field mt-2 min-h-24 resize-y" value={correctionDrafts[claim.id] ?? claim.corrected_claim_text ?? ""} onChange={(event) => setCorrectionDrafts((current) => ({ ...current, [claim.id]: event.target.value }))} maxLength={2000} />
                        <button type="button" className="button-primary mt-3" disabled={savingClaim === claim.id} onClick={() => reviewClaim(claim.id, "NEEDS_CORRECTION")}>{savingClaim === claim.id ? "Saving…" : "Save correction"}</button>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </div>
          </section>
        )}

        {analysis?.status === "COMPLETED" && roleAnalysis?.latest_analysis?.status === "COMPLETED" && (
          <section className="mt-14 border-t hairline pt-8" aria-labelledby="setup-confirmation-title">
            <p className="mono text-[10px] uppercase tracking-[0.18em] text-[var(--pulse)]">Setup confirmation</p>
            <h2 id="setup-confirmation-title" className="display mt-4 text-4xl font-semibold tracking-[-0.045em]">Your interview focus</h2>
            <div className="mt-7 rounded-lg border hairline p-5 sm:p-7">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--silver)]">Target Role</p>
              <p className="display mt-2 text-3xl font-semibold tracking-[-0.04em]">{roleAnalysis.canonical_role ?? targetRole}</p>
              <p className="mt-7 text-sm font-semibold">Mirror will focus on:</p>
              <ul className="mt-3 grid gap-2 sm:grid-cols-2">
                {(roleAnalysis.latest_analysis.output?.interview_themes.slice(0, 5)
                  ?? roleAnalysis.competencies.slice(0, 5).map((item) => item.name)).map((theme) => (
                  <li key={theme} className="flex items-center gap-2 text-sm text-[var(--silver)]"><Check size={16} className="text-[var(--pulse)]" /> {theme}</li>
                ))}
              </ul>
            </div>
          </section>
        )}

        {error && <p role="alert" className="mt-6 border-l-2 border-red-400 pl-3 text-sm text-red-200">{error}</p>}
        <div className="mt-9 flex justify-end">
          {analysis?.status === "COMPLETED" && roleAnalysis?.latest_analysis?.status === "COMPLETED" ? (
            <button type="button" className="button-primary" onClick={() => { router.replace("/app"); router.refresh(); }}>Continue to Mirror <ArrowRight size={18} /></button>
          ) : (
            <button type="button" className="button-primary" disabled={!resumeDocumentId || !jdMode || savingJd || analyzing} onClick={continueSetup}>{savingJd ? "Saving…" : analyzing ? "Analyzing resume…" : "Analyze resume"} {!savingJd && !analyzing && <ArrowRight size={18} />}</button>
          )}
        </div>
      </div>
    </main>
  );
}

