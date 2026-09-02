begin;

alter table public.claim_evidence
  add column if not exists source_type text,
  add column if not exists source_id uuid,
  add column if not exists reason_code text,
  add column if not exists agent_model text,
  add column if not exists prompt_version text,
  add column if not exists evidence_execution_id uuid,
  add column if not exists validated boolean not null default false,
  add column if not exists evidence_key text,
  add column if not exists evidence_strength text;

alter table public.claim_evidence
  add constraint claim_evidence_strength_value check (evidence_strength is null or evidence_strength in ('NONE','WEAK','MODERATE','STRONG')),
  add constraint claim_evidence_source_type_value check (
    source_type is null or source_type in ('RESUME','CANDIDATE_TURN','INTERVIEWER_TURN','PROJECT','OTHER_DOCUMENT')
  );

create unique index claim_evidence_validated_dedupe_idx
  on public.claim_evidence(claim_id, evidence_key)
  where evidence_key is not null and validated = true;

create or replace function public.evidence_normalize(p_text text)
returns text language sql immutable strict
as $$
  select trim(regexp_replace(translate(p_text, '“”’–—', '""''--'), '\s+', ' ', 'g'));
$$;

create or replace function public.insert_validated_claim_evidence(
  p_claim_id uuid, p_user_id uuid, p_source_type text, p_source_id uuid,
  p_turn_id uuid, p_document_id uuid, p_quote_text text,
  p_direction text, p_strength text, p_reason_code text,
  p_execution_id uuid, p_model text, p_prompt_version text
)
returns boolean
language plpgsql security definer set search_path = public
as $$
declare source_text text; key_value text; inserted_count integer;
begin
  if not exists (select 1 from public.claims where id = p_claim_id and user_id = p_user_id) then
    return false;
  end if;
  if p_source_type in ('CANDIDATE_TURN','INTERVIEWER_TURN') then
    select t.text into source_text from public.turns t join public.sessions s on s.id=t.session_id
    where t.id=p_source_id and t.id=p_turn_id and s.user_id=p_user_id
      and ((p_source_type='CANDIDATE_TURN' and t.speaker='candidate')
        or (p_source_type='INTERVIEWER_TURN' and t.speaker='interviewer'));
  elsif p_source_type in ('RESUME','OTHER_DOCUMENT') then
    select d.raw_text into source_text from public.documents d
    where d.id=p_source_id and d.id=p_document_id and d.user_id=p_user_id
      and (p_source_type<>'RESUME' or d.document_type='resume');
  else
    return false;
  end if;
  if source_text is null or position(public.evidence_normalize(p_quote_text) in public.evidence_normalize(source_text)) = 0 then
    return false;
  end if;
  key_value := encode(digest(
    p_source_type || ':' || p_source_id::text || ':' || public.evidence_normalize(p_quote_text) || ':' || p_direction,
    'sha256'), 'hex');
  insert into public.claim_evidence (
    user_id, claim_id, evidence_type, source_type, source_id, turn_id, document_id,
    quote_text, evidence_direction, strength, evidence_strength, reason_code, agent_model, prompt_version,
    evidence_execution_id, validated, evidence_key
  ) values (
    p_user_id, p_claim_id,
    case when p_turn_id is not null then 'INTERVIEW_TURN'::public.claim_evidence_type else 'DOCUMENT_EXCERPT'::public.claim_evidence_type end,
    p_source_type, p_source_id, p_turn_id, p_document_id, p_quote_text,
    p_direction::public.evidence_direction,
    case p_strength when 'NONE' then 0 when 'WEAK' then 0.25 when 'MODERATE' then 0.65 else 1 end,
    p_strength, p_reason_code, p_model,
    p_prompt_version, p_execution_id, true, key_value
  ) on conflict (claim_id, evidence_key) where evidence_key is not null and validated = true do nothing;
  get diagnostics inserted_count = row_count;
  return inserted_count = 1;
end;
$$;

revoke all on function public.evidence_normalize(text) from public, anon, authenticated;
revoke all on function public.insert_validated_claim_evidence(uuid,uuid,text,uuid,uuid,uuid,text,text,text,text,uuid,text,text) from public, anon, authenticated;
grant execute on function public.insert_validated_claim_evidence(uuid,uuid,text,uuid,uuid,uuid,text,text,text,text,uuid,text,text) to service_role;

commit;

