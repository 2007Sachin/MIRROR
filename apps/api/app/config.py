from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    app_url: str = "http://localhost:3000"
    next_public_supabase_url: str = ""
    next_public_supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    resume_max_file_size_bytes: int = 8 * 1024 * 1024
    groq_api_key: str = ""
    deepgram_api_key: str = ""
    deepgram_stt_model: str = "nova-3"
    sarvam_api_key: str = ""
    sarvam_tts_model: str = "bulbul:v2"
    sarvam_tts_voice: str = "anushka"
    interview_tts_language: str = "en-IN"
    interview_audio_max_file_size_bytes: int = 10 * 1024 * 1024
    interview_audio_min_duration_ms: int = 300
    interview_audio_signed_url_seconds: int = 300
    interview_min_transcript_confidence: float = 0.2
    interviewer_model: str = "llama-3.1-8b-instant"
    skeptic_model: str = "llama-3.3-70b-versatile"
    skeptic_shadow_mode: bool = True
    live_skeptic_probes: bool = False
    skeptic_live_probe_min_confidence: float = Field(default=0.8, ge=0, le=1)
    skeptic_job_max_attempts: int = 3
    skeptic_job_retry_base_seconds: int = 15
    assessment_job_max_attempts: int = 3
    assessment_job_retry_base_seconds: int = 30
    assessor_model: str = "llama-3.3-70b-versatile"
    batch_model: str = "llama-3.3-70b-versatile"
    skeptic_mode: str = "shadow"
    interview_default_duration_seconds: int = 20 * 60
    interview_phase_time_budget_seconds: int = 3 * 60
    planner_intro_reserve_seconds: int = 60
    planner_transition_reserve_seconds: int = 60
    planner_closing_reserve_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), extra="ignore", case_sensitive=False
    )

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.next_public_supabase_url and self.supabase_service_role_key)

    @property
    def supabase_auth_enabled(self) -> bool:
        return bool(
            self.next_public_supabase_url and self.next_public_supabase_anon_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

