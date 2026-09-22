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

export type AssessmentPipelineState = {
  session_id: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  retry_count: number;
  failure_code: string | null;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type SessionCompletion = Session & {
  assessment: AssessmentPipelineState;
};

export type DashboardDiagnostic = {
  id: string;
  target_role: string;
  company: string | null;
  interview_status: Session["status"];
  phase: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  assessment: AssessmentPipelineState | null;
  diagnostic_available: boolean;
};

export type DashboardResponse = {
  current: DashboardDiagnostic | null;
  previous: DashboardDiagnostic[];
};

export type DashboardSummary = {
  latest_review: null | {
    session_id: string;
    target_role: string;
    completed_at: string;
    counts: null | { clear: number; could_be_stronger: number; worth_revisiting: number };
    dimensions: Array<{ key: string; label: string; state: string; note: string }>;
    improvements: Array<{ title: string; note: string; from_label: string | null }>;
    next_step: { title: string; body: string };
    shorter_conversation: boolean;
  };
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
export type InquiryDepth =
  | "EVIDENCE_BEHIND_CLAIMS"
  | "ROLE_KNOWLEDGE"
  | "DECISION_QUALITY"
  | "OWNERSHIP_IMPACT"
  | "COMMUNICATION_UNDER_SCRUTINY"
  | "COMPLETE_READINESS";

export type Onboarding = {
  career_stage: CareerStage | null;
  career_intent: CareerIntent | null;
  target_role: string | null;
  interview_timeline: InterviewTimeline | null;
  preferred_language: PreferredLanguage | null;
  college_id: string | null;
  target_company: string | null;
  onboarding_step: number;
  onboarding_resume_document_id: string | null;
  onboarding_role_brief_document_id: string | null;
  onboarding_role_brief_skipped: boolean;
  onboarding_role_profile_id: string | null;
  onboarding_session_id: string | null;
  inquiry_depth: InquiryDepth[];
  onboarding_completed: boolean;
};

export type OnboardingUpdate = Partial<Onboarding>;

export type DocumentType = "RESUME" | "JOB_DESCRIPTION" | "PROJECT";
export type DocumentStatus = "UPLOADED" | "PROCESSING" | "PROCESSED" | "FAILED";
export type EvidenceCategory =
  | "RESUME"
  | "PROJECT"
  | "CASE_STUDY"
  | "CERTIFICATE"
  | "PORTFOLIO"
  | "COVER_LETTER"
  | "ACHIEVEMENT"
  | "WORK_SAMPLE"
  | "ROLE_BRIEF"
  | "OTHER";

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
  title: string | null;
  evidence_category: EvidenceCategory | null;
  context_note: string | null;
  updated_at: string | null;
  archived_at: string | null;
  version_number: number;
  supersedes_document_id: string | null;
};

export type EvidenceDiagnosticReference = {
  session_id: string;
  target_role: string;
  status: Session["status"];
  linked_at: string;
  completed_at: string | null;
};

export type EvidenceUsage = {
  active_diagnostic_count: number;
  completed_diagnostic_count: number;
  diagnostics: EvidenceDiagnosticReference[];
};

export type EvidenceDetail = {
  document: MirrorDocument;
  usage: EvidenceUsage;
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
    work_experience: Array<{ organization: string; role: string }>;
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
      canonical_role: string;
      seniority: RoleAnalysis["seniority"];
      interview_themes: string[];
      must_have_skills: string[];
      nice_to_have_skills: string[];
      behavioural_expectations: string[];
      domain_expectations: string[];
    };
  };
  competencies: RoleCompetency[];
};

export type InterviewPlanObjective = {
  objective_id: string;
  phase: string;
  objective: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  target_claim_ids: string[];
  target_competency_ids: string[];
  target_project_ids: string[];
  initial_question: string;
  question_intent: string;
  expected_signal: string[];
  time_budget_seconds: number;
  max_probes: number;
  difficulty_start: "FOUNDATIONAL" | "BASIC" | "INTERMEDIATE" | "ADVANCED";
  completion_conditions: string[];
};

export type InterviewPlanResponse = {
  id: string;
  session_id: string;
  version: number;
  status: "PROCESSING" | "COMPLETED" | "FAILED";
  plan: null | {
    session_id: string;
    target_role: string;
    total_time_budget_seconds: number;
    planning_version: string;
    objectives: InterviewPlanObjective[];
    created_at: string;
  };
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
  welcome_back?: boolean;
  welcome_text?: string | null;
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
  welcome_back?: boolean;
  welcome_text?: string | null;
  welcome_audio_url?: string | null;
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
  shorter_conversation?: boolean;
};

export type RoleProfileSummary = {
  id: string;
  user_id: string;
  target_role: string;
  canonical_role: string | null;
  seniority: RoleAnalysis["seniority"];
  source_type: RoleAnalysis["source_type"];
  source_document_id: string | null;
  current_analysis_version_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ProgressDirection = "IMPROVING" | "STEADY" | "NEEDS_MORE_PRACTICE";

export type ProgressExcerpt = { quote: string; note: string };

export type ProgressDimension = {
  key: string;
  label: string;
  state: string;
  note: string;
  direction: ProgressDirection | null;
  excerpts: ProgressExcerpt[];
};

export type ProgressChange = { kind: "IMPROVED" | "WATCH"; text: string };

export type SessionReview = NonNullable<DashboardSummary["latest_review"]>;

export type ProgressPractice = SessionReview;

export type ProgressResponse = {
  roles: string[];
  role: string | null;
  practices: ProgressPractice[];
  comparable_count: number;
  dimensions: ProgressDimension[];
  changes: ProgressChange[];
  headline: { title: string; body: string } | null;
};

export type MapCoverage = "PREPARED" | "EXPERIENCE" | "MENTIONED" | "MISSING";
export type MapAreaAction = "FIND_STORY" | "PRESSURE_TEST" | "PRACTICE" | "ADD_EXPERIENCE";

export type InterviewMap = {
  role_profile_id: string;
  target_role: string;
  state: "READY" | "ROLE_PREPARING" | "ROLE_UNREADABLE";
  experience_state: "READY" | "MISSING" | "READING" | "UNREADABLE";
  role_from_job_description: boolean;
  themes: Array<{
    key: string;
    name: string;
    category: RoleCompetency["category"];
    from_job_description: boolean;
    source_text: string | null;
    coverage: MapCoverage;
    matches: Array<{ kind: string; label: string; text: string }>;
  }>;
  preparation_areas: Array<{
    key: string;
    title: string;
    body: string;
    action: MapAreaAction;
    theme_key: string | null;
    focus: string | null;
  }>;
  questions: Array<{ text: string; theme_key: string | null; why: string }>;
  also_expected: string[];
};

export type StoryOrigin = "MANUAL" | "PRESSURE_TEST" | "FIND_A_STORY" | "EXPERIENCE";
export type StoryPart =
  | "situation" | "ownership" | "actions" | "reasoning" | "trade_offs"
  | "outcome" | "measurable_result" | "learning" | "do_differently";

export type StoryFields = Partial<Record<StoryPart, string | null>>;

export type Story = Record<StoryPart, string | null> & {
  id: string;
  user_id: string;
  title: string;
  themes: string[];
  role_profile_id: string | null;
  source_claim_id: string | null;
  source_document_id: string | null;
  source_text: string | null;
  origin: StoryOrigin;
  created_at: string;
  updated_at: string;
  completeness: "READY" | "DEVELOPING" | "STARTED";
  missing_parts: StoryPart[];
};

export type StoryInput = StoryFields & {
  title: string;
  themes?: string[];
  role_profile_id?: string | null;
  source_claim_id?: string | null;
  source_document_id?: string | null;
  source_text?: string | null;
  origin?: StoryOrigin;
};

export type PressureQuestionKind =
  | "OWNERSHIP" | "MEASURE" | "SOURCE_OF_NUMBER" | "OUTCOME" | "DECISION" | "ALTERNATIVE" | "USAGE";
export type PressureReadiness = "CAN_EXPLAIN" | "NEEDS_PREPARATION";

export type PressureTest = {
  role_profile_id: string;
  target_role: string;
  state: "READY" | "NO_RESUME" | "READING" | "UNREADABLE";
  items: Array<{
    claim_id: string;
    statement: string;
    where: string;
    related_theme: string | null;
    questions: Array<{ kind: PressureQuestionKind; text: string; why: string; story_part: StoryPart }>;
    readiness: PressureReadiness | null;
    story_id: string | null;
  }>;
};

export type AnswerChecks = {
  checks: Array<{ key: string; present: boolean; text: string }>;
  follow_up: string | null;
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
  const send = (accessToken: string | undefined) => {
    const headers = new Headers(init?.headers);
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(`${apiUrl}${path}`, { ...init, headers });
  };

  let response = await send(data.session?.access_token);
  if (response.status === 401 && data.session?.refresh_token) {
    const refreshed = await client.auth.refreshSession();
    if (refreshed.data.session?.access_token) {
      response = await send(refreshed.data.session.access_token);
    }
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: string | { code?: string; message?: string };
    };
    const detail = body.detail;
    throw new ApiError(
      response.status,
      typeof detail === "string" ? detail : detail?.message ?? "We couldn't complete that just now. Please try again in a moment.",
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
  if (!data.session?.access_token) throw new ApiError(401, "Please sign in to continue.");

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    if (signal?.aborted) {
      reject(new DOMException("The upload was stopped.", "AbortError"));
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
    xhr.onerror = () => settle(reject, new ApiError(0, "We couldn't reach the voice service just now. Please check your connection and try again."));
    xhr.ontimeout = () => settle(reject, new ApiError(0, "That answer took a little too long to process. Please try again."));
    xhr.onabort = () => settle(reject, new DOMException("The upload was stopped.", "AbortError"));
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
        typeof detail === "string" ? detail : detail?.message ?? "We couldn't process that recording just now. Please try again.",
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
  if (!data.session?.access_token) throw new ApiError(401, "Please sign in to continue.");

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${apiUrl}/api/v1/documents/resume`);
    request.setRequestHeader("Authorization", `Bearer ${data.session?.access_token}`);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new ApiError(0, "We couldn't reach the document service just now. Please check your connection and try again."));
    request.onload = () => {
      let body: MirrorDocument | { detail?: string } | null = null;
      try { body = JSON.parse(request.responseText) as MirrorDocument | { detail?: string }; } catch { /* Use safe fallback. */ }
      if (request.status >= 200 && request.status < 300 && body) {
        onProgress(100);
        resolve(body as MirrorDocument);
        return;
      }
      const detail = body && "detail" in body ? body.detail : undefined;
      reject(new ApiError(request.status, detail ?? "We couldn't upload that resume just now. Please try again."));
    };
    const form = new FormData();
    form.set("resume", file);
    request.send(form);
  });
}

export async function uploadRoleBriefDocument(
  file: File,
  onProgress: (percentage: number) => void,
): Promise<MirrorDocument> {
  const { data } = await getSupabaseBrowserClient().auth.getSession();
  if (!data.session?.access_token) throw new ApiError(401, "Please sign in to continue.");

  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${apiUrl}/api/v1/documents/job-description/upload`);
    request.setRequestHeader("Authorization", `Bearer ${data.session.access_token}`);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new ApiError(0, "We couldn't reach the document service just now. Please check your connection and try again."));
    request.onload = () => {
      let body: MirrorDocument | { detail?: string } | null = null;
      try { body = JSON.parse(request.responseText) as MirrorDocument | { detail?: string }; } catch { /* Use safe fallback. */ }
      if (request.status >= 200 && request.status < 300 && body) {
        onProgress(100);
        resolve(body as MirrorDocument);
        return;
      }
      const detail = body && "detail" in body ? body.detail : undefined;
      reject(new ApiError(request.status, detail ?? "We couldn't upload that role brief just now. Please try again."));
    };
    const form = new FormData();
    form.set("role_brief", file);
    request.send(form);
  });
}

export async function uploadEvidenceDocument(
  file: File,
  values: {
    title: string;
    evidence_category: EvidenceCategory;
    context_note: string;
    acknowledge_active_use?: boolean;
  },
  onProgress: (percentage: number) => void,
  replaceDocumentId?: string,
): Promise<EvidenceDetail> {
  const { data } = await getSupabaseBrowserClient().auth.getSession();
  if (!data.session?.access_token) throw new ApiError(401, "Please sign in to continue.");

  return new Promise((resolve, reject) => {
    const upload = new XMLHttpRequest();
    upload.open(
      "POST",
      `${apiUrl}${replaceDocumentId ? `/api/v1/documents/${replaceDocumentId}/replace` : "/api/v1/evidence"}`,
    );
    upload.setRequestHeader("Authorization", `Bearer ${data.session?.access_token}`);
    upload.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    upload.onerror = () => reject(new ApiError(0, "We couldn't reach the library just now. Please check your connection and try again."));
    upload.onload = () => {
      let body: EvidenceDetail | { detail?: string | { message?: string; code?: string } } | null = null;
      try { body = JSON.parse(upload.responseText) as typeof body; } catch { /* Safe fallback below. */ }
      if (upload.status >= 200 && upload.status < 300 && body) {
        onProgress(100);
        resolve(body as EvidenceDetail);
        return;
      }
      const detail = (body as { detail?: string | { message?: string; code?: string } } | null)?.detail;
      const message = typeof detail === "string"
        ? detail
        : detail && typeof detail === "object"
          ? detail.message
          : undefined;
      const code = detail && typeof detail === "object" ? detail.code : undefined;
      reject(new ApiError(
        upload.status,
        message ?? "We couldn't update that just now. Please try again.",
        code,
      ));
    };
    const form = new FormData();
    form.set("evidence_file", file);
    form.set("title", values.title);
    form.set("evidence_category", values.evidence_category);
    form.set("context_note", values.context_note);
    if (values.acknowledge_active_use) form.set("acknowledge_active_use", "true");
    upload.send(form);
  });
}

export async function downloadEvidenceDocument(
  id: string,
): Promise<{ blob: Blob; filename: string }> {
  const client = getSupabaseBrowserClient();
  let { data } = await client.auth.getSession();
  if (!data.session?.access_token) throw new ApiError(401, "Please sign in to continue.");
  let response = await fetch(`${apiUrl}/api/v1/documents/${id}/download`, {
    headers: { Authorization: `Bearer ${data.session.access_token}` },
  });
  if (response.status === 401 && data.session.refresh_token) {
    const refreshed = await client.auth.refreshSession();
    data = refreshed.data;
    if (data.session?.access_token) {
      response = await fetch(`${apiUrl}/api/v1/documents/${id}/download`, {
        headers: { Authorization: `Bearer ${data.session.access_token}` },
      });
    }
  }
  if (!response.ok) throw new ApiError(response.status, "We couldn't download the original file just now. Please try again.");
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "evidence";
  return { blob: await response.blob(), filename };
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
  documents: (includeArchived = false) => request<MirrorDocument[]>(
    `/api/v1/documents${includeArchived ? "?include_archived=true" : ""}`,
  ),
  evidence: (includeArchived = false) => request<EvidenceDetail[]>(
    `/api/v1/evidence${includeArchived ? "?include_archived=true" : ""}`,
  ),
  document: (id: string) => request<MirrorDocument>(`/api/v1/documents/${id}`),
  evidenceDetail: (id: string) => request<EvidenceDetail>(`/api/v1/documents/${id}/detail`),
  updateEvidence: (
    id: string,
    values: {
      title?: string;
      evidence_category?: EvidenceCategory;
      context_note?: string | null;
      acknowledge_active_use?: boolean;
    },
  ) => request<EvidenceDetail>(`/api/v1/documents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  }),
  archiveEvidence: (id: string, acknowledge_active_use = false) => request<EvidenceDetail>(
    `/api/v1/documents/${id}/archive`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ acknowledge_active_use }),
    },
  ),
  restoreEvidence: (id: string) => request<EvidenceDetail>(`/api/v1/documents/${id}/restore`, { method: "POST" }),
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
  linkSessionDocuments: (id: string, document_ids: string[]) => request<Session>(`/api/v1/sessions/${id}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_ids }),
  }),
  uploadResume: (id: string, resume: File) => {
    const form = new FormData();
    form.set("resume", resume);
    return request<Session>(`/api/sessions/${id}/resume`, { method: "POST", body: form });
  },
  prepare: (id: string) => request<{ session: Session }>(`/api/sessions/${id}/prepare`, { method: "POST" }),
  session: (id: string) => request<Session>(`/api/v1/sessions/${id}`),
  interviewPlan: (id: string) => request<InterviewPlanResponse>(`/api/v1/sessions/${id}/plan`),
  startInterview: (id: string) => request<InterviewStart>(`/api/v1/sessions/${id}/start`, { method: "POST" }),
  startVoiceInterview: (id: string) => request<VoiceTurnResult>(`/api/v1/sessions/${id}/voice/start`, { method: "POST" }),
  interviewTurns: (id: string) => request<PublicInterviewTurn[]>(`/api/v1/sessions/${id}/turns`),
  sendTextTurn: (id: string, text: string, clientTurnId: string) =>
    request<TextTurnResult>(`/api/v1/sessions/${id}/turn-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, client_turn_id: clientTurnId }),
    }),
  endInterview: (id: string) => request<SessionCompletion>(`/api/v1/sessions/${id}/end`, { method: "POST" }),
  pauseSession: (id: string) =>
    request<{ paused: boolean; remaining_time_seconds: number }>(`/api/v1/sessions/${id}/pause`, { method: "POST" }),
  heartbeat: (id: string, leaseId: string) => request<{ ok: boolean }>(`/api/v1/sessions/${id}/heartbeat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lease_id: leaseId }),
  }),
  assessmentStatus: (id: string) => request<AssessmentPipelineState>(`/api/v1/sessions/${id}/assessment`),
  retryAssessment: (id: string) => request<AssessmentPipelineState>(`/api/v1/sessions/${id}/assessment/retry`, { method: "POST" }),
  dashboard: () => request<DashboardResponse>("/api/v1/dashboard"),
  dashboardSummary: () => request<DashboardSummary>("/api/v1/dashboard/summary"),
  progress: (role?: string) => request<ProgressResponse>(
    `/api/v1/progress${role ? `?role=${encodeURIComponent(role)}` : ""}`,
  ),
  roles: () => request<RoleProfileSummary[]>("/api/v1/roles"),
  interviewMap: (roleProfileId: string) => request<InterviewMap>(`/api/v1/roles/${roleProfileId}/interview-map`),
  pressureTest: (roleProfileId: string) => request<PressureTest>(`/api/v1/roles/${roleProfileId}/pressure-test`),
  setPressureReadiness: (claimId: string, readiness: PressureReadiness) => request<{ claim_id: string; readiness: PressureReadiness }>(
    `/api/v1/pressure-test/${claimId}`,
    { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ readiness }) },
  ),
  answerChecks: (kind: PressureQuestionKind, answer: string) => request<AnswerChecks>("/api/v1/answer-checks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, answer }),
  }),
  stories: () => request<Story[]>("/api/v1/stories"),
  story: (id: string) => request<Story>(`/api/v1/stories/${id}`),
  createStory: (values: StoryInput) => request<Story>("/api/v1/stories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  }),
  updateStory: (id: string, values: Partial<StoryInput>) => request<Story>(`/api/v1/stories/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  }),
  deleteStory: (id: string) => request<void>(`/api/v1/stories/${id}`, { method: "DELETE" }),
  retryTurnAudio: (turnId: string) => request<VoiceTurnResult>(`/api/v1/turns/${turnId}/audio/retry`, { method: "POST" }),
  report: (id: string) => request<ReportResponse>(`/api/v1/sessions/${id}/report`),
  sessionReview: (id: string) => request<SessionReview>(`/api/v1/sessions/${id}/review`),
};


/** Saves the conversation when the tab is closing. `keepalive` lets the request outlive the page. */
export function pauseOnPageExit(sessionId: string, accessToken: string | undefined) {
  if (!accessToken) return;
  try {
    void fetch(`${apiUrl}/api/v1/sessions/${sessionId}/pause`, {
      method: "POST",
      keepalive: true,
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  } catch {
    /* nothing more can be done while the page is closing */
  }
}
