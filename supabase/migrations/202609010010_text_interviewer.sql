begin;

alter table public.turns
  add column if not exists client_turn_id uuid,
  add column if not exists response_to_turn_id uuid references public.turns(id) on delete set null,
  add column if not exists primary_thread_id text,
  add column if not exists agent_execution_id uuid,
  add column if not exists model text,
  add column if not exists prompt_version text,
  add column if not exists latency_ms integer check (latency_ms is null or latency_ms >= 0),
  add column if not exists retry_count integer check (retry_count is null or retry_count >= 0),
  add column if not exists target_claim_ids uuid[] not null default '{}',
  add column if not exists target_competency_ids uuid[] not null default '{}';

alter table public.turns
  drop constraint if exists turns_session_id_turn_index_speaker_key;
create unique index turns_session_turn_index_unique
  on public.turns(session_id, turn_index);
create unique index turns_candidate_client_id_unique
  on public.turns(session_id, client_turn_id)
  where client_turn_id is not null;
create unique index turns_interviewer_response_unique
  on public.turns(response_to_turn_id)
  where response_to_turn_id is not null;
create index turns_session_recent_idx
  on public.turns(session_id, turn_index desc);

create or replace function public.create_candidate_text_turn(
  p_session_id uuid,
  p_user_id uuid,
  p_text text,
  p_client_turn_id uuid,
  p_turn_type public.turn_type,
  p_phase public.interview_phase,
  p_primary_thread_id text
)
returns setof public.turns
language plpgsql
set search_path = public
as $$
declare
  next_index integer;
begin
  perform 1 from public.sessions
  where id = p_session_id and user_id = p_user_id and status = 'ACTIVE'
  for update;
  if not found then
    raise exception 'active session not found';
  end if;

  return query select t.* from public.turns t
  where t.session_id = p_session_id and t.client_turn_id = p_client_turn_id;
  if found then return; end if;
  select coalesce(max(turn_index), -1) + 1 into next_index
  from public.turns where session_id = p_session_id;
  return query insert into public.turns (
    session_id, turn_index, speaker, text, turn_type, phase,
    client_turn_id, primary_thread_id
  ) values (
    p_session_id, next_index, 'candidate', trim(p_text), p_turn_type, p_phase,
    p_client_turn_id, p_primary_thread_id
  ) returning *;
end;
$$;

create or replace function public.create_interviewer_text_turn(
  p_session_id uuid,
  p_user_id uuid,
  p_response_to_turn_id uuid,
  p_text text,
  p_turn_type public.turn_type,
  p_phase public.interview_phase,
  p_primary_thread_id text,
  p_agent_execution_id uuid,
  p_model text,
  p_prompt_version text,
  p_latency_ms integer,
  p_retry_count integer,
  p_target_claim_ids uuid[],
  p_target_competency_ids uuid[]
)
returns setof public.turns
language plpgsql
set search_path = public
as $$
declare
  next_index integer;
begin
  perform 1 from public.sessions
  where id = p_session_id and user_id = p_user_id
    and status in ('ACTIVE', 'ASSESSING')
  for update;
  if not found then
    raise exception 'interview session not found';
  end if;

  if p_response_to_turn_id is not null then
    return query select t.* from public.turns t
    where t.response_to_turn_id = p_response_to_turn_id;
    if found then return; end if;
  else
    return query select t.* from public.turns t
    where t.session_id = p_session_id and t.speaker = 'interviewer'
      and t.primary_thread_id = p_primary_thread_id and t.turn_index = 0;
    if found then return; end if;
  end if;

  if p_response_to_turn_id is not null and not exists (
    select 1 from public.turns
    where id = p_response_to_turn_id and session_id = p_session_id and speaker = 'candidate'
  ) then
    raise exception 'candidate turn not found';
  end if;
  select coalesce(max(turn_index), -1) + 1 into next_index
  from public.turns where session_id = p_session_id;
  return query insert into public.turns (
    session_id, turn_index, speaker, text, turn_type, phase,
    response_to_turn_id, primary_thread_id, agent_execution_id, model,
    prompt_version, latency_ms, retry_count, target_claim_ids, target_competency_ids
  ) values (
    p_session_id, next_index, 'interviewer', trim(p_text), p_turn_type, p_phase,
    p_response_to_turn_id, p_primary_thread_id, p_agent_execution_id, p_model,
    p_prompt_version, p_latency_ms, p_retry_count,
    coalesce(p_target_claim_ids, '{}'), coalesce(p_target_competency_ids, '{}')
  ) returning *;
end;
$$;

revoke all on function public.create_candidate_text_turn(
  uuid, uuid, text, uuid, public.turn_type, public.interview_phase, text
) from public, anon, authenticated;
revoke all on function public.create_interviewer_text_turn(
  uuid, uuid, uuid, text, public.turn_type, public.interview_phase, text,
  uuid, text, text, integer, integer, uuid[], uuid[]
) from public, anon, authenticated;
grant execute on function public.create_candidate_text_turn(
  uuid, uuid, text, uuid, public.turn_type, public.interview_phase, text
) to service_role;
grant execute on function public.create_interviewer_text_turn(
  uuid, uuid, uuid, text, public.turn_type, public.interview_phase, text,
  uuid, text, text, integer, integer, uuid[], uuid[]
) to service_role;

commit;

