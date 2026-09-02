begin;

alter table public.flags
  add column if not exists consumed_at_turn integer,
  add column if not exists consumed_at timestamptz,
  add column if not exists interviewer_turn_id uuid references public.turns(id) on delete set null;

-- Old consumed rows predate auditable activation. Return them to unresolved state rather
-- than inventing a consuming interviewer turn.
update public.flags
set consumed = false
where consumed = true and interviewer_turn_id is null;

alter table public.flags
  add constraint flags_consumption_audit_consistent check (
    (consumed = false and consumed_at_turn is null and consumed_at is null and interviewer_turn_id is null)
    or
    (consumed = true and consumed_at_turn is not null and consumed_at is not null and interviewer_turn_id is not null)
  );

create index flags_live_eligibility_idx
  on public.flags(session_id, severity desc, confidence desc, created_at asc)
  where consumed = false and safe_to_surface = true and resolved_at is null and disputed = false;

create or replace function public.get_eligible_skeptic_flags(
  p_session_id uuid,
  p_user_id uuid,
  p_current_candidate_turn_index integer,
  p_min_confidence numeric,
  p_allow_shadow boolean default false
)
returns table (
  id uuid,
  claim_id uuid,
  flag_type text,
  severity text,
  confidence numeric,
  reason text,
  suggested_probe text,
  detected_at_turn integer,
  created_at timestamptz,
  claim_summary text,
  claim_verification_priority text,
  consumed boolean,
  safe_to_surface boolean,
  shadow_mode boolean,
  disputed boolean,
  resolved_at timestamptz
)
language sql
security definer
set search_path = public
as $$
  select f.id, f.claim_id, f.flag_type::text, f.severity, f.confidence,
         f.reason, f.suggested_probe, f.detected_at_turn, f.created_at,
         c.claim_text, c.verification_priority::text,
         f.consumed, f.safe_to_surface, f.shadow_mode, f.disputed, f.resolved_at
  from public.flags f
  join public.sessions s on s.id = f.session_id
  left join public.claims c on c.id = f.claim_id and c.user_id = p_user_id
  where f.session_id = p_session_id
    and s.user_id = p_user_id
    and s.status::text = 'ACTIVE'
    and f.consumed = false
    and f.safe_to_surface = true
    and (f.shadow_mode = false or p_allow_shadow)
    and f.detected_at_turn < p_current_candidate_turn_index
    and f.confidence >= p_min_confidence
    and f.resolved_at is null
    and f.disputed = false
  order by f.created_at asc, f.id asc
  limit 50;
$$;

create or replace function public.consume_skeptic_flag(
  p_flag_id uuid,
  p_session_id uuid,
  p_user_id uuid,
  p_current_candidate_turn_index integer,
  p_interviewer_turn_id uuid,
  p_min_confidence numeric,
  p_allow_shadow boolean default false
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  updated_count integer;
begin
  if not exists (
    select 1
    from public.sessions s
    join public.turns candidate
      on candidate.session_id = s.id
     and candidate.turn_index = p_current_candidate_turn_index
     and candidate.speaker = 'candidate'
    join public.turns interviewer
      on interviewer.id = p_interviewer_turn_id
     and interviewer.session_id = s.id
     and interviewer.speaker = 'interviewer'
     and interviewer.response_to_turn_id = candidate.id
    where s.id = p_session_id
      and s.user_id = p_user_id
      and s.status::text = 'ACTIVE'
  ) then
    return false;
  end if;

  update public.flags f
  set consumed = true,
      consumed_at_turn = p_current_candidate_turn_index,
      consumed_at = now(),
      interviewer_turn_id = p_interviewer_turn_id
  where f.id = p_flag_id
    and f.session_id = p_session_id
    and f.consumed = false
    and f.safe_to_surface = true
    and (f.shadow_mode = false or p_allow_shadow)
    and f.detected_at_turn < p_current_candidate_turn_index
    and f.confidence >= p_min_confidence
    and f.resolved_at is null
    and f.disputed = false;
  get diagnostics updated_count = row_count;
  return updated_count = 1;
end;
$$;

revoke all on function public.get_eligible_skeptic_flags(uuid, uuid, integer, numeric, boolean) from public, anon, authenticated;
revoke all on function public.consume_skeptic_flag(uuid, uuid, uuid, integer, uuid, numeric, boolean) from public, anon, authenticated;
grant execute on function public.get_eligible_skeptic_flags(uuid, uuid, integer, numeric, boolean) to service_role;
grant execute on function public.consume_skeptic_flag(uuid, uuid, uuid, integer, uuid, numeric, boolean) to service_role;

commit;

