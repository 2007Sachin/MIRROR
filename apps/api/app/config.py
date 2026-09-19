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
    # Groq bills a tokens-per-minute budget, and a full diagnostic runs several
    # large agents in close succession, so a rate-limited call is worth waiting out.
    # The provider returns short Retry-After hints while a minute-long bucket
    # refills, so the attempt count has to be generous; the wait budget is the
    # real bound on how long a request may block.
    groq_rate_limit_max_retries: int = 10
    groq_rate_limit_max_wait_seconds: float = 75.0
    deepgram_api_key: str = ""
    deepgram_stt_model: str = "nova-3"
    # "sarvam" runs transcription and synthesis on one vendor; "deepgram" keeps the
    # original split. Defaults to deepgram so existing deployments are unaffected.
    speech_to_text_provider: str = "deepgram"
    sarvam_api_key: str = ""
    sarvam_stt_model: str = "saaras:v3"
    # Blank asks Sarvam to auto-detect the spoken language.
    sarvam_stt_language: str = "en-IN"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_voice: str = "priya"
    # Compressed audio keeps question playback fast on slow uplinks.
    sarvam_tts_output_codec: str = "mp3"
    interview_tts_language: str = "en-IN"
    interview_audio_max_file_size_bytes: int = 10 * 1024 * 1024
    interview_audio_min_duration_ms: int = 300
    interview_audio_signed_url_seconds: int = 300
    interview_min_transcript_confidence: float = 0.2
    interviewer_model: str = "openai/gpt-oss-20b"
    skeptic_model: str = "openai/gpt-oss-120b"
    skeptic_shadow_mode: bool = True
    live_skeptic_probes: bool = False
    skeptic_live_probe_min_confidence: float = Field(default=0.8, ge=0, le=1)
    skeptic_job_max_attempts: int = 3
    skeptic_job_retry_base_seconds: int = 15
    assessment_job_max_attempts: int = 3
    assessment_job_retry_base_seconds: int = 30
    assessor_model: str = "openai/gpt-oss-120b"
    batch_model: str = "openai/gpt-oss-120b"
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

