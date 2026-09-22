"use client";

import "@/styles/onboarding.css";

import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle,
  FileText,
  PencilSimple,
  UploadSimple,
} from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { ChangeEvent, FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  mirrorApi,
  uploadResumeDocument,
  uploadRoleBriefDocument,
  type InquiryDepth,
  type InterviewPlanResponse,
  type MirrorDocument,
  type Onboarding,
  type OnboardingUpdate,
  type ResumeAnalysis,
  type ResumeClaim,
  type RoleAnalysis,
  type Session,
} from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { DiagnosticPanel } from "@/components/onboarding/diagnostic-panel";
import { Reveal } from "@/components/motion/reveal";

import {
  describeFileRejection,
  friendlyAnalysisError,
  friendlyDocumentError,
  maximumFileSize,
} from "@/lib/documents";

type RoleBriefMode = "upload" | "paste" | "none" | null;
type BusyOperation = "role" | "resume" | "plan" | "complete" | null;

const analysisStages = [
  "Reading your experience",
  "Connecting your experience to the role",
  "Noticing what to explore",
  "Preparing your questions",
];

const planStages = [
  "Connecting your experience to the role",
  "Choosing where to start",
  "Shaping your questions",
  "Preparing your conversation plan",
];

const depthOptions: Array<{
  value: InquiryDepth;
  title: string;
  description: string;
  recommended?: boolean;
}> = [
  {
    value: "EVIDENCE_BEHIND_CLAIMS",
    title: "The story behind my work",
    description: "Can I explain the achievements and responsibilities on my resume?",
  },
  {
    value: "ROLE_KNOWLEDGE",
    title: "Depth of role knowledge",
    description: "Do I understand the role beyond terminology and frameworks?",
  },
  {
    value: "DECISION_QUALITY",
    title: "Decision quality",
    description: "Can I explain how I approached ambiguous problems and made trade-offs?",
  },
  {
    value: "OWNERSHIP_IMPACT",
    title: "Ownership and impact",
    description: "Can I separate what I personally contributed from what the team accomplished?",
  },
  {
    value: "COMMUNICATION_UNDER_SCRUTINY",
    title: "Explaining clearly when asked more",
    description: "Can I explain my thinking clearly when someone asks more?",
  },
  {
    value: "COMPLETE_READINESS",
    title: "A little of everything",
    description: "Let Mirror decide where to spend a little more time.",
    recommended: true,
  },
];

function WhyMirror({ children }: { children: ReactNode }) {
  return (
    <details className="ob-why">
      <summary>Why we ask</summary>
      <p>{children}</p>
    </details>
  );
}

function StepHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <Reveal as="header" className="ob-step-header">
      <p className="ob-eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </Reveal>
  );
}

function ActionRow({ children }: { children: ReactNode }) {
  return <div className="ob-actions">{children}</div>;
}

function BackButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <button type="button" className="ob-back" onClick={onClick} disabled={disabled}>
      <ArrowLeft size={17} /> Back
    </button>
  );
}

function claimDisplayText(claim: ResumeClaim) {
  return claim.review_status === "NEEDS_CORRECTION" && claim.corrected_claim_text
    ? claim.corrected_claim_text
    : claim.claim_text;
}

export function OnboardingFlow({ initialOnboarding }: { initialOnboarding: Onboarding }) {
  const router = useRouter();
  const resumeInput = useRef<HTMLInputElement>(null);
  const roleBriefInput = useRef<HTMLInputElement>(null);
  const [onboarding, setOnboarding] = useState(initialOnboarding);
  const [step, setStep] = useState(Math.min(5, Math.max(1, initialOnboarding.onboarding_step || 1)));
  const [stepDirection, setStepDirection] = useState<"forward" | "back">("forward");
  const [targetRole, setTargetRole] = useState(initialOnboarding.target_role ?? "");
  const [targetCompany, setTargetCompany] = useState(initialOnboarding.target_company ?? "");
  const [roleBriefMode, setRoleBriefMode] = useState<RoleBriefMode>(
    initialOnboarding.onboarding_role_brief_skipped ? "none" : null,
  );
  const [roleBriefText, setRoleBriefText] = useState("");
  const [savedRoleBriefText, setSavedRoleBriefText] = useState("");
  const [roleBrief, setRoleBrief] = useState<MirrorDocument | null>(null);
  const [resumeDocument, setResumeDocument] = useState<MirrorDocument | null>(null);
  const [resumeAnalysis, setResumeAnalysis] = useState<ResumeAnalysis | null>(null);
  const [roleAnalysis, setRoleAnalysis] = useState<RoleAnalysis | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [interviewPlan, setInterviewPlan] = useState<InterviewPlanResponse | null>(null);
  const [selectedDepth, setSelectedDepth] = useState<InquiryDepth[]>(
    initialOnboarding.inquiry_depth?.length ? initialOnboarding.inquiry_depth : ["COMPLETE_READINESS"],
  );
  const [busy, setBusy] = useState<BusyOperation>(null);
  const [uploadKind, setUploadKind] = useState<"resume" | "role" | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadNotice, setUploadNotice] = useState<{ kind: "resume" | "role"; message: string } | null>(null);
  const [stageIndex, setStageIndex] = useState(0);
  const [reviewingClaim, setReviewingClaim] = useState<string | null>(null);
  const [correctionDrafts, setCorrectionDrafts] = useState<Record<string, string>>({});
  const [savingClaim, setSavingClaim] = useState<string | null>(null);
  const [hydrating, setHydrating] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function hydrate() {
      try {
        const documents = await mirrorApi.documents();
        if (!active) return;
        const selectedResume = documents.find((item) => item.id === initialOnboarding.onboarding_resume_document_id) ?? null;
        const selectedRoleBrief = documents.find((item) => item.id === initialOnboarding.onboarding_role_brief_document_id) ?? null;
        setResumeDocument(selectedResume);
        setRoleBrief(selectedRoleBrief);
        if (selectedRoleBrief) {
          setRoleBriefText(selectedRoleBrief.raw_text ?? "");
          setSavedRoleBriefText(selectedRoleBrief.raw_text ?? "");
          setRoleBriefMode(selectedRoleBrief.original_filename ? "upload" : "paste");
        }

        const requests: Promise<void>[] = [];
        if (selectedResume) {
          requests.push(mirrorApi.resumeAnalysis(selectedResume.id).then((value) => {
            if (active) setResumeAnalysis(value);
          }).catch((reason: unknown) => {
            if (!(reason instanceof ApiError && reason.status === 404)) throw reason;
          }));
        }
        if (initialOnboarding.onboarding_role_profile_id) {
          requests.push(mirrorApi.role(initialOnboarding.onboarding_role_profile_id).then((value) => {
            if (active) setRoleAnalysis(value);
          }));
        }
        if (initialOnboarding.onboarding_session_id) {
          requests.push(mirrorApi.session(initialOnboarding.onboarding_session_id).then((value) => {
            if (active) setSession(value);
          }));
          requests.push(mirrorApi.interviewPlan(initialOnboarding.onboarding_session_id).then((value) => {
            if (active) setInterviewPlan(value);
          }).catch((reason: unknown) => {
            if (!(reason instanceof ApiError && reason.status === 404)) throw reason;
          }));
        }
        await Promise.all(requests);
      } catch (reason) {
        if (!active) return;
        if (reason instanceof ApiError && reason.status === 401) {
          router.replace("/login?reason=session_expired");
          return;
        }
        setError("We couldn't restore your saved session just now. Please refresh and try again.");
      } finally {
        if (active) setHydrating(false);
      }
    }
    void hydrate();
    return () => { active = false; };
  }, [initialOnboarding, router]);

  useEffect(() => {
    if (busy !== "resume" && busy !== "plan") {
      setStageIndex(0);
      return;
    }
    const stages = busy === "resume" ? analysisStages : planStages;
    const timer = window.setInterval(() => {
      setStageIndex((current) => Math.min(current + 1, stages.length - 1));
    }, 1100);
    return () => window.clearInterval(timer);
  }, [busy]);

  const experienceSignals = useMemo(() => {
    const names = resumeAnalysis?.output?.skills.map((skill) => skill.name) ?? [];
    return [...new Set(names)].slice(0, 8);
  }, [resumeAnalysis]);

  const claimsWorthExamining = useMemo(() => {
    const claims = resumeAnalysis?.claims ?? [];
    const prioritised = claims.filter((claim) => claim.verification_priority === "HIGH");
    return (prioritised.length ? prioritised : claims).slice(0, 3);
  }, [resumeAnalysis]);

  const documentLimits = useMemo(() => (
    [...(roleAnalysis?.competencies ?? [])]
      .sort((left, right) => right.importance_weight - left.importance_weight)
      .slice(0, 3)
  ), [roleAnalysis]);

  const unprovenObjectives = useMemo(() => (
    interviewPlan?.plan?.objectives
      .filter((objective) => objective.priority === "HIGH")
      .slice(0, 3)
      ?? []
  ), [interviewPlan]);

  const roleReady = roleAnalysis?.latest_analysis?.status === "COMPLETED";
  const evidenceReady = resumeAnalysis?.status === "COMPLETED";
  const sessionReady = session?.status === "READY" || session?.status === "ACTIVE";
  const activeStages = busy === "plan" ? planStages : analysisStages;
  const busyLabel = busy === "role"
    ? "Getting to know the role"
    : busy === "resume" || busy === "plan"
      ? activeStages[stageIndex]
      : busy === "complete"
        ? "Opening your conversation"
        : undefined;

  async function signOutExpiredSession() {
    await getSupabaseBrowserClient().auth.signOut();
    router.replace("/login?reason=session_expired");
  }

  async function persist(values: OnboardingUpdate) {
    try {
      const updated = await mirrorApi.updateOnboarding(values);
      setOnboarding(updated);
      return updated;
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        await signOutExpiredSession();
      } else {
        setError("We couldn't save this part just now. Please check your connection and try again.");
      }
      return null;
    }
  }

  async function goBack(targetStep: number) {
    setError("");
    const updated = await persist({ onboarding_step: targetStep });
    if (updated) {
      setStepDirection("back");
      setStep(targetStep);
    }
  }

  function validateFile(file: File, kind: "resume" | "role brief") {
    const rejection = describeFileRejection(file, kind);
    if (rejection) {
      setError(rejection);
      return false;
    }
    return true;
  }

  async function handleRoleBriefUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !validateFile(file, "role brief")) return;
    setError("");
    setUploadNotice(null);
    setUploadKind("role");
    setUploadProgress(0);
    try {
      const document = await uploadRoleBriefDocument(file, setUploadProgress);
      const updated = await persist({
        onboarding_role_brief_document_id: document.id,
        onboarding_role_brief_skipped: false,
      });
      if (!updated) return;
      setRoleBrief(document);
      setRoleBriefText(document.raw_text ?? "");
      setSavedRoleBriefText(document.raw_text ?? "");
      setRoleBriefMode("upload");
    } catch (reason) {
      setError(friendlyDocumentError(reason, "role brief"));
      if (reason instanceof ApiError && reason.status === 401) await signOutExpiredSession();
    } finally {
      setUploadKind(null);
      setUploadProgress(null);
    }
  }

  async function establishRole(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanedRole = targetRole.trim();
    const cleanedCompany = targetCompany.trim();
    if (cleanedRole.length < 2) return;
    if (!roleBriefMode) {
      setError("Please upload or paste a role brief, or continue without one.");
      return;
    }
    setError("");
    setBusy("role");
    try {
      let selectedRoleBrief = roleBrief;
      if (roleBriefMode === "paste") {
        const cleanedBrief = roleBriefText.trim();
        if (!cleanedBrief) {
          setError("Please paste the role brief, or choose to continue without one.");
          return;
        }
        if (!selectedRoleBrief || cleanedBrief !== savedRoleBriefText) {
          selectedRoleBrief = await mirrorApi.createJobDescription(cleanedBrief);
          setRoleBrief(selectedRoleBrief);
          setSavedRoleBriefText(selectedRoleBrief.raw_text ?? cleanedBrief);
        }
      }

      const reusableProfileId = roleAnalysis?.target_role.trim().toLocaleLowerCase() === cleanedRole.toLocaleLowerCase()
        ? roleAnalysis.id
        : undefined;
      const analysedRole = await mirrorApi.analyzeRole({
        target_role: cleanedRole,
        ...(roleBriefMode !== "none" && selectedRoleBrief ? { job_description_document_id: selectedRoleBrief.id } : {}),
        ...(reusableProfileId ? { role_profile_id: reusableProfileId } : {}),
      });
      if (analysedRole.latest_analysis?.status !== "COMPLETED") {
        setError("We couldn't finish getting to know the role just now. Please try again in a moment.");
        return;
      }
      const updated = await persist({
        target_role: cleanedRole,
        target_company: cleanedCompany || null,
        onboarding_role_brief_document_id: roleBriefMode === "none" ? null : selectedRoleBrief?.id ?? null,
        onboarding_role_brief_skipped: roleBriefMode === "none",
        onboarding_role_profile_id: analysedRole.id,
        onboarding_session_id: null,
        onboarding_step: 2,
      });
      if (!updated) return;
      setRoleAnalysis(analysedRole);
      setRoleBrief(roleBriefMode === "none" ? null : selectedRoleBrief);
      setSession(null);
      setInterviewPlan(null);
      setStepDirection("forward");
      setStep(2);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) await signOutExpiredSession();
      else setError(friendlyAnalysisError(reason, "role"));
    } finally {
      setBusy(null);
    }
  }

  async function handleResumeUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !validateFile(file, "resume")) return;
    setError("");
    setUploadNotice(null);
    setUploadKind("resume");
    setUploadProgress(0);
    try {
      const document = await uploadResumeDocument(file, setUploadProgress);
      const updated = await persist({
        onboarding_resume_document_id: document.id,
        onboarding_session_id: null,
      });
      if (!updated) return;
      setResumeDocument(document);
      setResumeAnalysis(null);
      setSession(null);
      setInterviewPlan(null);
      setUploadNotice({
        kind: "resume",
        message: `Resume uploaded — ${document.original_filename ?? file.name}. Continue whenever you're ready.`,
      });
    } catch (reason) {
      setError(friendlyDocumentError(reason, "resume"));
      if (reason instanceof ApiError && reason.status === 401) await signOutExpiredSession();
    } finally {
      setUploadKind(null);
      setUploadProgress(null);
    }
  }

  async function buildEvidenceMap() {
    if (!resumeDocument) return;
    setError("");
    setBusy("resume");
    try {
      const analysis = await mirrorApi.analyzeResume(resumeDocument.id);
      if (analysis.status === "FAILED") {
        const message = analysis.error_type === "document_parsing_failure"
          ? "We couldn't read enough text from this resume. Please try a text-based PDF or DOCX file."
          : "We couldn't put your experience together just now. Your upload is saved, so you can try again.";
        setError(message);
        return;
      }
      if (analysis.status !== "COMPLETED" || !analysis.output) {
        setError("This is still in progress. Please try again in a moment.");
        return;
      }
      const updated = await persist({ onboarding_step: 3 });
      if (!updated) return;
      setResumeAnalysis(analysis);
      setStepDirection("forward");
      setStep(3);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) await signOutExpiredSession();
      else setError(friendlyAnalysisError(reason, "resume"));
    } finally {
      setBusy(null);
    }
  }

  async function reviewClaim(claimId: string, status: "CORRECT" | "NEEDS_CORRECTION") {
    if (!resumeDocument) return;
    const correction = correctionDrafts[claimId]?.trim();
    if (status === "NEEDS_CORRECTION" && (!correction || correction.length < 3)) {
      setError("Please describe the correction before saving it.");
      return;
    }
    setError("");
    setSavingClaim(claimId);
    try {
      const updated = await mirrorApi.correctResumeClaim(
        resumeDocument.id,
        claimId,
        status,
        status === "NEEDS_CORRECTION" ? correction : undefined,
      );
      setResumeAnalysis(updated);
      setReviewingClaim(null);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) await signOutExpiredSession();
      else setError("We couldn't save that correction just now. Please try again.");
    } finally {
      setSavingClaim(null);
    }
  }

  async function confirmEvidenceMap() {
    setError("");
    const updated = await persist({ onboarding_step: 4 });
    if (updated) {
      setStepDirection("forward");
      setStep(4);
    }
  }

  function openFirstCorrection() {
    const claim = claimsWorthExamining[0] ?? resumeAnalysis?.claims[0];
    if (!claim) return;
    setReviewingClaim(claim.id);
    window.requestAnimationFrame(() => document.getElementById(`claim-${claim.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }

  function toggleDepth(value: InquiryDepth) {
    if (value === "COMPLETE_READINESS") {
      setSelectedDepth([value]);
      return;
    }
    setSelectedDepth((current) => {
      const withoutComplete = current.filter((item) => item !== "COMPLETE_READINESS");
      if (withoutComplete.includes(value)) {
        const next = withoutComplete.filter((item) => item !== value);
        return next.length ? next : ["COMPLETE_READINESS"];
      }
      return [...withoutComplete, value];
    });
  }

  async function prepareInterviewThesis() {
    if (!resumeDocument || !roleReady || !evidenceReady || !onboarding.target_role) return;
    setError("");
    setBusy("plan");
    try {
      const inquiryDepthChanged = selectedDepth.length !== onboarding.inquiry_depth.length
        || selectedDepth.some((value) => !onboarding.inquiry_depth.includes(value));
      const savedDepth = await persist({ inquiry_depth: selectedDepth });
      if (!savedDepth) return;

      let preparedSession = inquiryDepthChanged ? null : session;
      if (!preparedSession || preparedSession.status === "FAILED" || preparedSession.target_role !== onboarding.target_role) {
        preparedSession = await mirrorApi.createSession(onboarding.target_role, roleBrief?.raw_text ?? "");
        const documentIds = [resumeDocument.id, ...(roleBrief ? [roleBrief.id] : [])];
        await mirrorApi.linkSessionDocuments(preparedSession.id, documentIds);
      }
      if (preparedSession.status === "CREATED" || preparedSession.status === "PREPARING") {
        const prepared = await mirrorApi.prepare(preparedSession.id);
        preparedSession = prepared.session;
      }
      if (preparedSession.status !== "READY" && preparedSession.status !== "ACTIVE") {
        setError("We couldn't finish your conversation plan just now. Your progress is saved, so you can try again.");
        return;
      }
      const preparedPlan = await mirrorApi.interviewPlan(preparedSession.id);
      const updated = await persist({
        onboarding_session_id: preparedSession.id,
        onboarding_step: 5,
      });
      if (!updated) return;
      setSession(preparedSession);
      setInterviewPlan(preparedPlan);
      setStepDirection("forward");
      setStep(5);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        await signOutExpiredSession();
      } else if (reason instanceof ApiError && reason.status === 409) {
        setError("Your role and resume need to finish being read before we can prepare your conversation. Please try again in a moment.");
      } else if (reason instanceof ApiError && reason.status === 503) {
        setError("Planning is unavailable for a moment. Your role and experience are still saved.");
      } else {
        setError("We couldn't prepare your conversation plan just now. Please check your connection and try again.");
      }
    } finally {
      setBusy(null);
    }
  }

  async function beginInterview() {
    if (!sessionReady || !session) return;
    setError("");
    setBusy("complete");
    const updated = await persist({ onboarding_completed: true });
    if (updated) {
      router.replace(`/app/interview/${session.id}`);
      router.refresh();
    } else {
      setBusy(null);
    }
  }

  function renderStep() {
    if (step === 1) {
      return (
        <form onSubmit={establishRole} className="ob-step" aria-busy={busy === "role"}>
          <StepHeader
            eyebrow="Your target role"
            title="Tell us the role you're aiming for."
            description="Add the employer's brief if you have one, or continue with a general picture of the role."
          />
          <div className="ob-fields ob-two-col">
            <label>
              <span>Target role</span>
              <input className="field" value={targetRole} onChange={(event) => setTargetRole(event.target.value)} minLength={2} maxLength={160} required autoFocus placeholder="Product Manager" />
            </label>
            <label>
              <span>Company <small>Optional</small></span>
              <input className="field" value={targetCompany} onChange={(event) => setTargetCompany(event.target.value)} maxLength={160} placeholder="Company name" />
            </label>
          </div>
          <section className="ob-role-brief" aria-labelledby="role-brief-title">
            <div>
              <p className="ob-index">Role context</p>
              <h2 id="role-brief-title">Add the role brief</h2>
              <p>Use the employer's brief to make the conversation fit this opportunity.</p>
            </div>
            <div className="ob-role-brief-modes">
              <button type="button" aria-pressed={roleBriefMode === "upload"} onClick={() => roleBriefInput.current?.click()}>
                <UploadSimple size={18} /> Upload role brief
              </button>
              <button type="button" aria-pressed={roleBriefMode === "paste"} onClick={() => setRoleBriefMode("paste")}>
                <FileText size={18} /> Paste role brief
              </button>
              <button type="button" aria-pressed={roleBriefMode === "none"} onClick={() => { setRoleBriefMode("none"); setRoleBrief(null); }}>
                Continue without one
              </button>
            </div>
            <input ref={roleBriefInput} className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={handleRoleBriefUpload} />
            {roleBriefMode === "paste" && (
              <label className="ob-role-brief-paste">
                <span>Role brief</span>
                <textarea className="field" value={roleBriefText} onChange={(event) => setRoleBriefText(event.target.value)} maxLength={100000} placeholder="Paste the responsibilities, expectations, and role context." />
              </label>
            )}
            {roleBriefMode === "upload" && roleBrief && (
              <p className="ob-file-confirm"><Check size={16} /> {roleBrief.original_filename ?? "Role brief uploaded"}</p>
            )}
            {uploadKind === "role" && uploadProgress !== null && (
              <>
                <p className="ob-upload-status" role="status" aria-live="polite">
                  {uploadProgress < 100 ? `Uploading your role brief — ${uploadProgress}%` : "Upload complete. Extracting the role text…"}
                </p>
                <div className="ob-upload-progress" role="progressbar" aria-label="Role brief upload" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress}>
                  <span style={{ width: `${uploadProgress}%` }} />
                </div>
              </>
            )}
            <WhyMirror>The role brief tells Mirror what matters for this opportunity. Without one, Mirror uses a general picture of the role and says so.</WhyMirror>
          </section>
          <ActionRow>
            <span />
            <button className="button-primary" disabled={busy !== null || targetRole.trim().length < 2 || !roleBriefMode}>
              {busy === "role" ? "Getting to know the role" : "Continue"} <ArrowRight size={18} />
            </button>
          </ActionRow>
        </form>
      );
    }

    if (step === 2) {
      return (
        <section className="ob-step" aria-busy={busy === "resume"}>
          <StepHeader
            eyebrow="Your starting point"
            title="Share your resume to begin."
            description="Your resume lets the conversation start from your own experience."
          />
          <div className="ob-dropzone" data-has-file={Boolean(resumeDocument)}>
            <div>
              <p className="ob-dropzone-label">Resume</p>
              <h2>{resumeDocument ? resumeDocument.original_filename ?? "Resume uploaded" : "Add my resume"}</h2>
              <p>PDF or DOCX · up to {Math.round(maximumFileSize / 1024 / 1024)} MB</p>
            </div>
            <button type="button" className="button-secondary" onClick={() => resumeInput.current?.click()} disabled={uploadKind !== null || busy !== null}>
              <UploadSimple size={18} /> {resumeDocument ? "Replace resume" : "Choose file"}
            </button>
            <input ref={resumeInput} className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={handleResumeUpload} />
          </div>
          {uploadKind === "resume" && uploadProgress !== null && (
            <>
              <p className="ob-upload-status" role="status" aria-live="polite">
                {uploadProgress < 100 ? `Uploading your resume — ${uploadProgress}%` : "Upload complete. Saving to your experience library…"}
              </p>
              <div className="ob-upload-progress" role="progressbar" aria-label="Resume upload" aria-valuemin={0} aria-valuemax={100} aria-valuenow={uploadProgress}>
                <span style={{ width: `${uploadProgress}%` }} />
              </div>
            </>
          )}
          {uploadKind === null && uploadNotice?.kind === "resume" && (
            <p className="ob-upload-notice" role="status" aria-live="polite">
              <Check size={15} /> {uploadNotice.message}
            </p>
          )}
          <WhyMirror>Your resume is where Mirror starts. It helps us ask about your own experience.</WhyMirror>

          {busy === "resume" && (
            <div className="ob-analysis" role="status" aria-live="polite">
              <p className="ob-index">Putting your experience at a glance</p>
              <h2>{analysisStages[stageIndex]}</h2>
              <p>Mirror is connecting your experience to the role and choosing where a little more detail could help your story come across.</p>
              <ol>
                {analysisStages.map((label, index) => (
                  <li key={label} data-state={index < stageIndex ? "complete" : index === stageIndex ? "active" : "waiting"}>
                    {index < stageIndex ? <Check size={15} /> : <span>{String(index + 1).padStart(2, "0")}</span>}
                    {label}
                  </li>
                ))}
              </ol>
            </div>
          )}

          <ActionRow>
            <BackButton onClick={() => void goBack(1)} disabled={busy !== null} />
            <button type="button" className="button-primary" disabled={!resumeDocument || busy !== null || uploadKind !== null} onClick={() => void buildEvidenceMap()}>
              {busy === "resume" ? analysisStages[stageIndex] : "Show my experience at a glance"} <ArrowRight size={18} />
            </button>
          </ActionRow>
        </section>
      );
    }

    if (step === 3) {
      return (
        <section className="ob-step">
          <StepHeader
            eyebrow="Your experience at a glance"
            title="Here's the story your resume tells right now."
            description="Have a look at what Mirror understood. Change anything that doesn't feel right before we begin."
          />

          <div className="ob-evidence-map">
            <section>
              <p className="ob-evidence-label">Your target role</p>
              <h2>{roleAnalysis?.canonical_role ?? onboarding.target_role}</h2>
              <p>{onboarding.target_company || (onboarding.onboarding_role_brief_skipped ? "General picture of the role" : "Specific role brief")}</p>
            </section>
            <section>
              <p className="ob-evidence-label">Skills that came up</p>
              <div className="ob-signal-list">
                {experienceSignals.map((signal) => <span key={signal}>{signal}</span>)}
                {!experienceSignals.length && <p>No specific skills stood out yet.</p>}
              </div>
            </section>
            <section>
              <p className="ob-evidence-label">Moments worth talking through</p>
              <div className="ob-claim-list">
                {claimsWorthExamining.map((claim) => (
                  <article id={`claim-${claim.id}`} key={claim.id} data-review={claim.review_status ?? "pending"}>
                    <div>
                      <p>{claimDisplayText(claim)}</p>
                      <span>{claim.claim_type.replaceAll("_", " ")} · {claim.source_reference}</span>
                      {claim.review_status && <strong>{claim.review_status === "CORRECT" ? "Confirmed by you" : "Correction saved"}</strong>}
                    </div>
                    <div className="ob-claim-actions">
                      <button type="button" disabled={savingClaim === claim.id} onClick={() => void reviewClaim(claim.id, "CORRECT")}><CheckCircle size={15} /> Accurate</button>
                      <button type="button" disabled={savingClaim === claim.id} onClick={() => { setReviewingClaim(claim.id); setCorrectionDrafts((current) => ({ ...current, [claim.id]: current[claim.id] ?? claimDisplayText(claim) })); }}><PencilSimple size={15} /> Correct</button>
                    </div>
                    {reviewingClaim === claim.id && (
                      <div className="ob-claim-correction">
                        <label htmlFor={`correction-${claim.id}`}>How would you like this to read?</label>
                        <textarea id={`correction-${claim.id}`} className="field" value={correctionDrafts[claim.id] ?? ""} onChange={(event) => setCorrectionDrafts((current) => ({ ...current, [claim.id]: event.target.value }))} maxLength={2000} />
                        <div>
                          <button type="button" onClick={() => setReviewingClaim(null)}>Cancel</button>
                          <button type="button" className="button-primary" disabled={savingClaim === claim.id} onClick={() => void reviewClaim(claim.id, "NEEDS_CORRECTION")}>{savingClaim === claim.id ? "Saving correction" : "Save correction"}</button>
                        </div>
                      </div>
                    )}
                  </article>
                ))}
                {!claimsWorthExamining.length && <p className="ob-evidence-empty">Mirror didn't find enough detail to show here. You can replace the resume or try again.</p>}
              </div>
            </section>
            <section>
              <p className="ob-evidence-label">What a resume can't show on its own</p>
              <p className="ob-evidence-explainer">These are parts of the role a resume doesn't always show. They are things to talk about, not a judgment of your ability.</p>
              <ul className="ob-gap-list">
                {documentLimits.map((item) => <li key={item.id}>{item.name}<span>{item.expected_level.replaceAll("_", " ")}</span></li>)}
                {!documentLimits.length && <li>Mirror will use the conversation to hear more about depth, ownership, and the thinking behind your work.</li>}
              </ul>
            </section>
          </div>
          <ActionRow>
            <BackButton onClick={() => void goBack(2)} disabled={busy !== null} />
            <div className="ob-action-group">
              <button type="button" className="ob-text-action" onClick={openFirstCorrection}>Correct something</button>
              <button type="button" className="button-primary" onClick={() => void confirmEvidenceMap()}>This reflects my experience <ArrowRight size={18} /></button>
            </div>
          </ActionRow>
        </section>
      );
    }

    if (step === 4) {
      return (
        <section className="ob-step" aria-busy={busy === "plan"}>
          <StepHeader
            eyebrow="Your focus"
            title="How deep should we go?"
            description="Choose where you'd like the conversation to spend more time."
          />
          <div className="ob-inquiry-list" role="group" aria-label="Where to spend more time">
            {depthOptions.map((option, index) => {
              const selected = selectedDepth.includes(option.value);
              return (
                <button key={option.value} type="button" aria-pressed={selected} onClick={() => toggleDepth(option.value)}>
                  <span className="ob-inquiry-number">{String(index + 1).padStart(2, "0")}</span>
                  <span className="ob-inquiry-copy"><strong>{option.title}</strong><small>{option.description}</small></span>
                  {option.recommended && <span className="ob-inquiry-recommended">Recommended</span>}
                  <span className="ob-inquiry-check">{selected && <Check size={16} weight="bold" />}</span>
                </button>
              );
            })}
          </div>
          <WhyMirror>Your choice shapes which topics get more time. Mirror still covers the main areas and keeps follow-up questions to a sensible number.</WhyMirror>
          {busy === "plan" && (
            <div className="ob-analysis ob-compact" role="status" aria-live="polite">
              <p className="ob-index">Preparing your conversation plan</p>
              <h2>{planStages[stageIndex]}</h2>
              <p>Mirror is using your target role, your experience, and your choice to prepare your conversation.</p>
            </div>
          )}
          <ActionRow>
            <BackButton onClick={() => void goBack(3)} disabled={busy !== null} />
            <button type="button" className="button-primary" disabled={!selectedDepth.length || busy !== null} onClick={() => void prepareInterviewThesis()}>
              {busy === "plan" ? planStages[stageIndex] : "Prepare my conversation"} <ArrowRight size={18} />
            </button>
          </ActionRow>
        </section>
      );
    }

    return (
      <section className="ob-step ob-thesis" aria-busy={busy === "complete"}>
        <StepHeader
          eyebrow="Your conversation plan"
          title="Your conversation is ready."
          description="Your role, your experience, and your focus are now shaped into a plan for the conversation."
        />
        <div className="ob-thesis-grid">
          <section>
            <p>What you've shared</p>
            <h2>The experience and achievements on your resume.</h2>
            <ul>{claimsWorthExamining.slice(0, 3).map((claim) => <li key={claim.id}>{claimDisplayText(claim)}</li>)}</ul>
          </section>
          <section>
            <p>What the role looks for</p>
            <h2>The skills and depth expected for your target role.</h2>
            <ul>{(roleAnalysis?.competencies ?? []).slice(0, 4).map((item) => <li key={item.id}>{item.name}</li>)}</ul>
          </section>
          <section>
            <p>What's still to explore</p>
            <h2>Areas where a resume alone can't say much.</h2>
            <ul>
              {unprovenObjectives.map((item) => <li key={item.objective_id}>{item.objective}</li>)}
              {!unprovenObjectives.length && documentLimits.slice(0, 3).map((item) => <li key={item.id}>{item.name}</li>)}
              {!unprovenObjectives.length && !documentLimits.length && <li>Depth, ownership, and the thinking behind your work</li>}
            </ul>
          </section>
        </div>
        <div className="ob-thesis-convergence">
          <span aria-hidden="true" />
          <div>
            <p className="ob-index">Your conversation</p>
            <h2>Mirror will now ask about the spaces in between.</h2>
            <p>Your questions won't follow a fixed script. When something comes through clearly, we move on. When there's more to explore, we'll ask a gentle follow-up.</p>
          </div>
        </div>
        <ActionRow>
          <span />
          <button type="button" className="button-primary" disabled={!sessionReady || busy !== null} onClick={() => void beginInterview()}>
            {busy === "complete" ? "Opening conversation" : "Begin the conversation"} <ArrowRight size={18} />
          </button>
        </ActionRow>
      </section>
    );
  }

  return (
    <main id="main-content" className="ob-workspace" data-step={step}>
      <div className="ob-main">
        <div className="ob-progress" aria-label={`Step ${step} of 5`}>
          <span>Preparing your session</span>
          <span>{String(step).padStart(2, "0")} / 05</span>
          <div><span style={{ transform: `scaleX(${step / 5})` }} /></div>
        </div>
        {hydrating ? (
          <div className="ob-restore" role="status">
            <p className="ob-eyebrow">Getting your session ready</p>
            <h1>Reconnecting your saved work.</h1>
            <p>Mirror is loading the role and documents already attached to this session.</p>
          </div>
        ) : (
          <div key={step} className={`ob-step-enter${stepDirection === "back" ? " ob-step-enter--back" : ""}`}>
            {renderStep()}
          </div>
        )}
        {error && <p role="alert" className="ob-error">{error}</p>}
      </div>
      <DiagnosticPanel
        step={step}
        targetRole={targetRole}
        targetCompany={targetCompany}
        roleBriefReady={Boolean(roleBrief) || roleBriefMode === "none"}
        roleBriefSkipped={roleBriefMode === "none"}
        resumeName={resumeDocument?.original_filename ?? ""}
        evidenceReady={evidenceReady}
        roleReady={roleReady}
        sessionReady={sessionReady}
        busyLabel={busyLabel}
      />
    </main>
  );
}
