from __future__ import annotations

from functools import lru_cache
from fastapi import HTTPException, status

from .config import get_settings
from .claims_repository import (
    ClaimsGraphRepository,
    ClaimsGraphUnavailable,
    SupabaseClaimsGraphRepository,
)
from .claims_service import ClaimsGraphService
from .auth import current_user_id as current_user_id
from .agents import AgentRegistry, AgentRunner, PromptLoader
from .agents.providers import GroqProvider
from .agents.resume import create_resume_agent
from .agents.role import create_role_agent
from .agents.planner import create_planner_agent
from .agents.interviewer import create_interviewer_agent
from .agents.skeptic import create_skeptic_agent
from .document_parsing import ResumeDocumentParser
from .document_repository import (
    DocumentRepository,
    DocumentStorage,
    DocumentUnavailable,
    SupabaseDocumentRepository,
    SupabaseResumeStorage,
)
from .onboarding_repository import (
    OnboardingRepository,
    OnboardingUnavailable,
    SupabaseOnboardingRepository,
)
from .profile_repository import (
    ProfileRepository,
    ProfileUnavailable,
    SupabaseProfileRepository,
)
from .repository import (
    MemorySessionRepository,
    SessionRepository,
    SupabaseSessionRepository,
)
from .resume_repository import (
    ResumeAnalysisRepository,
    ResumeAnalysisUnavailable,
    SupabaseResumeAnalysisRepository,
)
from .resume_service import ResumeAnalysisService
from .role_repository import (
    RoleAnalysisRepository,
    RoleAnalysisUnavailable,
    SupabaseRoleAnalysisRepository,
)
from .role_service import RoleAnalysisService
from .interview_engine import InterviewStateMachine
from .planner_repository import (
    InterviewPlanRepository,
    InterviewPlanningUnavailable,
    SupabaseInterviewPlanRepository,
)
from .planner_service import InterviewPlanningService
from .interviewer_context import InterviewerContextBuilder
from .interviewer_repository import (
    InterviewTurnRepository,
    InterviewTurnsUnavailable,
    SupabaseInterviewTurnRepository,
)
from .interviewer_service import TextInterviewService
from .flag_activation import FlagActivationRepository, FlagEligibilityService
from .flag_repository import SupabaseFlagActivationRepository
from .audio_validation import AudioValidator
from .speech_providers import (
    DeepgramSpeechToTextProvider,
    SarvamTextToSpeechProvider,
    SpeechProviderUnavailable,
    SpeechToTextProvider,
    TextToSpeechProvider,
)
from .voice_repository import (
    InterviewAudioStorage,
    SupabaseInterviewAudioStorage,
    SupabaseVoiceRepository,
    VoicePersistenceUnavailable,
    VoiceRepository,
)
from .voice_service import VoiceInterviewService
from .skeptic_admin import SkepticAdminService
from .skeptic_context import SkepticContextBuilder
from .skeptic_processor import SkepticResultProcessor
from .skeptic_repository import (
    SkepticPersistenceUnavailable,
    SkepticRepository,
    SupabaseSkepticRepository,
)
from .skeptic_worker import SkepticWorker
from .agents.evidence import create_evidence_agent
from .evidence_repository import (
    EvidencePersistenceUnavailable,
    EvidenceRepository,
    SupabaseEvidenceRepository,
)
from .evidence_service import EvidenceResolutionService
from .claim_resolution_repository import (
    ClaimResolutionRepository,
    SupabaseClaimResolutionRepository,
)
from .claim_resolution_service import ClaimResolutionService, ClaimsAuditService
from .agents.specialist_assessors import create_specialist_assessor
from .assessment_orchestrator import AssessmentOrchestrator
from .specialist_assessment_repository import (
    SpecialistAssessmentRepository,
    SpecialistAssessmentUnavailable,
    SupabaseSpecialistAssessmentRepository,
)
from .specialist_assessor_models import AssessorType
from .evidence_service import EvidenceQuoteValidator
from .report_service import ReportService, SupabaseReportRepository
from .assessment_pipeline_repository import AssessmentPipelineRepository, AssessmentPipelineUnavailable, MemoryAssessmentPipelineRepository, SupabaseAssessmentPipelineRepository
from .assessment_worker import AssessmentWorker
from .assessment_adjudication_repository import SupabaseAssessmentAdjudicationRepository
from .assessment_adjudication_service import AssessmentAdjudicator
from .assessment_disagreement import AssessmentDisagreementDetector
from .agents.adjudicator import create_adjudicator_agent
from .agents.verdict import create_verdict_agent
from .verdict_service import VerdictLanguageService
from .final_assessment_aggregator import FinalAssessmentAggregator


@lru_cache
def get_repository() -> SessionRepository:
    settings = get_settings()
    return (
        SupabaseSessionRepository(settings)
        if settings.supabase_enabled
        else MemorySessionRepository()
    )


@lru_cache
def get_interview_state_machine() -> InterviewStateMachine:
    settings = get_settings()
    return InterviewStateMachine(
        get_repository(),
        total_time_budget_seconds=settings.interview_default_duration_seconds,
        phase_time_budget_seconds=settings.interview_phase_time_budget_seconds,
    )


@lru_cache
def get_interview_plan_repository() -> InterviewPlanRepository:
    try:
        return SupabaseInterviewPlanRepository(get_settings())
    except InterviewPlanningUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Interview planning is not configured",
        ) from exc


@lru_cache
def get_planner_agent_runner() -> AgentRunner:
    settings = get_settings()
    registry = AgentRegistry()
    registry.register(create_planner_agent(settings.batch_model))
    return AgentRunner(registry, GroqProvider(settings.groq_api_key), PromptLoader())


@lru_cache
def get_interview_planning_service() -> InterviewPlanningService:
    settings = get_settings()
    return InterviewPlanningService(
        get_repository(),
        get_interview_plan_repository(),
        get_planner_agent_runner(),
        model=settings.batch_model,
        intro_reserve_seconds=settings.planner_intro_reserve_seconds,
        transition_reserve_seconds=settings.planner_transition_reserve_seconds,
        closing_reserve_seconds=settings.planner_closing_reserve_seconds,
    )


@lru_cache
def get_interview_turn_repository() -> InterviewTurnRepository:
    try:
        return SupabaseInterviewTurnRepository(get_settings())
    except InterviewTurnsUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Text interview storage is not configured",
        ) from exc


@lru_cache
def get_interviewer_agent_runner() -> AgentRunner:
    settings = get_settings()
    registry = AgentRegistry()
    registry.register(create_interviewer_agent(settings.interviewer_model))
    return AgentRunner(registry, GroqProvider(settings.groq_api_key), PromptLoader())


@lru_cache
def get_interviewer_context_builder() -> InterviewerContextBuilder:
    return InterviewerContextBuilder(
        get_interview_state_machine(),
        get_interview_plan_repository(),
        get_interview_turn_repository(),
        get_flag_eligibility_service(),
    )


@lru_cache
def get_text_interview_service() -> TextInterviewService:
    return TextInterviewService(
        get_interview_state_machine(),
        get_interviewer_context_builder(),
        get_interview_turn_repository(),
        get_interviewer_agent_runner(),
        flag_eligibility=get_flag_eligibility_service(),
    )


@lru_cache
def get_flag_activation_repository() -> FlagActivationRepository:
    try:
        return SupabaseFlagActivationRepository(get_settings())
    except SkepticPersistenceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skeptic flag activation is not configured",
        ) from exc


@lru_cache
def get_flag_eligibility_service() -> FlagEligibilityService:
    settings = get_settings()
    return FlagEligibilityService(
        get_flag_activation_repository(),
        live_probes=settings.live_skeptic_probes,
        shadow_mode=settings.skeptic_shadow_mode,
        min_confidence=settings.skeptic_live_probe_min_confidence,
    )


@lru_cache
def get_voice_repository() -> VoiceRepository:
    try:
        return SupabaseVoiceRepository(get_settings())
    except VoicePersistenceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice persistence is not configured",
        ) from exc


@lru_cache
def get_interview_audio_storage() -> InterviewAudioStorage:
    try:
        return SupabaseInterviewAudioStorage(get_settings())
    except VoicePersistenceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Interview audio storage is not configured",
        ) from exc


@lru_cache
def get_speech_to_text_provider() -> SpeechToTextProvider:
    settings = get_settings()
    try:
        return DeepgramSpeechToTextProvider(
            settings.deepgram_api_key, model=settings.deepgram_stt_model
        )
    except SpeechProviderUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech transcription is not configured",
        ) from exc


@lru_cache
def get_text_to_speech_provider() -> TextToSpeechProvider:
    settings = get_settings()
    try:
        return SarvamTextToSpeechProvider(
            settings.sarvam_api_key,
            model=settings.sarvam_tts_model,
            voice=settings.sarvam_tts_voice,
        )
    except SpeechProviderUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech synthesis is not configured",
        ) from exc


@lru_cache
def get_audio_validator() -> AudioValidator:
    settings = get_settings()
    return AudioValidator(
        max_bytes=settings.interview_audio_max_file_size_bytes,
        minimum_duration_ms=settings.interview_audio_min_duration_ms,
    )


@lru_cache
def get_voice_interview_service() -> VoiceInterviewService:
    settings = get_settings()
    return VoiceInterviewService(
        get_interview_state_machine(),
        get_text_interview_service(),
        get_interview_turn_repository(),
        get_voice_repository(),
        get_interview_audio_storage(),
        get_speech_to_text_provider(),
        get_text_to_speech_provider(),
        get_audio_validator(),
        tts_language=settings.interview_tts_language,
        tts_model=settings.sarvam_tts_model,
        tts_voice=settings.sarvam_tts_voice,
        signed_url_seconds=settings.interview_audio_signed_url_seconds,
        minimum_transcript_confidence=settings.interview_min_transcript_confidence,
    )


@lru_cache
def get_profile_repository() -> ProfileRepository:
    try:
        return SupabaseProfileRepository(get_settings())
    except ProfileUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile service is not configured",
        ) from exc


@lru_cache
def get_onboarding_repository() -> OnboardingRepository:
    try:
        return SupabaseOnboardingRepository(get_settings())
    except OnboardingUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding service is not configured",
        ) from exc


@lru_cache
def get_document_repository() -> DocumentRepository:
    try:
        return SupabaseDocumentRepository(get_settings())
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is not configured",
        ) from exc


@lru_cache
def get_document_storage() -> DocumentStorage:
    try:
        return SupabaseResumeStorage(get_settings())
    except DocumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume storage is not configured",
        ) from exc


@lru_cache
def get_resume_analysis_repository() -> ResumeAnalysisRepository:
    try:
        return SupabaseResumeAnalysisRepository(get_settings())
    except ResumeAnalysisUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume analysis service is not configured",
        ) from exc


@lru_cache
def get_resume_document_parser() -> ResumeDocumentParser:
    return ResumeDocumentParser()


@lru_cache
def get_resume_agent_runner() -> AgentRunner:
    settings = get_settings()
    registry = AgentRegistry()
    registry.register(create_resume_agent(settings.batch_model))
    return AgentRunner(registry, GroqProvider(settings.groq_api_key), PromptLoader())


@lru_cache
def get_resume_analysis_service() -> ResumeAnalysisService:
    return ResumeAnalysisService(
        get_document_repository(),
        get_document_storage(),
        get_resume_document_parser(),
        get_resume_analysis_repository(),
        get_resume_agent_runner(),
        model=get_settings().batch_model,
    )


@lru_cache
def get_role_analysis_repository() -> RoleAnalysisRepository:
    try:
        return SupabaseRoleAnalysisRepository(get_settings())
    except RoleAnalysisUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Role analysis service is not configured",
        ) from exc


@lru_cache
def get_role_agent_runner() -> AgentRunner:
    settings = get_settings()
    registry = AgentRegistry()
    registry.register(create_role_agent(settings.batch_model))
    return AgentRunner(registry, GroqProvider(settings.groq_api_key), PromptLoader())


@lru_cache
def get_role_analysis_service() -> RoleAnalysisService:
    return RoleAnalysisService(
        get_document_repository(),
        get_role_analysis_repository(),
        get_role_agent_runner(),
        model=get_settings().batch_model,
    )


@lru_cache
def get_claims_graph_repository() -> ClaimsGraphRepository:
    try:
        return SupabaseClaimsGraphRepository(get_settings())
    except ClaimsGraphUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims service is not configured",
        ) from exc


@lru_cache
def get_claims_graph_service() -> ClaimsGraphService:
    return ClaimsGraphService(get_claims_graph_repository())


@lru_cache
def get_skeptic_repository() -> SkepticRepository:
    try:
        return SupabaseSkepticRepository(get_settings())
    except SkepticPersistenceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skeptic persistence is not configured",
        ) from exc


@lru_cache
def get_skeptic_agent_runner() -> AgentRunner:
    settings = get_settings()
    registry = AgentRegistry()
    registry.register(create_skeptic_agent(settings.skeptic_model))
    return AgentRunner(registry, GroqProvider(settings.groq_api_key), PromptLoader())


@lru_cache
def get_skeptic_context_builder() -> SkepticContextBuilder:
    return SkepticContextBuilder(get_skeptic_repository())


@lru_cache
def get_skeptic_result_processor() -> SkepticResultProcessor:
    return SkepticResultProcessor(
        get_skeptic_repository(), get_claims_graph_service()
    )


@lru_cache
def get_skeptic_worker() -> SkepticWorker:
    settings = get_settings()
    return SkepticWorker(
        get_skeptic_repository(),
        get_skeptic_context_builder(),
        get_skeptic_agent_runner(),
        get_skeptic_result_processor(),
        model=settings.skeptic_model,
        shadow_mode=settings.skeptic_shadow_mode,
        max_attempts=settings.skeptic_job_max_attempts,
        retry_base_seconds=settings.skeptic_job_retry_base_seconds,
    )


@lru_cache
def get_skeptic_admin_service() -> SkepticAdminService:
    return SkepticAdminService(get_skeptic_repository())


@lru_cache
def get_evidence_repository() -> EvidenceRepository:
    try:
        return SupabaseEvidenceRepository(get_settings())
    except EvidencePersistenceUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evidence persistence is not configured",
        ) from exc


@lru_cache
def get_evidence_agent_runner() -> AgentRunner:
    settings = get_settings()
    registry = AgentRegistry()
    registry.register(create_evidence_agent(settings.batch_model))
    return AgentRunner(registry, GroqProvider(settings.groq_api_key), PromptLoader())


@lru_cache
def get_evidence_resolution_service() -> EvidenceResolutionService:
    return EvidenceResolutionService(
        get_evidence_repository(), get_claim_resolution_service(), get_evidence_agent_runner()
    )


@lru_cache
def get_claim_resolution_repository() -> ClaimResolutionRepository:
    return SupabaseClaimResolutionRepository(get_settings())


@lru_cache
def get_claim_resolution_service() -> ClaimResolutionService:
    return ClaimResolutionService(get_claim_resolution_repository())


@lru_cache
def get_claims_audit_service() -> ClaimsAuditService:
    return ClaimsAuditService(get_claim_resolution_repository())


@lru_cache
def get_specialist_assessment_repository() -> SpecialistAssessmentRepository:
    try:
        return SupabaseSpecialistAssessmentRepository(get_settings())
    except SpecialistAssessmentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Specialist assessment persistence is not configured",
        ) from exc


@lru_cache
def get_specialist_assessment_orchestrator() -> AssessmentOrchestrator:
    settings = get_settings()
    runners: dict[AssessorType, AgentRunner] = {}
    for assessor_type in AssessorType:
        registry = AgentRegistry()
        registry.register(create_specialist_assessor(assessor_type, settings.assessor_model))
        runners[assessor_type] = AgentRunner(
            registry, GroqProvider(settings.groq_api_key), PromptLoader()
        )
    return AssessmentOrchestrator(
        get_specialist_assessment_repository(), runners,
        EvidenceQuoteValidator(get_evidence_repository()),
    )


@lru_cache
def get_report_service() -> ReportService:
    return ReportService(SupabaseReportRepository(get_settings()))


@lru_cache
def get_assessment_pipeline_repository() -> AssessmentPipelineRepository:
    if not get_settings().supabase_enabled:
        return MemoryAssessmentPipelineRepository()
    try:
        return SupabaseAssessmentPipelineRepository(get_settings())
    except AssessmentPipelineUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Assessment processing is not configured") from exc


@lru_cache
def get_adjudicator_runner() -> AgentRunner:
    settings = get_settings(); registry = AgentRegistry()
    registry.register(create_adjudicator_agent(settings.assessor_model))
    return AgentRunner(registry, GroqProvider(settings.groq_api_key), PromptLoader())


@lru_cache
def get_assessment_adjudicator() -> AssessmentAdjudicator:
    return AssessmentAdjudicator(AssessmentDisagreementDetector(), SupabaseAssessmentAdjudicationRepository(get_settings()), get_adjudicator_runner())


@lru_cache
def get_verdict_language_service() -> VerdictLanguageService:
    settings = get_settings(); registry = AgentRegistry()
    registry.register(create_verdict_agent(settings.assessor_model))
    return VerdictLanguageService(AgentRunner(registry, GroqProvider(settings.groq_api_key), PromptLoader()))


@lru_cache
def get_assessment_worker() -> AssessmentWorker:
    settings = get_settings()
    return AssessmentWorker(get_assessment_pipeline_repository(), get_specialist_assessment_orchestrator(), get_assessment_adjudicator(), FinalAssessmentAggregator(), get_verdict_language_service(), get_claims_audit_service(), max_attempts=settings.assessment_job_max_attempts, retry_base_seconds=settings.assessment_job_retry_base_seconds)
