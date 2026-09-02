begin;

alter type public.session_status add value if not exists 'CREATED';
alter type public.session_status add value if not exists 'PREPARING';
alter type public.session_status add value if not exists 'READY';
alter type public.session_status add value if not exists 'ACTIVE';
alter type public.session_status add value if not exists 'ASSESSING';
alter type public.session_status add value if not exists 'COMPLETED';
alter type public.session_status add value if not exists 'FAILED';

commit;

begin;

update public.sessions set status = case status::text
  when 'draft' then 'CREATED'::public.session_status
  when 'prepared' then 'READY'::public.session_status
  when 'in_progress' then 'ACTIVE'::public.session_status
  when 'processing' then 'ASSESSING'::public.session_status
  when 'complete' then 'COMPLETED'::public.session_status
  when 'failed' then 'FAILED'::public.session_status
  else status
end;

alter table public.sessions
  alter column status set default 'CREATED',
  add column if not exists updated_at timestamptz not null default now(),
  add column if not exists phase_started_at timestamptz not null default now(),
  add column if not exists phase_time_budget_seconds integer not null default 180,
  add column if not exists total_time_budget_seconds integer not null default 1200,
  add column if not exists elapsed_seconds integer not null default 0,
  add column if not exists current_primary_question_id text,
  add column if not exists current_probe_count integer not null default 0,
  add column if not exists total_questions integer not null default 0,
  add column if not exists recovery_count integer not null default 0,
  add constraint sessions_phase_budget_positive check (phase_time_budget_seconds > 0),
  add constraint sessions_total_budget_positive check (total_time_budget_seconds > 0),
  add constraint sessions_elapsed_valid check (
    elapsed_seconds >= 0 and elapsed_seconds <= total_time_budget_seconds
  ),
  add constraint sessions_probe_cap check (current_probe_count between 0 and 2),
  add constraint sessions_question_count_valid check (total_questions >= 0),
  add constraint sessions_recovery_count_valid check (recovery_count >= 0);

drop trigger if exists sessions_set_updated_at on public.sessions;
create trigger sessions_set_updated_at
  before update on public.sessions
  for each row execute procedure public.set_updated_at();

create table public.session_events (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint session_events_type_length check (char_length(trim(event_type)) between 3 and 100),
  constraint session_events_payload_object check (jsonb_typeof(payload) = 'object')
);

create index session_events_session_created_idx
  on public.session_events(session_id, created_at);

alter table public.session_events enable row level security;
create policy session_events_select_own
  on public.session_events for select to authenticated using (user_id = auth.uid());
revoke insert, update, delete on public.session_events from authenticated;
grant select on public.session_events to authenticated;
grant all on public.session_events to service_role;

create or replace function public.enforce_session_lifecycle()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if old.status <> new.status and not (
    (old.status = 'CREATED' and new.status in ('PREPARING', 'FAILED')) or
    (old.status = 'PREPARING' and new.status in ('READY', 'FAILED')) or
    (old.status = 'READY' and new.status in ('ACTIVE', 'FAILED')) or
    (old.status = 'ACTIVE' and new.status in ('ASSESSING', 'FAILED')) or
    (old.status = 'ASSESSING' and new.status in ('COMPLETED', 'FAILED'))
  ) then
    raise exception 'illegal session status transition: % to %', old.status, new.status;
  end if;
  if old.status in ('ACTIVE', 'ASSESSING', 'COMPLETED', 'FAILED')
    and new.total_time_budget_seconds <> old.total_time_budget_seconds then
    raise exception 'session time budget cannot be extended after start';
  end if;
  return new;
end;
$$;

create trigger sessions_enforce_lifecycle
  before update on public.sessions
  for each row execute procedure public.enforce_session_lifecycle();

create or replace function public.apply_interview_state_change(
  p_session_id uuid,
  p_user_id uuid,
  p_expected_updated_at timestamptz,
  p_values jsonb,
  p_event_type text,
  p_event_payload jsonb
)
returns setof public.sessions
language plpgsql
set search_path = public
as $$
declare
  changed public.sessions%rowtype;
begin
  update public.sessions set
    status = coalesce((p_values ->> 'status')::public.session_status, status),
    phase = coalesce((p_values ->> 'phase')::public.interview_phase, phase),
    phase_started_at = coalesce((p_values ->> 'phase_started_at')::timestamptz, phase_started_at),
    elapsed_seconds = coalesce((p_values ->> 'elapsed_seconds')::integer, elapsed_seconds),
    current_primary_question_id = case
      when p_values ? 'current_primary_question_id'
        then nullif(p_values ->> 'current_primary_question_id', '')
      else current_primary_question_id end,
    current_probe_count = coalesce((p_values ->> 'current_probe_count')::integer, current_probe_count),
    total_questions = coalesce((p_values ->> 'total_questions')::integer, total_questions),
    recovery_count = coalesce((p_values ->> 'recovery_count')::integer, recovery_count),
    completion_pct = coalesce((p_values ->> 'completion_pct')::numeric, completion_pct),
    started_at = case when p_values ? 'started_at'
      then (p_values ->> 'started_at')::timestamptz else started_at end,
    completed_at = case when p_values ? 'completed_at'
      then (p_values ->> 'completed_at')::timestamptz else completed_at end
  where id = p_session_id and user_id = p_user_id and updated_at = p_expected_updated_at
  returning * into changed;

  if changed.id is null then
    raise exception 'session not found or changed concurrently';
  end if;
  insert into public.session_events (session_id, user_id, event_type, payload)
  values (p_session_id, p_user_id, trim(p_event_type), coalesce(p_event_payload, '{}'::jsonb));
  return next changed;
end;
$$;

revoke all on function public.apply_interview_state_change(
  uuid, uuid, timestamptz, jsonb, text, jsonb
) from public, anon, authenticated;
grant execute on function public.apply_interview_state_change(
  uuid, uuid, timestamptz, jsonb, text, jsonb
) to service_role;

commit;

