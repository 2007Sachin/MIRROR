import { getSupabaseBrowserClient } from "@/lib/supabase";

export type Session = {
  id: string;
  user_id: string;
  target_role: string;
  resume_url: string | null;
  jd_text: string;
  status: "CREATED" | "PREPARING" | "READY" | "ACTIVE" | "ASSESSING" | "COMPLETED" | "FAILED";
  phase: string;
  completion_pct: number;
  synthetic: boolean;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  phase_started_at: string;
  phase_time_budget_seconds: number;
  total_time_budget_seconds: number;
  elapsed_seconds: number;
  current_primary_question_id: string | null;
  current_probe_count: number;
  total_questions: number;
  recovery_count: number;
};

export type Profile = {
  id: string;
  full_name: string | null;
  email: string;
};

export type CareerStage = "STUDENT" | "FINAL_YEAR_STUDENT" | "FRESHER" | "EARLY_CAREER" | "EXPERIENCED";
export type CareerIntent = "CAMPUS_PLACEMENT" | "INTERNSHIP" | "FIRST_JOB" | "JOB_SWITCH" | "SPECIFIC_COMPANY" | "EXPLORING";
export type InterviewTimeline = "TODAY" | "THIS_WEEK" | "THIS_MONTH" | "LATER" | "EXPLORING";
export type PreferredLanguage = "ENGLISH" | "HINDI" | "KANNADA" | "TAMIL" | "TELUGU";

export type Onboarding = {
  career_stage: CareerStage | null;
  career_intent: CareerIntent | null;
  target_role: string | null;
  interview_timeline: InterviewTimeline | null;
  preferred_language: PreferredLanguage | null;
  college_id: string | null;
  onboarding_completed: boolean;
};

export type OnboardingUpdate = Partial<Onboarding>;

export type DocumentType = "RESUME" | "JOB_DESCRIPTION" | "PROJECT";
export type DocumentStatus = "UPLOADED" | "PROCESSING" | "PROCESSED" | "FAILED";

export type MirrorDocument = {
  id: string;
  user_id: string;
  document_type: DocumentType;
  storage_path: string | null;
  original_filename: string | null;
  mime_type: string | null;
  raw_text: string | null;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  processed_at: string | null;
};

export type ClaimReviewStatus = "CORRECT" | "NEEDS_CORRECTION";

export type ResumeClaim = {
  id: string;
  claim_text: string;
  claim_type: "SKILL" | "PROJECT" | "SCALE" | "OWNERSHIP" | "TOOL" | "OUTCOME" | "EXPERIENCE" | "RESPONSIBILITY";
  source: "RESUME";
  source_reference: string;
  confidence: number;
  verification_priority: "LOW" | "MEDIUM" | "HIGH";
  skill: string | null;
  project_name: string | null;
  metric_value: number | null;
  metric_unit: string | null;
  ownership_language: string | null;
  outcome: string | null;
  tool: string | null;
  review_status: ClaimReviewStatus | null;
  corrected_claim_text: string | null;
  correction_version: number | null;
};

export type ResumeAnalysis = {
  id: string;
  document_id: string;
  user_id: string;
  version: number;
  status: "PROCESSING" | "COMPLETED" | "FAILED";
  output: null | {
    skills: Array<{ name: string; category: string; source_reference: string; confidence: number }>;
    projects: Array<{
      project_name: string;
      description: string;
      technologies: string[];
      claimed_responsibilities: string[];
      claimed_outcomes: string[];
      source_reference: string;
    }>;
    work_experience: unknown[];
    education: unknown[];
    tools: unknown[];
    achievements: unknown[];
    claims: unknown[];
  };
  model: string;
  prompt_version: string;
  analysis_version: string;
  execution_id: string | null;
  error_type: string | null;
  created_at: string;
  completed_at: string | null;
  claims: ResumeClaim[];
};

export type RoleCompetency = {
  id: string;
  role_profile_id: string;
  analysis_version_id: string;
  name: string;
  category: "TECHNICAL" | "ANALYTICAL" | "DOMAIN" | "BEHAVIOURAL" | "COMMUNICATION" | "TOOL";
  importance_weight: number;
  expected_level: "FOUNDATIONAL" | "BASIC" | "INTERMEDIATE" | "ADVANCED";
  source_type: "JOB_DESCRIPTION_EXPLICIT" | "JOB_DESCRIPTION_INFERRED" | "SYNTHETIC_CANONICAL";
  source_reference: string;
  confidence: number;
};

export type RoleAnalysis = {
  id: string;
  user_id: string;
  target_role: string;
  canonical_role: string | null;
  seniority: "ENTRY_LEVEL" | "JUNIOR" | "MID_LEVEL" | "SENIOR" | "LEAD" | "UNSPECIFIED" | null;
  source_type: "JOB_DESCRIPTION" | "SYNTHETIC_CANONICAL";
  source_document_id: string | null;
  current_analysis_version_id: string | null;
  created_at: string;
  updated_at: string;
  latest_analysis: null | {
    id: string;
    version: number;
    status: "PROCESSING" | "COMPLETED" | "FAILED";
    model: string;
    prompt_version: string;
    analysis_version: string;
    error_type: string | null;
    output: null | {
      interview_themes: string[];
      must_have_skills: string[];
      nice_to_have_skills: string[];
    };
  };
  competencies: RoleCompetency[];
};

export type InterviewTurnType =
  | "PLANNED"
  | "DEPTH_PROBE"
  | "CONTRADICTION_PROBE"
  | "LADDER_UP"
  | "LADDER_DOWN"
  | "RECOVERY"
  | "TRANSITION"
  | "CLOSING";

export type PublicInterviewTurn = {
  id: string;
  session_id: string;
  turn_index: number;
  speaker: "CANDIDATE" | "INTERVIEWER";
  text: string;
  turn_type: InterviewTurnType;
  phase: string;
  created_at: string;
};

export type InterviewStart = {
  session_id: string;
  interviewer_turn_index: number;
  question_text: string;
  phase: string;
  turn_type: InterviewTurnType;
  remaining_time_seconds: number;
};

export type TextTurnResult = InterviewStart & {
  candidate_turn_index: number;
};

export type VoiceTurnResult = {
  session_id: string;
  turn_id: string;
  question_text: string;
  audio_url: string | null;
  audio_status: "READY" | "FAILED";
  turn_index: number;
  phase: string;
  turn_type: InterviewTurnType;
  remaining_time_seconds: number;
};

export type ReportEvidence = {
  turn_id: string | null;
  timecode_ms: number | null;
  quote: string;
  direction: "SUPPORTS" | "WEAKENS" | "CONTEXT_ONLY";
};

export type ReportClaim = {
  id: string;
  claim_text: string;
  source: "RESUME" | "JD" | "SPOKEN" | "PROJECT";
  status: "UNVERIFIED" | "CORROBORATED" | "PARTIALLY_HELD" | "WALKED_BACK" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE";
  explanation: string;
  evidence: ReportEvidence[];
  confidence: number;
};

export type ReportReadiness = {
  low: number | null;
  high: number | null;
  label: string;
  signal_strength: string;
  confidence_note: string;
};

export type ReportResponse = {
  session: { target_role: string; completed_at: string; duration_seconds: number; assessment_confidence: number };
  verdict: { code: "NOT_READY_YET" | "DEVELOPING" | "NEAR_READY" | "READY" | "STRONG"; label: string; summary: string };
  role_readiness: ReportReadiness;
  interview_readiness: ReportReadiness;
  claims_audit: { held: ReportClaim[]; partially_held: ReportClaim[]; walked_back: ReportClaim[]; contradicted: ReportClaim[]; insufficient_evidence: ReportClaim[]; unverified: ReportClaim[] };
  skill_assessments: Array<{ skill: string; status: string; readiness: ReportReadiness | null; signal_strength: string; evidence: ReportEvidence[]; explanation: string }>;
  session_moments: Array<{ type: "STRONG_EVIDENCE" | "RECOVERY" | "OWNERSHIP_CLARIFICATION" | "UNSUPPORTED_SCALE" | "TECHNICAL_DEPTH"; turn_id: string | null; timecode_ms: number | null; quote: string | null; explanation: string }>;
  root_cause: string;
  trust_and_limitations: { ai_assessments_can_make_mistakes: boolean; candidate_may_dispute_assessments: boolean; skills_may_have_insufficient_signal: boolean; evaluates_this_interview_evidence: boolean; outcome_validation_status: string };
  prescription: Record<string, unknown> | null;
};

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly code?: string) {
    super(message);
  }
}

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const client = getSupabaseBrowserClient();
  const { data } = await client.auth.getSession();
  const headers = new Headers(init?.headers);
  if (data.session?.access_token) headers.set("Authorization", `Bearer ${data.session.access_token}`);
  const response = await fetch(`${apiUrl}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string | { code?: string; message?: string };
    };
    const detail = body.detail;
    throw new ApiError(
      response.status,
      typeof detail === "string" ? detail : detail?.message ?? "Mirror could not complete that request.",
      typeof detail === "object" ? detail.code : undefined,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function uploadVoiceTurn(
  sessionId: string,
  audio: Blob,
  recordedDurationMs: number,
  clientTurnId: string,
  onProgress: (percentage: number) => void,
  onUploaded: () => void,
  signal?: AbortSignal,
): Promise<VoiceTurnResult> {
  const { data } = await getSupabaseBrowserClient().auth.getSession();
  if (!data.session?.access_token) throw new ApiError(401, "Authentication required");

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    if (signal?.aborted) {
      reject(new DOMException("The upload was cancelled.", "AbortError"));
      return;
    }
    signal?.addEventListener("abort", abort, { once: true });
    const settle = <T>(callback: (value: T) => void, value: T) => {
      signal?.removeEventListener("abort", abort);
      callback(value);
    };
    xhr.open("POST", `${apiUrl}/api/v1/sessions/${sessionId}/turn`);
    xhr.timeout = 90_000;
    xhr.setRequestHeader("Authorization", `Bearer ${data.session?.access_token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.upload.onload = onUploaded;
    xhr.onerror = () => settle(reject, new ApiError(0, "Mirror could not reach the voice service."));
    xhr.ontimeout = () => settle(reject, new ApiError(0, "That answer took too long to process. Try again."));
    xhr.onabort = () => settle(reject, new DOMException("The upload was cancelled.", "AbortError"));
    xhr.onload = () => {
      let body: VoiceTurnResult | {
        detail?: string | { code?: string; message?: string };
      } | null = null;
      try { body = JSON.parse(xhr.responseText) as typeof body; } catch { /* Safe fallback below. */ }
      if (xhr.status >= 200 && xhr.status < 300 && body) {
        settle(resolve, body as VoiceTurnResult);
        return;
      }
      const detail = (body as {
        detail?: string | { code?: string; message?: string };
      } | null)?.detail;
      settle(reject, new ApiError(
        xhr.status,
        typeof detail === "string" ? detail : detail?.message ?? "Mirror could not process that recording.",
        typeof detail === "object" ? detail.code : undefined,
      ));
    };
    const form = new FormData();
    const mime = audio.type.split(";", 1)[0] || "audio/webm";
    const extension = mime === "audio/mp4" ? "m4a" : mime.split("/")[1] || "webm";
    form.set("audio", audio, `answer.${extension}`);
    form.set("recorded_duration_ms", String(recordedDurationMs));
    form.set("client_turn_id", clientTurnId);
    xhr.send(form);
  });
}

export async function uploadResumeDocument(
  file: File,
  onProgress: (percentage: number) => void,
): Promise<MirrorDocument> {
  const { data } = await getSupabaseBrowserClient().auth.getSession();
  if (!data.session?.access_token) throw new ApiError(401, "Authentication required");

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${apiUrl}/api/v1/documents/resume`);
    request.setRequestHeader("Authorization", `Bearer ${data.session?.access_token}`);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new ApiError(0, "Mirror could not reach the document service."));
    request.onload = () => {
      let body: MirrorDocument | { detail?: string } | null = null;
      try { body = JSON.parse(request.responseText) as MirrorDocument | { detail?: string }; } catch { /* Use safe fallback. */ }
      if (request.status >= 200 && request.status < 300 && body) {
        onProgress(100);
        resolve(body as MirrorDocument);
        return;
      }
      const detail = body && "detail" in body ? body.detail : undefined;
      reject(new ApiError(request.status, detail ?? "Mirror could not upload that resume."));
    };
    const form = new FormData();
    form.set("resume", file);
    request.send(form);
  });
}

export const mirrorApi = {
  me: () => request<Profile>("/api/v1/me"),
  updateMe: (full_name: string) => request<Profile>("/api/v1/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name }),
  }),
  onboarding: () => request<Onboarding>("/api/v1/onboarding"),
  updateOnboarding: (values: OnboardingUpdate) => request<Onboarding>("/api/v1/onboarding", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  }),
  documents: () => request<MirrorDocument[]>("/api/v1/documents"),
  document: (id: string) => request<MirrorDocument>(`/api/v1/documents/${id}`),
  createJobDescription: (raw_text: string) => request<MirrorDocument>("/api/v1/documents/job-description", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_text }),
  }),
  deleteDocument: (id: string) => request<void>(`/api/v1/documents/${id}`, { method: "DELETE" }),
  analyzeResume: (id: string) => request<ResumeAnalysis>(`/api/v1/resumes/${id}/analyze`, {
    method: "POST",
  }),
  resumeAnalysis: (id: string) => request<ResumeAnalysis>(`/api/v1/resumes/${id}/analysis`),
  correctResumeClaim: (
    documentId: string,
    claimId: string,
    reviewStatus: ClaimReviewStatus,
    correctedClaimText?: string,
  ) => request<ResumeAnalysis>(
    `/api/v1/resumes/${documentId}/analysis/claims/${claimId}/corrections`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        review_status: reviewStatus,
        corrected_claim_text: correctedClaimText,
      }),
    },
  ),
  analyzeRole: (values: {
    target_role: string;
    job_description_document_id?: string;
    role_profile_id?: string;
  }) => request<RoleAnalysis>("/api/v1/roles/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  }),
  role: (id: string) => request<RoleAnalysis>(`/api/v1/roles/${id}`),
  roleCompetencies: (id: string) => request<RoleCompetency[]>(`/api/v1/roles/${id}/competencies`),
  createSession: (target_role: string, jd_text: string) =>
    request<Session>("/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target_role, jd_text }) }),
  uploadResume: (id: string, resume: File) => {
    const form = new FormData();
    form.set("resume", resume);
    return request<Session>(`/api/sessions/${id}/resume`, { method: "POST", body: form });
  },
  prepare: (id: string) => request<{ session: Session }>(`/api/sessions/${id}/prepare`, { method: "POST" }),
  session: (id: string) => request<Session>(`/api/v1/sessions/${id}`),
  startInterview: (id: string) => request<InterviewStart>(`/api/v1/sessions/${id}/start`, { method: "POST" }),
  startVoiceInterview: (id: string) => request<VoiceTurnResult>(`/api/v1/sessions/${id}/voice/start`, { method: "POST" }),
  interviewTurns: (id: string) => request<PublicInterviewTurn[]>(`/api/v1/sessions/${id}/turns`),
  sendTextTurn: (id: string, text: string, clientTurnId: string) =>
    request<TextTurnResult>(`/api/v1/sessions/${id}/turn-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, client_turn_id: clientTurnId }),
    }),
  endInterview: (id: string) => request<Session>(`/api/v1/sessions/${id}/end`, { method: "POST" }),
  retryTurnAudio: (turnId: string) => request<VoiceTurnResult>(`/api/v1/turns/${turnId}/audio/retry`, { method: "POST" }),
  report: (id: string) => request<ReportResponse>(`/api/v1/sessions/${id}/report`),
};

