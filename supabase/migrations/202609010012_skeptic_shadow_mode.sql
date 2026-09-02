begin;

alter type public.flag_type add value if not exists 'clarification';
alter type public.flag_type add value if not exists 'additional_detail';
alter type public.flag_type add value if not exists 'scope_difference';
alter type public.flag_type add value if not exists 'timeline_difference';
alter type public.flag_type add value if not exists 'paraphrase';
alter type public.flag_type add value if not exists 'corroboration';

commit;

begin;

alter table public.flags drop constraint if exists flags_severity_check;
alter table public.flags
  alter column severity type text using (
    case severity::text
      when '1' then 'LOW'
      when '2' then 'MEDIUM'
      when '3' then 'HIGH'
      else upper(severity::text)
    end
  ),
  add column if not exists reason text,
  add column if not exists safe_to_surface boolean not null default false,
  add column if not exists shadow_mode boolean not null default true,
  add column if not exists source_turn_id uuid references public.turns(id) on delete cascade,
  add column if not exists related_turn_ids uuid[] not null default '{}',
  add column if not exists skeptic_execution_id uuid,
  add column if not exists dedupe_key text,
  add column if not exists resolved_at timestamptz,
  add constraint flags_severity_value check (severity in ('LOW', 'MEDIUM', 'HIGH')),
  add constraint flags_reason_length check (
    reason is null or char_length(trim(reason)) between 3 and 2000
  );

update public.flags
set reason = coalesce(nullif(trim(distinction), ''), suggested_probe)
where reason is null;

update public.flags f
set source_turn_id = t.id
from public.turns t
where f.source_turn_id is null
  and t.session_id = f.session_id
  and t.turn_index = f.detected_at_turn
  and t.speaker = 'candidate';

alter table public.flags alter column reason set not null;

create unique index flags_active_dedupe_idx
  on public.flags(dedupe_key)
  where dedupe_key is not null and resolved_at is null;

create table public.skeptic_observations (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_turn_id uuid not null references public.turns(id) on delete cascade,
  skeptic_execution_id uuid not null,
  observation_type text not null check (observation_type in (
    'CONTRADICTION', 'VAGUENESS', 'UNSUPPORTED_SCALE', 'OWNERSHIP_DRIFT',
    'CLARIFICATION', 'ADDITIONAL_DETAIL', 'SCOPE_DIFFERENCE',
    'TIMELINE_DIFFERENCE', 'PARAPHRASE', 'CORROBORATION'
  )),
  summary text not null check (char_length(trim(summary)) between 3 and 2000),
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  related_claim_ids uuid[] not null default '{}',
  related_turn_ids uuid[] not null default '{}',
  dedupe_key text not null,
  created_at timestamptz not null default now(),
  unique(dedupe_key)
);

create table public.skeptic_claim_update_proposals (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_turn_id uuid not null references public.turns(id) on delete cascade,
  claim_id uuid not null references public.claims(id) on delete cascade,
  skeptic_execution_id uuid not null,
  proposed_status public.claim_status not null,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  reason text not null check (char_length(trim(reason)) between 3 and 2000),
  related_turn_ids uuid[] not null default '{}',
  reviewed boolean not null default false,
  accepted boolean,
  reviewed_by uuid references public.profiles(id) on delete set null,
  reviewed_at timestamptz,
  dedupe_key text not null,
  created_at timestamptz not null default now(),
  unique(dedupe_key)
);

create table public.skeptic_analyses (
  id uuid primary key default gen_random_uuid(),
  skeptic_execution_id uuid not null unique,
  session_id uuid not null references public.sessions(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_turn_id uuid not null references public.turns(id) on delete cascade,
  model text not null,
  prompt_version text not null,
  shadow_mode boolean not null,
  success boolean not null,
  structured_output jsonb,
  latency_ms integer not null check (latency_ms >= 0),
  retry_count integer not null check (retry_count >= 0),
  flags_created integer not null default 0 check (flags_created >= 0),
  new_claims_created integer not null default 0 check (new_claims_created >= 0),
  claim_update_proposals_created integer not null default 0
    check (claim_update_proposals_created >= 0),
  observations_created integer not null default 0 check (observations_created >= 0),
  failure_type text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.jobs drop constraint if exists jobs_job_type_check;
alter table public.jobs
  add column if not exists dedupe_key text,
  add constraint jobs_job_type_check check (job_type in (
    'skeptic_turn', 'SKEPTIC_TURN_ANALYSIS', 'generate_report',
    'generate_tts', 'process_resume', 'generate_question_plan'
  ));

create unique index jobs_type_dedupe_idx
  on public.jobs(job_type, dedupe_key)
  where dedupe_key is not null;

create index skeptic_observations_session_turn_idx
  on public.skeptic_observations(session_id, source_turn_id, created_at);
create index skeptic_claim_proposals_session_idx
  on public.skeptic_claim_update_proposals(session_id, created_at);
create index skeptic_analyses_session_turn_idx
  on public.skeptic_analyses(session_id, source_turn_id, created_at);

alter table public.skeptic_observations enable row level security;
alter table public.skeptic_claim_update_proposals enable row level security;
alter table public.skeptic_analyses enable row level security;

drop policy if exists flags_owner_read on public.flags;
revoke all on public.flags, public.skeptic_observations,
  public.skeptic_claim_update_proposals, public.skeptic_analyses
  from anon, authenticated;
grant all on public.flags, public.skeptic_observations,
  public.skeptic_claim_update_proposals, public.skeptic_analyses
  to service_role;

create or replace function public.enqueue_skeptic_after_candidate_turn()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  owner_id uuid;
  queued_id uuid;
begin
  if new.speaker <> 'candidate' then
    return new;
  end if;
  select s.user_id into owner_id from public.sessions s where s.id = new.session_id;
  if owner_id is null then
    raise exception 'candidate turn session owner not found';
  end if;
  insert into public.jobs (job_type, payload, status, dedupe_key)
  values (
    'SKEPTIC_TURN_ANALYSIS',
    jsonb_build_object(
      'session_id', new.session_id,
      'turn_id', new.id,
      'user_id', owner_id,
      'prompt_version', 'v1'
    ),
    'pending',
    new.id::text || ':v1'
  )
  on conflict (job_type, dedupe_key) where dedupe_key is not null do nothing
  returning id into queued_id;
  if queued_id is not null then
    insert into public.session_events (session_id, user_id, event_type, payload)
    values (
      new.session_id,
      owner_id,
      'candidate.turn.completed',
      jsonb_build_object('turn_id', new.id, 'job_id', queued_id)
    );
  end if;
  return new;
exception
  when others then
    -- Shadow analysis must never prevent the candidate turn from committing.
    return new;
end;
$$;

drop trigger if exists turns_enqueue_skeptic_shadow on public.turns;
create trigger turns_enqueue_skeptic_shadow
  after insert on public.turns
  for each row
  when (new.speaker = 'candidate')
  execute procedure public.enqueue_skeptic_after_candidate_turn();

create or replace function public.enqueue_skeptic_turn_analysis(
  p_session_id uuid,
  p_user_id uuid,
  p_turn_id uuid,
  p_prompt_version text
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  queued_id uuid;
begin
  if not exists (
    select 1
    from public.turns t
    join public.sessions s on s.id = t.session_id
    where t.id = p_turn_id
      and t.session_id = p_session_id
      and t.speaker = 'candidate'
      and s.user_id = p_user_id
  ) then
    raise exception 'owned candidate turn not found';
  end if;

  insert into public.jobs (job_type, payload, status, dedupe_key)
  values (
    'SKEPTIC_TURN_ANALYSIS',
    jsonb_build_object(
      'session_id', p_session_id,
      'turn_id', p_turn_id,
      'user_id', p_user_id,
      'prompt_version', p_prompt_version
    ),
    'pending',
    p_turn_id::text || ':' || p_prompt_version
  )
  on conflict (job_type, dedupe_key) where dedupe_key is not null do nothing
  returning id into queued_id;

  if queued_id is not null then
    insert into public.session_events (session_id, user_id, event_type, payload)
    values (
      p_session_id,
      p_user_id,
      'candidate.turn.completed',
      jsonb_build_object('turn_id', p_turn_id, 'job_id', queued_id)
    );
  end if;

  return queued_id;
end;
$$;

create or replace function public.claim_skeptic_turn_analysis(
  p_worker_id text,
  p_max_attempts integer
)
returns setof public.jobs
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  with next_job as (
    select j.id
    from public.jobs j
    where j.job_type = 'SKEPTIC_TURN_ANALYSIS'
      and j.status = 'pending'
      and j.run_after <= now()
      and j.attempts < p_max_attempts
    order by j.run_after, j.created_at
    for update skip locked
    limit 1
  )
  update public.jobs j set
    status = 'running',
    attempts = j.attempts + 1,
    locked_at = now(),
    locked_by = left(p_worker_id, 200),
    error = null
  from next_job
  where j.id = next_job.id
  returning j.*;
end;
$$;

revoke all on function public.enqueue_skeptic_turn_analysis(uuid, uuid, uuid, text)
  from public, anon, authenticated;
revoke all on function public.claim_skeptic_turn_analysis(text, integer)
  from public, anon, authenticated;
grant execute on function public.enqueue_skeptic_turn_analysis(uuid, uuid, uuid, text)
  to service_role;
grant execute on function public.claim_skeptic_turn_analysis(text, integer)
  to service_role;
revoke all on function public.enqueue_skeptic_after_candidate_turn()
  from public, anon, authenticated;

commit;

