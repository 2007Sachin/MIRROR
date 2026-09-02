begin;

create type public.claim_resolution_trigger as enum (
  'SKEPTIC_FLAG', 'EVIDENCE_AGENT', 'USER_CORRECTION',
  'ADMIN_REVIEW', 'SESSION_FINALIZATION'
);

create table public.claim_resolutions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  claim_id uuid not null references public.claims(id) on delete cascade,
  previous_status public.claim_status not null,
  new_status public.claim_status not null,
  resolution_reason text not null check (char_length(trim(resolution_reason)) between 3 and 2000),
  evidence_ids uuid[] not null default '{}',
  trigger_type public.claim_resolution_trigger not null,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  created_at timestamptz not null default now()
);

create index claim_resolutions_history_idx
  on public.claim_resolutions(claim_id, created_at asc);

alter table public.claim_resolutions enable row level security;
create policy claim_resolutions_select_own on public.claim_resolutions
  for select to authenticated using (user_id = auth.uid());
revoke insert, update, delete on public.claim_resolutions from authenticated;
grant select on public.claim_resolutions to authenticated;
grant all on public.claim_resolutions to service_role;

create or replace function public.resolve_claim_state(
  p_claim_id uuid, p_user_id uuid, p_expected_status public.claim_status,
  p_new_status public.claim_status, p_reason text, p_evidence_ids uuid[],
  p_trigger_type public.claim_resolution_trigger, p_confidence numeric
)
returns jsonb
language plpgsql security definer set search_path = public
as $$
declare
  old_claim public.claims%rowtype;
  updated_claim public.claims%rowtype;
  resolution public.claim_resolutions%rowtype;
  next_version integer;
begin
  select * into old_claim from public.claims
  where id = p_claim_id and user_id = p_user_id for update;
  if old_claim.id is null then raise exception 'claim_resolution_not_found'; end if;
  if old_claim.status <> p_expected_status then raise exception 'claim_resolution_conflict'; end if;
  if char_length(trim(p_reason)) < 3 then raise exception 'claim_resolution_reason_required'; end if;
  if p_confidence < 0 or p_confidence > 1 then raise exception 'claim_resolution_confidence_invalid'; end if;
  if exists (
    select 1 from unnest(coalesce(p_evidence_ids, '{}')) evidence_id
    where not exists (
      select 1 from public.claim_evidence e
      where e.id=evidence_id and e.claim_id=p_claim_id and e.user_id=p_user_id
        and coalesce(e.validated, false)=true
    )
  ) then raise exception 'claim_resolution_evidence_invalid'; end if;

  select coalesce(max(version),0)+1 into next_version
  from public.claim_versions where claim_id=p_claim_id;
  insert into public.claim_versions (
    user_id, claim_id, version, previous_state, new_state, changed_by, reason
  ) values (
    p_user_id, p_claim_id, next_version,
    jsonb_build_object('claim_text',old_claim.claim_text,'status',upper(old_claim.status::text),'confidence',old_claim.confidence),
    jsonb_build_object('claim_text',old_claim.claim_text,'status',upper(p_new_status::text),'confidence',old_claim.confidence,
      'trigger_type',p_trigger_type::text,'evidence_ids',coalesce(p_evidence_ids,'{}')),
    case p_trigger_type when 'USER_CORRECTION' then 'USER'::public.claim_changed_by
      when 'ADMIN_REVIEW' then 'ADMIN'::public.claim_changed_by
      when 'EVIDENCE_AGENT' then 'AI'::public.claim_changed_by
      else 'SYSTEM'::public.claim_changed_by end,
    trim(p_reason)
  );
  update public.claims set status=p_new_status where id=p_claim_id returning * into updated_claim;
  insert into public.claim_resolutions (
    user_id,claim_id,previous_status,new_status,resolution_reason,evidence_ids,trigger_type,confidence
  ) values (
    p_user_id,p_claim_id,old_claim.status,p_new_status,trim(p_reason),
    coalesce(p_evidence_ids,'{}'),p_trigger_type,p_confidence
  ) returning * into resolution;
  return jsonb_build_object('claim',to_jsonb(updated_claim),'resolution',to_jsonb(resolution));
end;
$$;

-- Retire the former generic write path. Status commits now require expected-state
-- comparison, validated evidence references, and a resolution audit record.
revoke execute on function public.update_claim_status(
  uuid, uuid, public.claim_status, public.claim_changed_by, text
) from service_role;
revoke all on function public.resolve_claim_state(
  uuid,uuid,public.claim_status,public.claim_status,text,uuid[],public.claim_resolution_trigger,numeric
) from public, anon, authenticated;
grant execute on function public.resolve_claim_state(
  uuid,uuid,public.claim_status,public.claim_status,text,uuid[],public.claim_resolution_trigger,numeric
) to service_role;

commit;

