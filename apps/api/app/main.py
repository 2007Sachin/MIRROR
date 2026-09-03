from __future__ import annotations

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

from .config import get_settings
from .auth import AuthenticatedUser, get_current_user
from .dependencies import (
    current_user_id,
    get_document_repository,
    get_document_storage,
    get_onboarding_repository,
    get_profile_repository,
    get_repository,
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
from .document_repository import (
    DocumentRepository,
    DocumentStorage,
    DocumentUnavailable,
    job_description_values,
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
    JobDescriptionCreate,
    OnboardingRead,
    OnboardingUpdate,
    PrepareResponse,
    ProfileRead,
    ProfileUpdate,
    SessionCreate,
    SessionPatch,
    SessionRead,
    SessionStatus,
    onboarding_is_complete,
)
from .report_models import ReportResponse
from .assessment_pipeline_models import AssessmentPipelineState
from .assessment_pipeline_repository import AssessmentPipelineRepository, AssessmentPipelineUnavailable
from .report_service import ReportAssessmentIncomplete, ReportNotFound, ReportService, ReportUnavailable

settings = get_settings()
app = FastAPI(title="Mirror API", version="0.1.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
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
        raise HTTPException(status_code=404, detail="Session report not found") from exc
    except ReportAssessmentIncomplete as exc:
        raise HTTPException(status_code=409, detail="Session assessment is not complete") from exc
    except ReportUnavailable as exc:
        raise HTTPException(status_code=503, detail="Session report is temporarily unavailable") from exc


@app.get("/api/v1/sessions/{session_id}/assessment", response_model=AssessmentPipelineState)
async def read_assessment_status(
    session_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: AssessmentPipelineRepository = Depends(get_assessment_pipeline_repository),
) -> AssessmentPipelineState:
    try:
        state = await repository.status(session_id, user.id)
    except AssessmentPipelineUnavailable as exc:
        raise HTTPException(status_code=503, detail="Assessment processing is temporarily unavailable") from exc
    if state is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return state


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
        raise HTTPException(status_code=404, detail="Session not found") from exc
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
            status_code=503, detail="Claims service is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Claim not found") from exc
    except ClaimsGraphUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Claims service is temporarily unavailable"
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
            detail="Profile service is temporarily unavailable",
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
            detail="Profile service is temporarily unavailable",
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
            detail="Onboarding service is temporarily unavailable",
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
                detail="Complete all required onboarding fields before continuing",
            )
        return await onboarding.update(user.id, values)
    except HTTPException:
        raise
    except (ProfileUnavailable, OnboardingUnavailable) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding service is temporarily unavailable",
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
        raise HTTPException(status_code=415, detail="Resume must be a PDF or DOCX file")

    maximum_size = settings.resume_max_file_size_bytes
    if maximum_size <= 0:
        raise HTTPException(
            status_code=503, detail="Resume upload is temporarily unavailable"
        )
    content = await resume.read(maximum_size + 1)
    if len(content) > maximum_size:
        raise HTTPException(
            status_code=413, detail="Resume exceeds the configured file-size limit"
        )

    detected_mime = detect_resume_mime_type(content)
    if detected_mime is None or detected_mime != declared_mime:
        raise HTTPException(
            status_code=415,
            detail="Resume content does not match an allowed PDF or DOCX file",
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
            detail="Resume upload is temporarily unavailable",
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
            detail="Document service is temporarily unavailable",
        ) from exc


@app.get("/api/v1/documents", response_model=list[DocumentRead])
async def list_documents(
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
) -> list[DocumentRead]:
    try:
        return await repository.list_for_user(user.id)
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is temporarily unavailable",
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
            detail="Document service is temporarily unavailable",
        ) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.delete("/api/v1/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
) -> Response:
    try:
        document = await repository.get_for_user(document_id, user.id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        if await repository.linked_to_protected_session(document.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Documents linked to an active or completed session cannot be deleted",
            )
        if document.storage_path:
            await storage.delete(document.storage_path)
        if not await repository.delete(document.id, user.id):
            raise HTTPException(status_code=404, detail="Document not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is temporarily unavailable",
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
        raise HTTPException(status_code=404, detail="Resume not found") from exc
    except UnsupportedResumeDocument as exc:
        raise HTTPException(status_code=422, detail="Document is not a resume") from exc
    except (
        DocumentUnavailable,
        OnboardingUnavailable,
        ResumeAnalysisUnavailable,
    ) as exc:
        raise HTTPException(
            status_code=503, detail="Resume analysis is temporarily unavailable"
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
            status_code=404, detail="Resume analysis not found"
        ) from exc
    except UnsupportedResumeDocument as exc:
        raise HTTPException(status_code=422, detail="Document is not a resume") from exc
    except (DocumentUnavailable, ResumeAnalysisUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Resume analysis is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Resume claim not found") from exc
    except UnsupportedResumeDocument as exc:
        raise HTTPException(status_code=422, detail="Document is not a resume") from exc
    except (DocumentUnavailable, ResumeAnalysisUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Resume analysis is temporarily unavailable"
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
            status_code=422, detail="Job description document is not available"
        ) from exc
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="Role profile not found") from exc
    except RoleProfileTargetMismatch as exc:
        raise HTTPException(
            status_code=409, detail="Role profile belongs to a different target role"
        ) from exc
    except (DocumentUnavailable, OnboardingUnavailable, RoleAnalysisUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Role analysis is temporarily unavailable"
        ) from exc


@app.get("/api/v1/roles/{role_profile_id}", response_model=RoleAnalysisResponse)
async def read_role_profile(
    role_profile_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    service: RoleAnalysisService = Depends(get_role_analysis_service),
) -> RoleAnalysisResponse:
    try:
        return await service.get(role_profile_id, user.id)
    except RoleProfileNotFoundForUser as exc:
        raise HTTPException(status_code=404, detail="Role profile not found") from exc
    except RoleAnalysisUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Role analysis is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Role profile not found") from exc
    except RoleAnalysisUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Role analysis is temporarily unavailable"
        ) from exc


@app.post("/api/v1/sessions", response_model=SessionRead, status_code=201)
@app.post("/api/sessions", response_model=SessionRead, status_code=201)
async def create_session(
    payload: SessionCreate,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
) -> SessionRead:
    return await engine.create_session_state(user_id, payload)


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
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.post("/api/sessions/{session_id}/jd", response_model=SessionRead)
async def save_job_description(
    session_id: UUID,
    payload: SessionPatch,
    user_id: UUID = Depends(current_user_id),
    repository: SessionRepository = Depends(get_repository),
) -> SessionRead:
    session = await repository.update(session_id, user_id, {"jd_text": payload.jd_text})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
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
        raise HTTPException(status_code=415, detail="Resume must be a PDF or DOCX file")
    if settings.resume_max_file_size_bytes <= 0:
        raise HTTPException(
            status_code=503, detail="Resume upload is temporarily unavailable"
        )
    content = await resume.read(settings.resume_max_file_size_bytes + 1)
    if len(content) > settings.resume_max_file_size_bytes:
        raise HTTPException(
            status_code=413, detail="Resume exceeds the configured file-size limit"
        )
    detected_mime = detect_resume_mime_type(content)
    if detected_mime is None or detected_mime != declared_mime:
        raise HTTPException(
            status_code=415,
            detail="Resume content does not match an allowed PDF or DOCX file",
        )
    safe_name = "resume.pdf" if detected_mime == "application/pdf" else "resume.docx"
    object_path = f"{user_id}/{session_id}/{safe_name}"
    if settings.supabase_enabled:
        async with httpx.AsyncClient(timeout=20) as client:
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
        if response.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail="Private resume storage failed")
    session = await repository.update(
        session_id, user_id, {"resume_url": f"private-resumes/{object_path}"}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
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
        elif session.status != SessionStatus.PREPARING:
            raise IllegalSessionTransition
        plan = await planning.plan(session_id, user_id)
        if plan.status != PlanningStatus.COMPLETED:
            raise HTTPException(status_code=502, detail="Interview planning failed")
        session = await engine.mark_ready(session_id, user_id)
        return PrepareResponse(
            session=session, claims_extracted=0, competencies_derived=0
        )
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except IllegalSessionTransition as exc:
        raise HTTPException(
            status_code=409, detail="Illegal session transition"
        ) from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Session changed concurrently"
        ) from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Session changed concurrently"
        ) from exc
    except (ResumeAnalysisRequired, RoleAnalysisRequired) as exc:
        raise HTTPException(
            status_code=409,
            detail="Resume and role intelligence are required before planning",
        ) from exc
    except InterviewPlanningUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Interview planning is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except SessionNotPlannable as exc:
        raise HTTPException(
            status_code=409, detail="Session is not available for planning"
        ) from exc
    except (ResumeAnalysisRequired, RoleAnalysisRequired) as exc:
        raise HTTPException(
            status_code=409,
            detail="Resume and role intelligence are required before planning",
        ) from exc
    except InterviewPlanningUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Interview planning is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Interview plan not found") from exc
    except InterviewPlanningUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Interview planning is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except IllegalSessionTransition as exc:
        raise HTTPException(
            status_code=409, detail="Illegal session transition"
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
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except InterviewPlanUnavailableForSession as exc:
        raise HTTPException(
            status_code=409, detail="An active interview plan is required"
        ) from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="Interview cannot be started"
        ) from exc
    except (ConcurrentSessionChange, InterviewTurnsUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Text interview is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except InterviewPlanUnavailableForSession as exc:
        raise HTTPException(
            status_code=409, detail="An active interview plan is required"
        ) from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="This interview turn is not allowed"
        ) from exc
    except (ConcurrentSessionChange, InterviewTurnsUnavailable) as exc:
        raise HTTPException(
            status_code=503, detail="Text interview is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except InterviewPlanUnavailableForSession as exc:
        raise HTTPException(
            status_code=409, detail="An active interview plan is required"
        ) from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="Interview cannot be started"
        ) from exc
    except (
        ConcurrentSessionChange,
        InterviewTurnsUnavailable,
        VoicePersistenceUnavailable,
    ) as exc:
        raise HTTPException(
            status_code=503, detail="Voice interview is temporarily unavailable"
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
            detail={"code": exc.code, "message": "That recording is too large."},
        ) from exc
    except UnsupportedAudioType as exc:
        raise HTTPException(
            status_code=415,
            detail={"code": exc.code, "message": "That audio format is not supported."},
        ) from exc
    except AudioTooShort as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": "That recording is too short."},
        ) from exc
    except InvalidAudio as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": "That recording could not be read."},
        ) from exc
    except TranscriptionFailed as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "message": "We couldn't hear that clearly. Try that answer again.",
            },
        ) from exc
    except VoiceRequestInProgress as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": exc.code,
                "message": "That recording is still being processed.",
            },
        ) from exc
    except (SessionNotFound, VoiceTurnNotFound) as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="This interview turn is not allowed"
        ) from exc
    except (
        ConcurrentSessionChange,
        InterviewTurnsUnavailable,
        VoicePersistenceUnavailable,
    ) as exc:
        raise HTTPException(
            status_code=503, detail="Voice interview is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Turn not found") from exc
    except VoicePersistenceUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Question audio is temporarily unavailable"
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
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except InterviewTurnsUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="Text interview is temporarily unavailable"
        ) from exc


@app.post("/api/v1/sessions/{session_id}/end", response_model=SessionRead)
@app.post("/api/sessions/{session_id}/end", response_model=SessionRead)
async def end_session(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
    assessment: AssessmentPipelineRepository = Depends(get_assessment_pipeline_repository),
) -> SessionRead:
    try:
        current = await engine.get_state(session_id, user_id)
        if current.status == SessionStatus.ACTIVE:
            assessing = await engine.request_close(session_id, user_id)
            current = await engine.complete(assessing.id, user_id)
        elif current.status != SessionStatus.COMPLETED:
            raise IllegalSessionTransition
        await assessment.enqueue(current.id, user_id)
        return current
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except (IllegalSessionTransition, InterviewFlowRejected) as exc:
        raise HTTPException(
            status_code=409, detail="Illegal session transition"
        ) from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Session changed concurrently"
        ) from exc
    except AssessmentPipelineUnavailable as exc:
        raise HTTPException(status_code=503, detail="Assessment processing is temporarily unavailable") from exc
