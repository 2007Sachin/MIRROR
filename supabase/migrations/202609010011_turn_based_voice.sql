begin;

alter table public.turns
  add column if not exists audio_storage_path text,
  add column if not exists audio_mime_type text,
  add column if not exists audio_status text
    check (audio_status is null or audio_status in ('READY', 'FAILED')),
  add column if not exists stt_provider text,
  add column if not exists stt_model text,
  add column if not exists stt_confidence numeric(5,4)
    check (stt_confidence is null or stt_confidence between 0 and 1),
  add column if not exists stt_detected_language text,
  add column if not exists stt_metadata jsonb not null default '{}'::jsonb,
  add column if not exists stt_latency_ms integer
    check (stt_latency_ms is null or stt_latency_ms >= 0),
  add column if not exists tts_provider text,
  add column if not exists tts_model text,
  add column if not exists tts_voice text,
  add column if not exists tts_language text,
  add column if not exists tts_metadata jsonb not null default '{}'::jsonb,
  add column if not exists tts_latency_ms integer
    check (tts_latency_ms is null or tts_latency_ms >= 0);

create table public.voice_turn_requests (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  client_turn_id uuid not null,
  status text not null check (status in ('PROCESSING', 'COMPLETED', 'FAILED')),
  candidate_audio_path text,
  candidate_audio_mime_type text,
  recorded_duration_ms integer
    check (recorded_duration_ms is null or recorded_duration_ms >= 0),
  candidate_turn_id uuid references public.turns(id) on delete set null,
  interviewer_turn_id uuid references public.turns(id) on delete set null,
  response_json jsonb,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(session_id, client_turn_id)
);

create index voice_turn_requests_user_session_idx
  on public.voice_turn_requests(user_id, session_id, created_at desc);

create table public.tts_audio_cache (
  cache_key text primary key,
  user_id uuid not null references public.users(id) on delete cascade,
  session_id uuid not null references public.sessions(id) on delete cascade,
  normalized_text_hash text not null,
  provider text not null,
  model text not null,
  voice text not null,
  language text not null,
  storage_path text not null,
  mime_type text not null,
  created_at timestamptz not null default now(),
  last_used_at timestamptz not null default now()
);

create index tts_audio_cache_session_idx
  on public.tts_audio_cache(user_id, session_id, last_used_at desc);

create table public.voice_turn_metrics (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  turn_index integer check (turn_index is null or turn_index >= 0),
  candidate_turn_id uuid references public.turns(id) on delete set null,
  interviewer_turn_id uuid references public.turns(id) on delete set null,
  audio_upload_ms integer not null default 0 check (audio_upload_ms >= 0),
  audio_processing_ms integer not null default 0 check (audio_processing_ms >= 0),
  stt_ms integer not null default 0 check (stt_ms >= 0),
  context_build_ms integer not null default 0 check (context_build_ms >= 0),
  interviewer_ms integer not null default 0 check (interviewer_ms >= 0),
  tts_ms integer not null default 0 check (tts_ms >= 0),
  storage_ms integer not null default 0 check (storage_ms >= 0),
  total_turn_ms integer not null default 0 check (total_turn_ms >= 0),
  stt_provider text,
  stt_model text,
  tts_provider text,
  tts_model text,
  created_at timestamptz not null default now()
);

create index voice_turn_metrics_session_idx
  on public.voice_turn_metrics(session_id, created_at desc);

alter table public.voice_turn_requests enable row level security;
alter table public.tts_audio_cache enable row level security;
alter table public.voice_turn_metrics enable row level security;

revoke all on public.voice_turn_requests, public.tts_audio_cache,
  public.voice_turn_metrics from anon, authenticated;
grant all on public.voice_turn_requests, public.tts_audio_cache,
  public.voice_turn_metrics to service_role;

create or replace function public.claim_voice_turn_request(
  p_session_id uuid,
  p_user_id uuid,
  p_client_turn_id uuid,
  p_recorded_duration_ms integer
)
returns table (
  id uuid,
  session_id uuid,
  user_id uuid,
  client_turn_id uuid,
  status text,
  candidate_audio_path text,
  candidate_audio_mime_type text,
  recorded_duration_ms integer,
  candidate_turn_id uuid,
  interviewer_turn_id uuid,
  response_json jsonb,
  error_code text,
  created_at timestamptz,
  updated_at timestamptz,
  claimed boolean
)
language plpgsql
set search_path = public
as $$
declare
  existing public.voice_turn_requests%rowtype;
begin
  perform 1 from public.sessions s
  where s.id = p_session_id and s.user_id = p_user_id and s.status = 'ACTIVE'
  for update;
  if not found then
    raise exception 'active session not found';
  end if;

  select * into existing from public.voice_turn_requests v
  where v.session_id = p_session_id and v.client_turn_id = p_client_turn_id
  for update;

  if found and existing.status in ('COMPLETED', 'PROCESSING')
    and not (
      existing.status = 'PROCESSING'
      and existing.updated_at < now() - interval '2 minutes'
    ) then
    return query select
      existing.id, existing.session_id, existing.user_id,
      existing.client_turn_id, existing.status, existing.candidate_audio_path,
      existing.candidate_audio_mime_type, existing.recorded_duration_ms,
      existing.candidate_turn_id, existing.interviewer_turn_id,
      existing.response_json, existing.error_code, existing.created_at,
      existing.updated_at, false;
    return;
  end if;

  if found then
    update public.voice_turn_requests v set
      status = 'PROCESSING',
      error_code = null,
      recorded_duration_ms = p_recorded_duration_ms,
      updated_at = now()
    where v.id = existing.id
    returning v.* into existing;
  else
    insert into public.voice_turn_requests (
      session_id, user_id, client_turn_id, status, recorded_duration_ms
    ) values (
      p_session_id, p_user_id, p_client_turn_id, 'PROCESSING',
      p_recorded_duration_ms
    ) returning * into existing;
  end if;

  return query select
    existing.id, existing.session_id, existing.user_id,
    existing.client_turn_id, existing.status, existing.candidate_audio_path,
    existing.candidate_audio_mime_type, existing.recorded_duration_ms,
    existing.candidate_turn_id, existing.interviewer_turn_id,
    existing.response_json, existing.error_code, existing.created_at,
    existing.updated_at, true;
end;
$$;

revoke all on function public.claim_voice_turn_request(uuid, uuid, uuid, integer)
  from public, anon, authenticated;
grant execute on function public.claim_voice_turn_request(uuid, uuid, uuid, integer)
  to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'private-interview-audio',
  'private-interview-audio',
  false,
  10485760,
  array['audio/webm', 'audio/ogg', 'audio/mp4', 'audio/wav', 'audio/mpeg']
)
on conflict (id) do update set
  public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

commit;

