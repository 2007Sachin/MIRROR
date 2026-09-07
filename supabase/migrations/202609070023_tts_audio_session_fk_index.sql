begin;

-- The existing tts_audio_cache_session_idx is led by user_id and therefore
-- cannot support session FK checks or session-first cleanup on its own.
create index if not exists tts_audio_cache_session_fk_idx
  on public.tts_audio_cache(session_id);

commit;
