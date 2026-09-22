from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID, uuid4

import httpx
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_settings
from .auth import AuthenticatedUser, get_current_user
from .deferred_writes import get_deferred_writes
from .dependencies import (
    get_dashboard_summary_service,
    get_progress_service,
    get_readiness_service,
    get_story_repository,
    current_user_id,
    get_document_repository,
    get_document_storage,
    get_onboarding_repository,
    get_profile_repository,
    get_repository,
    get_resume_document_parser,
    get_resume_analysis_service,
    get_role_analysis_service,
    get_claims_graph_service,
    get_interview_state_machine,
    get_interview_planning_service,
    get_skeptic_admin_service,
    get_text_interview_service,
    get_voice_interview_service,
    get_report_service,
    get_assessment_pipeline_repository,
    get_dashboard_service,
)
from .interview_engine import (
    ConcurrentSessionChange,
    IllegalSessionTransition,
    InterviewFlowRejected,
    InterviewStateMachine,
    SessionNotFound,
)
from .planner_models import InterviewPlanResponse, PlanningResponse, PlanningStatus
from .planner_repository import (
    InterviewPlanningUnavailable,
    ResumeAnalysisRequired,
    RoleAnalysisRequired,
)
from .planner_service import (
    InterviewPlanningService,
    PlanNotFound,
    SessionNotPlannable,
)
from .interviewer_context import InterviewPlanUnavailableForSession
from .interviewer_models import (
    InterviewStartResponse,
    PublicTurn,
    TextTurnRequest,
    TextTurnResponse,
)
from .interviewer_repository import InterviewTurnsUnavailable
from .interviewer_service import TextInterviewService
from .audio_validation import (
    AudioTooLarge,
    AudioTooShort,
    InvalidAudio,
    UnsupportedAudioType,
)
from .voice_models import VoiceTurnResponse
from .voice_repository import VoicePersistenceUnavailable
from .voice_service import (
    TranscriptionFailed,
    VoiceInterviewService,
    VoiceRequestInProgress,
    VoiceTurnNotFound,
)
from .claims_models import ClaimGraphRead, ClaimRead, ClaimSource, ClaimStatus
from .claims_repository import ClaimsGraphUnavailable
from .claims_service import ClaimNotFound, ClaimsGraphService
from .skeptic_admin import (
    AdminAccessRequired,
    SkepticAdminService,
    SkepticSessionNotFound,
)
from .skeptic_models import SkepticAdminSessionResult
from .skeptic_repository import SkepticPersistenceUnavailable
from .document_ingestion import (
    ALLOWED_RESUME_MIME_TYPES,
    DOCX_MIME,
    detect_resume_mime_type,
    safe_original_filename,
)
from .document_parsing import DocumentParsingError, ResumeDocumentParser
from .document_repository import (
    DocumentRepository,
    DocumentStorage,
    DocumentUnavailable,
    document_type_for_category,
    job_description_values,
)
from .document_library_service import (
    DocumentLibraryService,
    EvidenceActiveUse,
    EvidenceArchived,
    EvidenceNotFound,
)
from .onboarding_repository import OnboardingRepository, OnboardingUnavailable
from .profile_repository import ProfileRepository, ProfileUnavailable
from .repository import SessionRepository
from .resume_models import ClaimCorrectionCreate, ResumeAnalysisResponse
from .resume_repository import ResumeAnalysisNotFound, ResumeAnalysisUnavailable
from .resume_service import (
    ResumeAnalysisService,
    ResumeNotFound,
    UnsupportedResumeDocument,
)
from .role_models import (
    RoleAnalysisResponse,
    RoleAnalyzeRequest,
    RoleProfileRead,
    StoredRoleCompetency,
)
from .role_repository import RoleAnalysisUnavailable
from .role_service import (
    InvalidRoleSourceDocument,
    RoleAnalysisService,
    RoleProfileNotFoundForUser,
    RoleProfileTargetMismatch,
)
from .schemas import (
    DocumentRead,
    DocumentStatus,
    DocumentType,
    EvidenceArchiveRequest,
    EvidenceCategory,
    EvidenceDetail,
    EvidenceMetadataUpdate,
    JobDescriptionCreate,
    OnboardingRead,
    OnboardingUpdate,
    PrepareResponse,
    ProfileRead,
    ProfileUpdate,
    SessionCreate,
    SessionDocumentsLink,
    SessionPatch,
    SessionRead,
    SessionStatus,
    onboarding_is_complete,
)
from .report_models import ReportResponse
from .assessment_pipeline_models import AssessmentPipelineState
from .assessment_pipeline_models import SessionCompletionResponse
from .assessment_pipeline_repository import AssessmentPipelineRepository, AssessmentPipelineUnavailable
from .report_service import ReportAssessmentIncomplete, ReportNotFound, ReportService, ReportUnavailable
from .dashboard_models import DashboardResponse
from .dashboard_repository import DashboardUnavailable
from .dashboard_service import DashboardService
from .dashboard_summary import (
    DashboardSummaryResponse,
    DashboardSummaryService,
    LatestReview,
    build_latest_review,
)
from .progress_summary import ProgressResponse, ProgressService
from .interview_map import InterviewMap
from .readiness_service import ClaimNotFoundForUser, ReadinessService
from .pressure_test import (
    AnswerCheckRequest,
    AnswerChecks,
    PressureResponse,
    PressureTest,
    ReadinessUpdate,
    check_answer,
)
from .story_models import StoryCreate, StoryUpdate, StoryView, story_view
from .story_repository import StoriesUnavailable, StoryRepository

settings = get_settings()

# Uvicorn configures only its own loggers, so without an explicit handler every
# "mirror.*" warning is discarded and operational failures surface to callers as
# bare status codes with no matching server-side record.
_mirror_logger = logging.getLogger("mirror")
if not _mirror_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    _mirror_logger.addHandler(_handler)
    _mirror_logger.setLevel(logging.INFO)
    _mirror_logger.propagate = False

logger = logging.getLogger("mirror.lifecycle")


def _evidence_category(value: str) -> EvidenceCategory:
    try:
        return EvidenceCategory(value.strip().upper())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Please choose a category from the list.") from exc


def _evidence_title(value: str | None, fallback: str) -> str:
    cleaned = " ".join((value or fallback).split())
    if not cleaned or len(cleaned) > 160:
        raise HTTPException(status_code=422, detail="Please give this a title between 1 and 160 characters.")
    return cleaned


def _active_evidence_conflict(exc: EvidenceActiveUse) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "EVIDENCE_ACTIVE_USE",
            "message": "This is part of a session in progress. Please confirm that the change should apply only to future sessions.",
            "usage": exc.usage.model_dump(mode="json"),
        },
    )


app = FastAPI(title="Mirror API", version="0.1.0", docs_url="/api/docs")


@app.on_event("shutdown")
async def _flush_deferred_writes() -> None:
    await get_deferred_writes().flush_all()


@app.on_event("startup")
async def _start_idle_pause_loop() -> None:
    # Registry is in-memory and lost on restart; see session_liveness.py.
    import asyncio
    from .session_liveness import run_idle_pause_loop

    app.state.idle_pause_task = asyncio.create_task(
        run_idle_pause_loop(get_interview_state_machine, get_deferred_writes, settings.session_idle_pause_seconds)
    )


@app.on_event("shutdown")
async def _stop_idle_pause_loop() -> None:
    task = getattr(app.state, "idle_pause_task", None)
    if task:
        task.cancel()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/api/v1/sessions/{session_id}/report", response_model=ReportResponse)
async def read_session_report(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    report: ReportService = Depends(get_report_service),
) -> ReportResponse:
    try:
        return await report.get_report(session_id, user.id)
    except ReportNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that reflection.") from exc
    except ReportAssessmentIncomplete as exc:
        raise HTTPException(status_code=409, detail="Your reflection isn't ready yet. Please check back shortly.") from exc
    except ReportUnavailable as exc:
        raise HTTPException(status_code=503, detail="Your reflection isn't available right now. Please try again in a moment.") from exc


@app.get("/api/v1/sessions/{session_id}/review", response_model=LatestReview)
async def read_session_review(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    report: ReportService = Depends(get_report_service),
) -> LatestReview:
    """The same plain-language reading of one review that the Home page shows."""
    try:
        return build_latest_review(session_id, await report.get_report(session_id, user.id))
    except ReportNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that review.") from exc
    except ReportAssessmentIncomplete as exc:
        raise HTTPException(status_code=409, detail="Your review isn't ready yet. Please check back shortly.") from exc
    except ReportUnavailable as exc:
        raise HTTPException(status_code=503, detail="Your review isn't available right now. Please try again in a moment.") from exc


@app.get("/api/v1/sessions/{session_id}/assessment", response_model=AssessmentPipelineState)
async def read_assessment_status(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: AssessmentPipelineRepository = Depends(get_assessment_pipeline_repository),
) -> AssessmentPipelineState:
    try:
        state = await repository.status(session_id, user.id)
    except AssessmentPipelineUnavailable as exc:
        raise HTTPException(status_code=503, detail="Your reflection can't be prepared right now. Please try again in a moment.") from exc
    if state is None:
        raise HTTPException(status_code=404, detail="We couldn't find that reflection.")
    return state


@app.post(
    "/api/v1/sessions/{session_id}/assessment/retry",
    response_model=AssessmentPipelineState,
)
async def retry_assessment(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: AssessmentPipelineRepository = Depends(get_assessment_pipeline_repository),
) -> AssessmentPipelineState:
    try:
        state = await repository.retry(session_id, user.id)
        logger.info(
            "assessment retry requested",
            extra={"session_id": str(session_id), "user_id": str(user.id)},
        )
        return state
    except AssessmentPipelineUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="We can't try that again right now. Please try again in a moment.",
        ) from exc


@app.get("/api/v1/dashboard", response_model=DashboardResponse)
async def read_dashboard(
    user: AuthenticatedUser = Depends(get_current_user),
    dashboard: DashboardService = Depends(get_dashboard_service),
) -> DashboardResponse:
    try:
        return await dashboard.workspace(user.id)
    except DashboardUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Your space isn't available right now. Please try again in a moment.",
        ) from exc


@app.get("/api/v1/dashboard/summary", response_model=DashboardSummaryResponse)
async def read_dashboard_summary(
    user: AuthenticatedUser = Depends(get_current_user),
    summary: DashboardSummaryService = Depends(get_dashboard_summary_service),
) -> DashboardSummaryResponse:
    """What the Home page shows about the latest finished review."""
    try:
        return await summary.summary(user.id)
    except DashboardUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Your space isn't available right now. Please try again in a moment.",
        ) from exc


@app.get("/api/v1/progress", response_model=ProgressResponse)
async def read_progress(
    role: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    progress: ProgressService = Depends(get_progress_service),
) -> ProgressResponse:
    """How someone's answers are developing across their finished practices."""
    try:
        return await progress.progress(user.id, role)
    except DashboardUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Your space isn't available right now. Please try again in a moment.",
        ) from exc


@app.get(
    "/api/v1/admin/sessions/{session_id}/skeptic",
    response_model=SkepticAdminSessionResult,
)
async def inspect_skeptic_shadow_results(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    service: SkepticAdminService = Depends(get_skeptic_admin_service),
) -> SkepticAdminSessionResult:
    try:
        return await service.inspect(session_id, user.id)
    except AdminAccessRequired as exc:
        raise HTTPException(status_code=403, detail="Admin access required") from exc
    except SkepticSessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except SkepticPersistenceUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Skeptic inspection is temporarily unavailable"
        ) from exc


@app.get("/api/v1/claims", response_model=list[ClaimRead])
async def list_claims(
    skill: str | None = Query(default=None, min_length=1, max_length=500),
    project: str | None = Query(default=None, min_length=1, max_length=500),
    claim_status: ClaimStatus | None = Query(default=None, alias="status"),
    source: ClaimSource | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ClaimsGraphService = Depends(get_claims_graph_service),
) -> list[ClaimRead]:
    try:
        return await service.get_claims_for_user(
            user.id,
            skill=skill,
            project=project,
            status=claim_status,
            source=source,
        )
    except ClaimsGraphUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="This isn't available right now. Please try again in a moment."
        ) from exc


@app.get("/api/v1/claims/{claim_id}", response_model=ClaimGraphRead)
async def read_claim(
    claim_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ClaimsGraphService = Depends(get_claims_graph_service),
) -> ClaimGraphRead:
    try:
        return await service.get_claim(claim_id, user.id)
    except ClaimNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except ClaimsGraphUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="This isn't available right now. Please try again in a moment."
        ) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/api/v1/me", response_model=ProfileRead)
async def read_me(
    user: AuthenticatedUser = Depends(get_current_user),
    repository: ProfileRepository = Depends(get_profile_repository),
) -> ProfileRead:
    try:
        return await repository.reconcile(user)
    except ProfileUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Your profile isn't available right now. Please try again in a moment.",
        ) from exc


@app.patch("/api/v1/me", response_model=ProfileRead)
async def update_me(
    payload: ProfileUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: ProfileRepository = Depends(get_profile_repository),
) -> ProfileRead:
    try:
        await repository.reconcile(user)
        return await repository.update_full_name(user.id, payload.full_name)
    except ProfileUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Your profile isn't available right now. Please try again in a moment.",
        ) from exc


@app.get("/api/v1/onboarding", response_model=OnboardingRead)
async def read_onboarding(
    user: AuthenticatedUser = Depends(get_current_user),
    profiles: ProfileRepository = Depends(get_profile_repository),
    onboarding: OnboardingRepository = Depends(get_onboarding_repository),
) -> OnboardingRead:
    try:
        await profiles.reconcile(user)
        return await onboarding.get(user.id)
    except (ProfileUnavailable, OnboardingUnavailable) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Setup isn't available right now. Please try again in a moment.",
        ) from exc


@app.put("/api/v1/onboarding", response_model=OnboardingRead)
async def update_onboarding(
    payload: OnboardingUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    profiles: ProfileRepository = Depends(get_profile_repository),
    onboarding: OnboardingRepository = Depends(get_onboarding_repository),
) -> OnboardingRead:
    try:
        await profiles.reconcile(user)
        current = await onboarding.get(user.id)
        values = payload.model_dump(exclude_unset=True)
        proposed = current.model_copy(update=values)
        if payload.onboarding_completed is True and not onboarding_is_complete(
            proposed
        ):
            raise HTTPException(
                status_code=422,
                detail="Please finish the required setup steps before continuing.",
            )
        return await onboarding.update(user.id, values)
    except HTTPException:
        raise
    except (ProfileUnavailable, OnboardingUnavailable) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Setup isn't available right now. Please try again in a moment.",
        ) from exc


@app.post(
    "/api/v1/documents/resume",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_resume_document(
    resume: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> DocumentRead:
    declared_mime = resume.content_type or ""
    if declared_mime not in ALLOWED_RESUME_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Please choose a PDF or DOCX file for your resume.")

    maximum_size = settings.resume_max_file_size_bytes
    if maximum_size <= 0:
        raise HTTPException(
            status_code=503, detail="Resume upload isn't available right now. Please try again in a moment."
        )
    content = await resume.read(maximum_size + 1)
    if len(content) > maximum_size:
        raise HTTPException(
            status_code=413, detail="That resume is larger than the size limit. Please try a smaller file."
        )

    detected_mime = detect_resume_mime_type(content)
    if detected_mime is None or detected_mime != declared_mime:
        raise HTTPException(
            status_code=415,
            detail="That file doesn't look like a PDF or DOCX. Please try a different file.",
        )

    document_id = uuid4()
    extension = "docx" if detected_mime == DOCX_MIME else "pdf"
    storage_path = f"{user.id}/documents/{document_id}/resume.{extension}"
    try:
        await storage.upload(storage_path, content, detected_mime)
        try:
            return await repository.create(
                {
                    "id": document_id,
                    "user_id": user.id,
                    "document_type": DocumentType.RESUME,
                    "storage_path": storage_path,
                    "original_filename": safe_original_filename(
                        resume.filename, detected_mime
                    ),
                    "title": _evidence_title(resume.filename, "Resume"),
                    "evidence_category": EvidenceCategory.RESUME,
                    "mime_type": detected_mime,
                    "status": DocumentStatus.UPLOADED,
                }
            )
        except DocumentUnavailable:
            try:
                await storage.delete(storage_path)
            except DocumentUnavailable:
                pass
            raise
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume upload isn't available right now. Please try again in a moment.",
        ) from exc


@app.post(
    "/api/v1/documents/job-description",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_description_document(
    payload: JobDescriptionCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
) -> DocumentRead:
    try:
        return await repository.create(
            job_description_values(user.id, payload.raw_text)
        )
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Documents aren't available right now. Please try again in a moment.",
        ) from exc


@app.post(
    "/api/v1/documents/job-description/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_job_description_document(
    role_brief: UploadFile = File(...),
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
    parser: ResumeDocumentParser = Depends(get_resume_document_parser),
) -> DocumentRead:
    declared_mime = role_brief.content_type or ""
    if declared_mime not in ALLOWED_RESUME_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Please choose a PDF or DOCX file for the role brief.")

    maximum_size = settings.resume_max_file_size_bytes
    if maximum_size <= 0:
        raise HTTPException(
            status_code=503, detail="Role brief upload isn't available right now. Please try again in a moment."
        )
    content = await role_brief.read(maximum_size + 1)
    if len(content) > maximum_size:
        raise HTTPException(
            status_code=413, detail="That role brief is larger than the size limit. Please try a smaller file."
        )
    detected_mime = detect_resume_mime_type(content)
    if detected_mime is None or detected_mime != declared_mime:
        raise HTTPException(
            status_code=415,
            detail="That file doesn't look like a PDF or DOCX. Please try a different file.",
        )
    try:
        raw_text = parser.extract(content, detected_mime)
    except DocumentParsingError as exc:
        raise HTTPException(
            status_code=422,
            detail="We couldn't read text from this role brief. Please try a text-based PDF or DOCX file.",
        ) from exc

    document_id = uuid4()
    extension = "docx" if detected_mime == DOCX_MIME else "pdf"
    storage_path = f"{user.id}/documents/{document_id}/role-brief.{extension}"
    try:
        await storage.upload(storage_path, content, detected_mime)
        try:
            return await repository.create(
                {
                    "id": document_id,
                    "user_id": user.id,
                    "document_type": DocumentType.JOB_DESCRIPTION,
                    "storage_path": storage_path,
                    "original_filename": safe_original_filename(
                        role_brief.filename,
                        detected_mime,
                        fallback_stem="role-brief",
                    ),
                    "title": _evidence_title(role_brief.filename, "Role brief"),
                    "evidence_category": EvidenceCategory.ROLE_BRIEF,
                    "mime_type": detected_mime,
                    "raw_text": raw_text,
                    "status": DocumentStatus.PROCESSED,
                    "processed_at": datetime.now(UTC).isoformat(),
                }
            )
        except DocumentUnavailable:
            try:
                await storage.delete(storage_path)
            except DocumentUnavailable:
                pass
            raise
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Role brief upload isn't available right now. Please try again in a moment.",
        ) from exc


@app.get("/api/v1/evidence", response_model=list[EvidenceDetail])
async def list_evidence_library(
    include_archived: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> list[EvidenceDetail]:
    try:
        return await DocumentLibraryService(repository, storage).list(
            user.id,
            include_archived=include_archived,
        )
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="Your experience library isn't available right now. Please try again in a moment.") from exc


@app.post(
    "/api/v1/evidence",
    response_model=EvidenceDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_evidence(
    evidence_file: UploadFile = File(...),
    title: str | None = Form(default=None),
    evidence_category: str = Form(default=EvidenceCategory.OTHER.value),
    context_note: str | None = Form(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
    parser: ResumeDocumentParser = Depends(get_resume_document_parser),
) -> EvidenceDetail:
    if settings.resume_max_file_size_bytes <= 0:
        raise HTTPException(status_code=503, detail="Uploads aren't available right now. Please try again later.")
    declared_mime = evidence_file.content_type or ""
    if declared_mime not in ALLOWED_RESUME_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Please choose a PDF or DOCX file.")
    content = await evidence_file.read(settings.resume_max_file_size_bytes + 1)
    if len(content) > settings.resume_max_file_size_bytes:
        raise HTTPException(status_code=413, detail="That file is larger than the size limit. Please try a smaller file.")
    detected_mime = detect_resume_mime_type(content)
    if detected_mime is None or detected_mime != declared_mime:
        raise HTTPException(status_code=415, detail="That file doesn't look like a PDF or DOCX. Please try a different file.")

    category = _evidence_category(evidence_category)
    context = (context_note or "").strip() or None
    if context and len(context) > 4_000:
        raise HTTPException(status_code=422, detail="Please keep the note to 4000 characters or fewer.")
    document_type = document_type_for_category(category.value)
    raw_text = None
    document_status = DocumentStatus.UPLOADED
    processed_at = None
    if document_type != DocumentType.RESUME:
        try:
            raw_text = parser.extract(content, detected_mime)
        except DocumentParsingError as exc:
            raise HTTPException(status_code=422, detail="We couldn't read this file just now. Please try another PDF or DOCX.") from exc
        document_status = DocumentStatus.PROCESSED
        processed_at = datetime.now(UTC).isoformat()

    document_id = uuid4()
    extension = "docx" if detected_mime == DOCX_MIME else "pdf"
    storage_path = f"{user.id}/documents/{document_id}/evidence.{extension}"
    original_filename = safe_original_filename(
        evidence_file.filename,
        detected_mime,
        fallback_stem="evidence",
    )
    try:
        await storage.upload(storage_path, content, detected_mime)
        try:
            document = await repository.create(
                {
                    "id": document_id,
                    "user_id": user.id,
                    "document_type": document_type,
                    "storage_path": storage_path,
                    "original_filename": original_filename,
                    "mime_type": detected_mime,
                    "raw_text": raw_text,
                    "status": document_status,
                    "processed_at": processed_at,
                    "title": _evidence_title(title, original_filename),
                    "evidence_category": category,
                    "context_note": context,
                }
            )
        except DocumentUnavailable:
            try:
                await storage.delete(storage_path)
            except DocumentUnavailable:
                pass
            raise
        return EvidenceDetail(
            document=document,
            usage={"active_diagnostic_count": 0, "completed_diagnostic_count": 0},
        )
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="Uploads aren't available right now. Please try again in a moment.") from exc


@app.get("/api/v1/documents", response_model=list[DocumentRead])
async def list_documents(
    include_archived: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
) -> list[DocumentRead]:
    try:
        return await repository.list_for_user(user.id, include_archived=include_archived)
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Documents aren't available right now. Please try again in a moment.",
        ) from exc


@app.get("/api/v1/documents/{document_id}", response_model=DocumentRead)
async def read_document(
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
) -> DocumentRead:
    try:
        document = await repository.get_for_user(document_id, user.id)
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Documents aren't available right now. Please try again in a moment.",
        ) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="We couldn't find that document.")
    return document


@app.get("/api/v1/documents/{document_id}/detail", response_model=EvidenceDetail)
async def read_evidence_detail(
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> EvidenceDetail:
    try:
        return await DocumentLibraryService(repository, storage).detail(document_id, user.id)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="Those details aren't available right now. Please try again in a moment.") from exc


@app.patch("/api/v1/documents/{document_id}", response_model=EvidenceDetail)
async def update_evidence_metadata(
    document_id: UUID,
    payload: EvidenceMetadataUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> EvidenceDetail:
    values = payload.model_dump(
        exclude={"acknowledge_active_use"},
        exclude_unset=True,
    )
    try:
        return await DocumentLibraryService(repository, storage).update_metadata(
            document_id,
            user.id,
            values,
            acknowledge_active_use=payload.acknowledge_active_use,
        )
    except EvidenceActiveUse as exc:
        raise _active_evidence_conflict(exc)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except EvidenceArchived as exc:
        raise HTTPException(status_code=409, detail="Please restore this before editing it.") from exc
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="We couldn't update this just now. Your original details are unchanged.") from exc


@app.post("/api/v1/documents/{document_id}/archive", response_model=EvidenceDetail)
async def archive_evidence(
    document_id: UUID,
    payload: EvidenceArchiveRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> EvidenceDetail:
    try:
        return await DocumentLibraryService(repository, storage).archive(
            document_id,
            user.id,
            acknowledge_active_use=payload.acknowledge_active_use,
        )
    except EvidenceActiveUse as exc:
        raise _active_evidence_conflict(exc)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except EvidenceArchived as exc:
        raise HTTPException(status_code=409, detail="This has already been removed from your library.") from exc
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="We couldn't remove this just now. It's still in your library.") from exc


@app.post("/api/v1/documents/{document_id}/restore", response_model=EvidenceDetail)
async def restore_evidence(
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> EvidenceDetail:
    try:
        return await DocumentLibraryService(repository, storage).restore(document_id, user.id)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="We couldn't restore this just now. Please try again.") from exc


@app.get("/api/v1/documents/{document_id}/download")
async def download_evidence(
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> Response:
    try:
        document = await repository.get_for_user(document_id, user.id)
        if document is None or not document.storage_path:
            raise HTTPException(status_code=404, detail="We couldn't find the original file.")
        content = await storage.download(document.storage_path)
        filename = (document.original_filename or "evidence").replace('"', "")
        return Response(
            content=content,
            media_type=document.mime_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="The original file isn't available right now. Please try again in a moment.") from exc


@app.post("/api/v1/documents/{document_id}/replace", response_model=EvidenceDetail)
async def replace_evidence_file(
    document_id: UUID,
    evidence_file: UploadFile = File(...),
    title: str | None = Form(default=None),
    evidence_category: str | None = Form(default=None),
    context_note: str | None = Form(default=None),
    acknowledge_active_use: bool = Form(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
    parser: ResumeDocumentParser = Depends(get_resume_document_parser),
) -> EvidenceDetail:
    service = DocumentLibraryService(repository, storage)
    try:
        current = await service.detail(document_id, user.id)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="Those details aren't available right now. Please try again in a moment.") from exc

    if settings.resume_max_file_size_bytes <= 0:
        raise HTTPException(status_code=503, detail="Uploads aren't available right now. Please try again later.")
    declared_mime = evidence_file.content_type or ""
    if declared_mime not in ALLOWED_RESUME_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Please choose a PDF or DOCX file.")
    content = await evidence_file.read(settings.resume_max_file_size_bytes + 1)
    if len(content) > settings.resume_max_file_size_bytes:
        raise HTTPException(status_code=413, detail="That file is larger than the size limit. Please try a smaller file.")
    detected_mime = detect_resume_mime_type(content)
    if detected_mime is None or detected_mime != declared_mime:
        raise HTTPException(status_code=415, detail="That file doesn't look like a PDF or DOCX. Please try a different file.")

    current_document = current.document
    category = (
        _evidence_category(evidence_category)
        if evidence_category
        else current_document.evidence_category
        or EvidenceCategory.OTHER
    )
    next_context = current_document.context_note if context_note is None else context_note.strip() or None
    if next_context and len(next_context) > 4_000:
        raise HTTPException(status_code=422, detail="Please keep the note to 4000 characters or fewer.")
    document_type = document_type_for_category(category.value)
    raw_text = None
    document_status = DocumentStatus.UPLOADED
    processed_at = None
    if document_type != DocumentType.RESUME:
        try:
            raw_text = parser.extract(content, detected_mime)
        except DocumentParsingError as exc:
            raise HTTPException(status_code=422, detail="We couldn't read the new file just now. Your original file is unchanged.") from exc
        document_status = DocumentStatus.PROCESSED
        processed_at = datetime.now(UTC).isoformat()

    replacement_id = uuid4()
    extension = "docx" if detected_mime == DOCX_MIME else "pdf"
    storage_path = f"{user.id}/documents/{replacement_id}/evidence.{extension}"
    original_filename = safe_original_filename(
        evidence_file.filename,
        detected_mime,
        fallback_stem="evidence",
    )
    try:
        return await service.replace(
            document_id,
            user.id,
            {
                "id": replacement_id,
                "document_type": document_type,
                "storage_path": storage_path,
                "original_filename": original_filename,
                "mime_type": detected_mime,
                "raw_text": raw_text,
                "status": document_status,
                "processed_at": processed_at,
                "title": _evidence_title(title, current_document.title or original_filename),
                "evidence_category": category,
                "context_note": next_context,
            },
            content,
            acknowledge_active_use=acknowledge_active_use,
        )
    except EvidenceActiveUse as exc:
        raise _active_evidence_conflict(exc)
    except EvidenceArchived as exc:
        raise HTTPException(status_code=409, detail="Please restore this before replacing its file.") from exc
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except DocumentUnavailable as exc:
        raise HTTPException(status_code=503, detail="We couldn't replace this just now. Your original file is unchanged.") from exc


@app.delete("/api/v1/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    acknowledge_active_use: bool = Query(default=False),
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> Response:
    try:
        await DocumentLibraryService(repository, storage).archive(
            document_id,
            user.id,
            acknowledge_active_use=acknowledge_active_use,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except EvidenceActiveUse as exc:
        raise _active_evidence_conflict(exc)
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except EvidenceArchived:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We couldn't remove this just now. It's still in your library.",
        ) from exc


@app.post(
    "/api/v1/resumes/{document_id}/analyze",
    response_model=ResumeAnalysisResponse,
)
async def analyze_resume(
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    onboarding: OnboardingRepository = Depends(get_onboarding_repository),
    service: ResumeAnalysisService = Depends(get_resume_analysis_service),
) -> ResumeAnalysisResponse:
    try:
        profile = await onboarding.get(user.id)
        return await service.analyze(document_id, user.id, profile)
    except ResumeNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that resume.") from exc
    except UnsupportedResumeDocument as exc:
        raise HTTPException(status_code=422, detail="That document isn't a resume.") from exc
    except (
        DocumentUnavailable,
        OnboardingUnavailable,
        ResumeAnalysisUnavailable,
    ) as exc:
        raise HTTPException(
            status_code=503, detail="Reading your resume isn't available right now. Please try again in a moment."
        ) from exc


@app.get(
    "/api/v1/resumes/{document_id}/analysis",
    response_model=ResumeAnalysisResponse,
)
async def read_resume_analysis(
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeAnalysisService = Depends(get_resume_analysis_service),
) -> ResumeAnalysisResponse:
    try:
        return await service.get(document_id, user.id)
    except ResumeNotFound as exc:
        raise HTTPException(
            status_code=404, detail="We couldn't find that."
        ) from exc
    except UnsupportedResumeDocument as exc:
        raise HTTPException(status_code=422, detail="That document isn't a resume.") from exc
    except (DocumentUnavailable, ResumeAnalysisUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Reading your resume isn't available right now. Please try again in a moment."
        ) from exc


@app.post(
    "/api/v1/resumes/{document_id}/analysis/claims/{claim_id}/corrections",
    response_model=ResumeAnalysisResponse,
)
async def correct_resume_claim(
    document_id: UUID,
    claim_id: UUID,
    payload: ClaimCorrectionCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeAnalysisService = Depends(get_resume_analysis_service),
) -> ResumeAnalysisResponse:
    try:
        return await service.correct_claim(document_id, user.id, claim_id, payload)
    except (ResumeNotFound, ResumeAnalysisNotFound) as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that item.") from exc
    except UnsupportedResumeDocument as exc:
        raise HTTPException(status_code=422, detail="That document isn't a resume.") from exc
    except (DocumentUnavailable, ResumeAnalysisUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Reading your resume isn't available right now. Please try again in a moment."
        ) from exc


@app.post("/api/v1/roles/analyze", response_model=RoleAnalysisResponse)
async def analyze_role(
    payload: RoleAnalyzeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    onboarding: OnboardingRepository = Depends(get_onboarding_repository),
    service: RoleAnalysisService = Depends(get_role_analysis_service),
) -> RoleAnalysisResponse:
    try:
        profile = await onboarding.get(user.id)
        return await service.analyze(payload, user.id, profile)
    except InvalidRoleSourceDocument as exc:
        raise HTTPException(
            status_code=422, detail="We couldn't find that job description."
        ) from exc
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that role.") from exc
    except RoleProfileTargetMismatch as exc:
        raise HTTPException(
            status_code=409, detail="That belongs to a different target role."
        ) from exc
    except (DocumentUnavailable, OnboardingUnavailable, RoleAnalysisUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Getting to know the role isn't available right now. Please try again in a moment."
        ) from exc


@app.get("/api/v1/roles", response_model=list[RoleProfileRead])
async def list_role_profiles(
    user: AuthenticatedUser = Depends(get_current_user),
    service: RoleAnalysisService = Depends(get_role_analysis_service),
) -> list[RoleProfileRead]:
    """The roles this person is preparing for, newest first."""
    try:
        return await service.list_profiles(user.id)
    except RoleAnalysisUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Getting to know the role isn't available right now. Please try again in a moment."
        ) from exc


@app.get("/api/v1/roles/{role_profile_id}/interview-map", response_model=InterviewMap)
async def read_interview_map(
    role_profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    readiness: ReadinessService = Depends(get_readiness_service),
) -> InterviewMap:
    """What this role is likely to explore, next to what you can already show for it."""
    try:
        return await readiness.interview_map(role_profile_id, user.id)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that role.") from exc
    except (RoleAnalysisUnavailable, DocumentUnavailable, StoriesUnavailable, DashboardUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Your interview map isn't available right now. Please try again in a moment."
        ) from exc


@app.get("/api/v1/roles/{role_profile_id}/pressure-test", response_model=PressureTest)
async def read_pressure_test(
    role_profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    readiness: ReadinessService = Depends(get_readiness_service),
) -> PressureTest:
    """Follow-up questions your resume statements invite, most relevant to this role first."""
    try:
        return await readiness.pressure_test(role_profile_id, user.id)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that role.") from exc
    except (RoleAnalysisUnavailable, DocumentUnavailable, StoriesUnavailable) as exc:
        raise HTTPException(status_code=503, detail="This isn't available right now. Please try again in a moment.") from exc


@app.put("/api/v1/pressure-test/{claim_id}", response_model=PressureResponse)
async def set_pressure_readiness(
    claim_id: UUID,
    payload: ReadinessUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    readiness: ReadinessService = Depends(get_readiness_service),
) -> PressureResponse:
    try:
        return await readiness.set_readiness(claim_id, user.id, payload.readiness)
    except ClaimNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that statement on your resume.") from exc
    except (DocumentUnavailable, StoriesUnavailable) as exc:
        raise HTTPException(status_code=503, detail="We couldn't save that just now. Please try again in a moment.") from exc


@app.post("/api/v1/answer-checks", response_model=AnswerChecks)
async def run_answer_checks(
    payload: AnswerCheckRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AnswerChecks:
    """What a practice answer contains. Nothing is stored and nothing is graded."""
    return check_answer(payload)


@app.get("/api/v1/stories", response_model=list[StoryView])
async def list_stories(
    user: AuthenticatedUser = Depends(get_current_user),
    stories: StoryRepository = Depends(get_story_repository),
) -> list[StoryView]:
    try:
        return [story_view(story) for story in await stories.list_for_user(user.id)]
    except StoriesUnavailable as exc:
        raise HTTPException(status_code=503, detail="Your stories aren't available right now. Please try again in a moment.") from exc


@app.post("/api/v1/stories", response_model=StoryView, status_code=201)
async def create_story(
    payload: StoryCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    stories: StoryRepository = Depends(get_story_repository),
    roles: RoleAnalysisService = Depends(get_role_analysis_service),
) -> StoryView:
    try:
        if payload.role_profile_id is not None:
            await roles.get(payload.role_profile_id, user.id)
        return story_view(await stories.create(user.id, payload))
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that role.") from exc
    except (StoriesUnavailable, RoleAnalysisUnavailable) as exc:
        raise HTTPException(status_code=503, detail="We couldn't save your story just now. Please try again in a moment.") from exc


@app.get("/api/v1/stories/{story_id}", response_model=StoryView)
async def read_story(
    story_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    stories: StoryRepository = Depends(get_story_repository),
) -> StoryView:
    try:
        story = await stories.get(story_id, user.id)
    except StoriesUnavailable as exc:
        raise HTTPException(status_code=503, detail="Your story isn't available right now. Please try again in a moment.") from exc
    if story is None:
        raise HTTPException(status_code=404, detail="We couldn't find that story.")
    return story_view(story)


@app.patch("/api/v1/stories/{story_id}", response_model=StoryView)
async def update_story(
    story_id: UUID,
    payload: StoryUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    stories: StoryRepository = Depends(get_story_repository),
    roles: RoleAnalysisService = Depends(get_role_analysis_service),
) -> StoryView:
    try:
        if payload.role_profile_id is not None:
            await roles.get(payload.role_profile_id, user.id)
        story = await stories.update(story_id, user.id, payload)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that role.") from exc
    except (StoriesUnavailable, RoleAnalysisUnavailable) as exc:
        raise HTTPException(status_code=503, detail="We couldn't save your story just now. Please try again in a moment.") from exc
    if story is None:
        raise HTTPException(status_code=404, detail="We couldn't find that story.")
    return story_view(story)


@app.delete("/api/v1/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(
    story_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    stories: StoryRepository = Depends(get_story_repository),
) -> Response:
    try:
        removed = await stories.delete(story_id, user.id)
    except StoriesUnavailable as exc:
        raise HTTPException(status_code=503, detail="We couldn't remove your story just now. Please try again in a moment.") from exc
    if not removed:
        raise HTTPException(status_code=404, detail="We couldn't find that story.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/roles/{role_profile_id}", response_model=RoleAnalysisResponse)
async def read_role_profile(
    role_profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    service: RoleAnalysisService = Depends(get_role_analysis_service),
) -> RoleAnalysisResponse:
    try:
        return await service.get(role_profile_id, user.id)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that role.") from exc
    except RoleAnalysisUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Getting to know the role isn't available right now. Please try again in a moment."
        ) from exc


@app.get(
    "/api/v1/roles/{role_profile_id}/competencies",
    response_model=list[StoredRoleCompetency],
)
async def read_role_competencies(
    role_profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    service: RoleAnalysisService = Depends(get_role_analysis_service),
) -> list[StoredRoleCompetency]:
    try:
        return await service.competencies(role_profile_id, user.id)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that role.") from exc
    except RoleAnalysisUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Getting to know the role isn't available right now. Please try again in a moment."
        ) from exc


@app.post("/api/v1/sessions", response_model=SessionRead, status_code=201)
@app.post("/api/sessions", response_model=SessionRead, status_code=201)
async def create_session(
    payload: SessionCreate,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
) -> SessionRead:
    return await engine.create_session_state(user_id, payload)


@app.post(
    "/api/v1/sessions/{session_id}/documents",
    response_model=SessionRead,
)
async def link_session_documents(
    session_id: UUID,
    payload: SessionDocumentsLink,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
    documents: DocumentRepository = Depends(get_document_repository),
) -> SessionRead:
    try:
        session = await engine.get_state(session_id, user_id)
        for document_id in payload.document_ids:
            document = await documents.get_for_user(document_id, user_id)
            if document is None:
                raise HTTPException(status_code=404, detail="We couldn't find that document.")
            if document.archived_at is not None:
                raise HTTPException(
                    status_code=409,
                    detail="Please restore this before using it in a session.",
                )
            if document.document_type not in (
                DocumentType.RESUME,
                DocumentType.JOB_DESCRIPTION,
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Only a resume and a role brief can be added to a session.",
                )
            await documents.link_to_session(session_id, document_id)
        return session
    except HTTPException:
        raise
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Adding documents isn't available right now. Please try again in a moment."
        ) from exc


@app.get("/api/v1/sessions/{session_id}", response_model=SessionRead)
@app.get("/api/sessions/{session_id}", response_model=SessionRead)
async def read_session(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
) -> SessionRead:
    try:
        return await engine.get_state(session_id, user_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc


@app.post("/api/sessions/{session_id}/jd", response_model=SessionRead)
async def save_job_description(
    session_id: UUID,
    payload: SessionPatch,
    user_id: UUID = Depends(current_user_id),
    repository: SessionRepository = Depends(get_repository),
) -> SessionRead:
    session = await repository.update(session_id, user_id, {"jd_text": payload.jd_text})
    if not session:
        raise HTTPException(status_code=404, detail="We couldn't find that session.")
    return session


@app.post("/api/sessions/{session_id}/resume", response_model=SessionRead)
async def upload_resume(
    session_id: UUID,
    resume: UploadFile = File(...),
    user_id: UUID = Depends(current_user_id),
    repository: SessionRepository = Depends(get_repository),
) -> SessionRead:
    declared_mime = resume.content_type or ""
    if declared_mime not in ALLOWED_RESUME_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Please choose a PDF or DOCX file for your resume.")
    if settings.resume_max_file_size_bytes <= 0:
        raise HTTPException(
            status_code=503, detail="Resume upload isn't available right now. Please try again in a moment."
        )
    content = await resume.read(settings.resume_max_file_size_bytes + 1)
    if len(content) > settings.resume_max_file_size_bytes:
        raise HTTPException(
            status_code=413, detail="That resume is larger than the size limit. Please try a smaller file."
        )
    detected_mime = detect_resume_mime_type(content)
    if detected_mime is None or detected_mime != declared_mime:
        raise HTTPException(
            status_code=415,
            detail="That file doesn't look like a PDF or DOCX. Please try a different file.",
        )
    safe_name = "resume.pdf" if detected_mime == "application/pdf" else "resume.docx"
    object_path = f"{user_id}/{session_id}/{safe_name}"
    if settings.supabase_enabled:
        # An unhandled transport error here escapes the CORS middleware, so the
        # browser reports an opaque "Failed to fetch" instead of this status.
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{settings.next_public_supabase_url.rstrip('/')}/storage/v1/object/private-resumes/{object_path}",
                    headers={
                        "apikey": settings.supabase_service_role_key,
                        "Authorization": f"Bearer {settings.supabase_service_role_key}",
                        "Content-Type": detected_mime,
                        "x-upsert": "true",
                    },
                    content=content,
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "Private resume storage upload failed for session %s: %s",
                session_id,
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=503, detail="Resume storage isn't available right now. Please try again in a moment."
            ) from exc
        if response.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail="We couldn't save your resume just now. Please try again in a moment.")
    session = await repository.update(
        session_id, user_id, {"resume_url": f"private-resumes/{object_path}"}
    )
    if not session:
        raise HTTPException(status_code=404, detail="We couldn't find that session.")
    return session


@app.post("/api/v1/sessions/{session_id}/prepare", response_model=PrepareResponse)
@app.post("/api/sessions/{session_id}/prepare", response_model=PrepareResponse)
async def prepare_session(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
    planning: InterviewPlanningService = Depends(get_interview_planning_service),
) -> PrepareResponse:
    try:
        session = await engine.get_state(session_id, user_id)
        if session.status == SessionStatus.CREATED:
            session = await engine.begin_preparation(session_id, user_id)
        elif session.status == SessionStatus.READY:
            return PrepareResponse(
                session=session, claims_extracted=0, competencies_derived=0
            )
        elif session.status != SessionStatus.PREPARING:
            raise IllegalSessionTransition
        plan = await planning.plan(session_id, user_id)
        if plan.status != PlanningStatus.COMPLETED:
            raise HTTPException(status_code=502, detail="We couldn't prepare your conversation just now. Please try again in a moment.")
        session = await engine.mark_ready(session_id, user_id)
        return PrepareResponse(
            session=session, claims_extracted=0, competencies_derived=0
        )
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except IllegalSessionTransition as exc:
        raise HTTPException(
            status_code=409, detail="That can't be done at this point in the session."
        ) from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Your session changed while we were working. Please refresh and try again."
        ) from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Your session changed while we were working. Please refresh and try again."
        ) from exc
    except (ResumeAnalysisRequired, RoleAnalysisRequired) as exc:
        raise HTTPException(
            status_code=409,
            detail="Your resume and role need to be read before we can prepare your conversation.",
        ) from exc
    except InterviewPlanningUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Preparing your conversation isn't available right now. Please try again in a moment."
        ) from exc


@app.post("/api/v1/sessions/{session_id}/plan", response_model=PlanningResponse)
async def plan_interview(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
    planning: InterviewPlanningService = Depends(get_interview_planning_service),
) -> PlanningResponse:
    try:
        record = await planning.plan(session_id, user_id)
        session = await engine.get_state(session_id, user_id)
        if (
            record.status == PlanningStatus.COMPLETED
            and session.status == SessionStatus.PREPARING
        ):
            await engine.mark_ready(session_id, user_id)
        return planning.response(record)
    except PlanNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except SessionNotPlannable as exc:
        raise HTTPException(
            status_code=409, detail="This session can't be prepared right now."
        ) from exc
    except (ResumeAnalysisRequired, RoleAnalysisRequired) as exc:
        raise HTTPException(
            status_code=409,
            detail="Your resume and role need to be read before we can prepare your conversation.",
        ) from exc
    except InterviewPlanningUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Preparing your conversation isn't available right now. Please try again in a moment."
        ) from exc


@app.get("/api/v1/sessions/{session_id}/plan", response_model=InterviewPlanResponse)
async def read_interview_plan(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    planning: InterviewPlanningService = Depends(get_interview_planning_service),
) -> InterviewPlanResponse:
    try:
        return planning.detail(await planning.get(session_id, user_id))
    except PlanNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find your conversation plan.") from exc
    except InterviewPlanningUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Preparing your conversation isn't available right now. Please try again in a moment."
        ) from exc


@app.post("/api/sessions/{session_id}/start", response_model=SessionRead)
async def start_session(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
) -> SessionRead:
    try:
        return await engine.start(session_id, user_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except IllegalSessionTransition as exc:
        raise HTTPException(
            status_code=409, detail="That can't be done at this point in the session."
        ) from exc


@app.post(
    "/api/v1/sessions/{session_id}/start", response_model=InterviewStartResponse
)
async def start_text_interview(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    interview: TextInterviewService = Depends(get_text_interview_service),
) -> InterviewStartResponse:
    try:
        return await interview.start(session_id, user_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except InterviewPlanUnavailableForSession as exc:
        raise HTTPException(
            status_code=409, detail="Your conversation plan needs to be ready first."
        ) from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="We can't start this conversation yet."
        ) from exc
    except (ConcurrentSessionChange, InterviewTurnsUnavailable) as exc:
        logger.warning(
            "Text interview start failed for session %s: %s: %s",
            session_id,
            type(exc).__name__,
            exc.__cause__ or exc,
        )
        raise HTTPException(
            status_code=503, detail="The conversation isn't available right now. Please try again in a moment."
        ) from exc


@app.post(
    "/api/v1/sessions/{session_id}/turn-text", response_model=TextTurnResponse
)
async def create_text_turn(
    session_id: UUID,
    payload: TextTurnRequest,
    user_id: UUID = Depends(current_user_id),
    interview: TextInterviewService = Depends(get_text_interview_service),
) -> TextTurnResponse:
    try:
        return await interview.submit(session_id, user_id, payload)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except InterviewPlanUnavailableForSession as exc:
        raise HTTPException(
            status_code=409, detail="Your conversation plan needs to be ready first."
        ) from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="That can't be done at this point in the conversation."
        ) from exc
    except (ConcurrentSessionChange, InterviewTurnsUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="The conversation isn't available right now. Please try again in a moment."
        ) from exc


@app.post(
    "/api/v1/sessions/{session_id}/voice/start", response_model=VoiceTurnResponse
)
async def start_voice_interview(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    voice: VoiceInterviewService = Depends(get_voice_interview_service),
) -> VoiceTurnResponse:
    try:
        return await voice.start(session_id, user_id)
    except (SessionNotFound, VoiceTurnNotFound) as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except InterviewPlanUnavailableForSession as exc:
        raise HTTPException(
            status_code=409, detail="Your conversation plan needs to be ready first."
        ) from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="We can't start this conversation yet."
        ) from exc
    except (
        ConcurrentSessionChange,
        InterviewTurnsUnavailable,
        VoicePersistenceUnavailable,
    ) as exc:
        raise HTTPException(
            status_code=503, detail="The voice conversation isn't available right now. Please try again in a moment."
        ) from exc


@app.post("/api/v1/sessions/{session_id}/turn", response_model=VoiceTurnResponse)
async def create_voice_turn(
    session_id: UUID,
    audio: UploadFile = File(...),
    recorded_duration_ms: int | None = Form(default=None, ge=0),
    client_turn_id: UUID = Form(...),
    user_id: UUID = Depends(current_user_id),
    voice: VoiceInterviewService = Depends(get_voice_interview_service),
) -> VoiceTurnResponse:
    upload_started = perf_counter()
    content = await audio.read(settings.interview_audio_max_file_size_bytes + 1)
    upload_ms = max(0, round((perf_counter() - upload_started) * 1000))
    try:
        return await voice.submit(
            session_id,
            user_id,
            content=content,
            claimed_mime_type=audio.content_type,
            client_turn_id=client_turn_id,
            recorded_duration_ms=recorded_duration_ms,
            audio_upload_ms=upload_ms,
        )
    except AudioTooLarge as exc:
        raise HTTPException(
            status_code=413,
            detail={"code": exc.code, "message": "That recording is too large to send. Please try a shorter answer."},
        ) from exc
    except UnsupportedAudioType as exc:
        raise HTTPException(
            status_code=415,
            detail={"code": exc.code, "message": "We can't use that audio format. Please try again."},
        ) from exc
    except AudioTooShort as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": "That recording was very short. Whenever you're ready, please try again."},
        ) from exc
    except InvalidAudio as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": "We couldn't read that recording. Please try again."},
        ) from exc
    except TranscriptionFailed as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "message": "We couldn't hear that clearly. Whenever you're ready, please try that answer again.",
            },
        ) from exc
    except VoiceRequestInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": exc.code,
                "message": "That recording is still being processed. Please give it a moment.",
            },
        ) from exc
    except (SessionNotFound, VoiceTurnNotFound) as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="That can't be done at this point in the conversation."
        ) from exc
    except (
        ConcurrentSessionChange,
        InterviewTurnsUnavailable,
        VoicePersistenceUnavailable,
    ) as exc:
        raise HTTPException(
            status_code=503, detail="The voice conversation isn't available right now. Please try again in a moment."
        ) from exc


@app.post("/api/v1/turns/{turn_id}/audio/retry", response_model=VoiceTurnResponse)
async def retry_turn_audio(
    turn_id: UUID,
    user_id: UUID = Depends(current_user_id),
    voice: VoiceInterviewService = Depends(get_voice_interview_service),
) -> VoiceTurnResponse:
    try:
        return await voice.retry_audio(turn_id, user_id)
    except (VoiceTurnNotFound, SessionNotFound) as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that part of the conversation.") from exc
    except VoicePersistenceUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="The question audio isn't available right now. You can read the question instead."
        ) from exc


@app.get("/api/v1/sessions/{session_id}/turns", response_model=list[PublicTurn])
async def list_text_turns(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    interview: TextInterviewService = Depends(get_text_interview_service),
) -> list[PublicTurn]:
    try:
        return await interview.list_public_turns(session_id, user_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except InterviewTurnsUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="The conversation isn't available right now. Please try again in a moment."
        ) from exc


@app.post("/api/v1/sessions/{session_id}/pause")
async def pause_session(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
) -> dict:
    """Save the conversation and stop its clock ("continue later")."""
    await get_deferred_writes().flush(session_id)
    try:
        session = await engine.pause(session_id, user_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(status_code=409, detail="That can't be done at this point in the session.") from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Your session changed while we were working. Please refresh and try again."
        ) from exc
    from .session_liveness import get_liveness

    get_liveness().release(session_id)  # a reopened tab must not be told the room is elsewhere
    _, remaining = engine.remaining_times(session)
    return {"session_id": str(session_id), "paused": True, "remaining_time_seconds": remaining}


class HeartbeatBody(BaseModel):
    lease_id: str = Field(min_length=8, max_length=64)


@app.post("/api/v1/sessions/{session_id}/heartbeat")
async def session_heartbeat(
    session_id: UUID,
    body: HeartbeatBody,
    user_id: UUID = Depends(current_user_id),
) -> dict:
    """Keep this tab's lease fresh; a second live tab is refused."""
    from .session_liveness import OPEN_ELSEWHERE, get_liveness

    if not get_liveness().heartbeat(session_id, user_id, body.lease_id, settings.session_lease_seconds):
        raise HTTPException(status_code=409, detail=OPEN_ELSEWHERE)
    return {"ok": True}


@app.post("/api/v1/sessions/{session_id}/resume")
async def resume_session(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
) -> dict:
    try:
        session = await engine.resume(session_id, user_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(status_code=409, detail="That can't be done at this point in the session.") from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Your session changed while we were working. Please refresh and try again."
        ) from exc
    _, remaining = engine.remaining_times(session)
    return {"session_id": str(session_id), "paused": False, "remaining_time_seconds": remaining}


@app.post("/api/v1/sessions/{session_id}/end", response_model=SessionCompletionResponse)
@app.post("/api/sessions/{session_id}/end", response_model=SessionCompletionResponse)
async def end_session(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
    assessment: AssessmentPipelineRepository = Depends(get_assessment_pipeline_repository),
) -> SessionCompletionResponse:
    await get_deferred_writes().flush(session_id)  # pending turn writes land before the session closes
    try:
        current = None
        for attempt in range(3):
            current = await engine.get_state(session_id, user_id)
            try:
                if current.status == SessionStatus.ACTIVE:
                    current = await engine.request_close(session_id, user_id)
                if current.status == SessionStatus.ASSESSING:
                    current = await engine.complete(current.id, user_id)
                elif current.status != SessionStatus.COMPLETED:
                    raise IllegalSessionTransition
                break
            except ConcurrentSessionChange:
                if attempt == 2:
                    raise
        if current is None or current.status != SessionStatus.COMPLETED:
            raise IllegalSessionTransition
        assessment_state = await assessment.enqueue(current.id, user_id)
        logger.info(
            "interview completion persisted",
            extra={
                "session_id": str(current.id),
                "user_id": str(user_id),
                "assessment_status": assessment_state.status.value,
            },
        )
        return SessionCompletionResponse(
            **current.model_dump(), assessment=assessment_state
        )
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="That can't be done at this point in the session."
        ) from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Your session changed while we were working. Please refresh and try again."
        ) from exc
    except AssessmentPipelineUnavailable as exc:
        raise HTTPException(status_code=503, detail="Your reflection can't be prepared right now. Please try again in a moment.") from exc
