begin;

create type public.resume_analysis_status as enum ('PROCESSING', 'COMPLETED', 'FAILED');
create type public.verification_priority as enum ('LOW', 'MEDIUM', 'HIGH');
create type public.claim_review_status as enum ('CORRECT', 'NEEDS_CORRECTION');

create table public.resume_analyses (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  version integer not null check (version > 0),
  status public.resume_analysis_status not null default 'PROCESSING',
  output jsonb,
  model text not null,
  prompt_version text not null,
  analysis_version text not null,
  execution_id uuid,
  error_type text,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (document_id, version),
  constraint resume_analyses_output_state check (
    (status = 'COMPLETED' and output is not null and completed_at is not null)
    or (status = 'FAILED' and completed_at is not null)
    or (status = 'PROCESSING' and output is null and completed_at is null)
  )
);

create unique index resume_analyses_one_processing_idx
  on public.resume_analyses(document_id)
  where status = 'PROCESSING';
create index resume_analyses_owner_document_idx
  on public.resume_analyses(user_id, document_id, version desc);

-- Resume claims exist before an interview session. Keep the later session ledger
-- compatible while attaching these claims to their immutable source analysis.
alter table public.claims
  alter column session_id drop not null,
  add column source_document_id uuid references public.documents(id) on delete cascade,
  add column resume_analysis_id uuid references public.resume_analyses(id) on delete cascade,
  add column source_reference text,
  add column verification_priority public.verification_priority,
  add column skill text,
  add column project_name text,
  add column metric_value numeric,
  add column metric_unit text,
  add column ownership_language text,
  add column outcome text,
  add column tool text;

update public.claims set source_reference = source_ref where source_reference is null;

alter table public.claims
  add constraint claims_have_context check (
    session_id is not null or (source_document_id is not null and resume_analysis_id is not null)
  );

create index claims_resume_analysis_idx on public.claims(resume_analysis_id, created_at);
create index claims_source_document_idx on public.claims(source_document_id);

create table public.resume_claim_corrections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  resume_analysis_id uuid not null references public.resume_analyses(id) on delete cascade,
  claim_id uuid not null references public.claims(id) on delete cascade,
  version integer not null check (version > 0),
  review_status public.claim_review_status not null,
  corrected_claim_text text,
  created_at timestamptz not null default now(),
  unique (claim_id, version),
  constraint correction_text_required check (
    (review_status = 'CORRECT' and corrected_claim_text is null)
    or (
      review_status = 'NEEDS_CORRECTION'
      and char_length(trim(corrected_claim_text)) between 3 and 2000
    )
  )
);

create index resume_claim_corrections_latest_idx
  on public.resume_claim_corrections(claim_id, version desc);

alter table public.resume_analyses enable row level security;
alter table public.resume_claim_corrections enable row level security;

create policy resume_analyses_select_own
  on public.resume_analyses for select to authenticated
  using (user_id = auth.uid());

create policy resume_claim_corrections_select_own
  on public.resume_claim_corrections for select to authenticated
  using (user_id = auth.uid());

revoke insert, update, delete on public.resume_analyses from authenticated;
revoke insert, update, delete on public.resume_claim_corrections from authenticated;
grant select on public.resume_analyses to authenticated;
grant select on public.resume_claim_corrections to authenticated;
grant all on public.resume_analyses to service_role;
grant all on public.resume_claim_corrections to service_role;

create or replace function public.complete_resume_analysis(
  p_analysis_id uuid,
  p_user_id uuid,
  p_execution_id uuid,
  p_output jsonb
)
returns setof public.resume_analyses
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.resume_analyses
    where id = p_analysis_id and user_id = p_user_id and status = 'PROCESSING'
    for update
  ) then
    raise exception 'resume analysis is not available for completion';
  end if;

  insert into public.claims (
    session_id, user_id, claim_text, claim_type, source, source_ref, status,
    confidence, source_document_id, resume_analysis_id, source_reference,
    verification_priority, skill, project_name, metric_value, metric_unit,
    ownership_language, outcome, tool
  )
  select
    null,
    p_user_id,
    claim ->> 'claim_text',
    lower(claim ->> 'claim_type')::public.claim_type,
    'resume'::public.claim_source,
    claim ->> 'source_reference',
    'unverified'::public.claim_status,
    (claim ->> 'confidence')::numeric,
    analysis.document_id,
    analysis.id,
    claim ->> 'source_reference',
    (claim ->> 'verification_priority')::public.verification_priority,
    claim ->> 'skill',
    claim ->> 'project_name',
    nullif(claim ->> 'metric_value', '')::numeric,
    claim ->> 'metric_unit',
    claim ->> 'ownership_language',
    claim ->> 'outcome',
    claim ->> 'tool'
  from public.resume_analyses analysis
  cross join lateral jsonb_array_elements(coalesce(p_output -> 'claims', '[]'::jsonb)) claim
  where analysis.id = p_analysis_id and analysis.user_id = p_user_id;

  return query
  update public.resume_analyses
  set status = 'COMPLETED',
      output = p_output,
      execution_id = p_execution_id,
      completed_at = now()
  where id = p_analysis_id and user_id = p_user_id
  returning *;
end;
$$;

create or replace function public.create_resume_claim_correction(
  p_document_id uuid,
  p_user_id uuid,
  p_claim_id uuid,
  p_review_status public.claim_review_status,
  p_corrected_claim_text text
)
returns setof public.resume_claim_corrections
language plpgsql
set search_path = public
as $$
declare
  target_analysis_id uuid;
  next_version integer;
begin
  select c.resume_analysis_id into target_analysis_id
  from public.claims c
  join public.resume_analyses a on a.id = c.resume_analysis_id
  where c.id = p_claim_id
    and c.user_id = p_user_id
    and c.source_document_id = p_document_id
    and a.user_id = p_user_id
  for update of c;

  if target_analysis_id is null then
    raise exception 'resume claim not found';
  end if;

  select coalesce(max(version), 0) + 1 into next_version
  from public.resume_claim_corrections
  where claim_id = p_claim_id;

  return query
  insert into public.resume_claim_corrections (
    user_id, resume_analysis_id, claim_id, version, review_status, corrected_claim_text
  ) values (
    p_user_id, target_analysis_id, p_claim_id, next_version,
    p_review_status, p_corrected_claim_text
  )
  returning *;
end;
$$;

revoke all on function public.complete_resume_analysis(uuid, uuid, uuid, jsonb)
  from public, anon, authenticated;
revoke all on function public.create_resume_claim_correction(
  uuid, uuid, uuid, public.claim_review_status, text
) from public, anon, authenticated;
grant execute on function public.complete_resume_analysis(uuid, uuid, uuid, jsonb)
  to service_role;
grant execute on function public.create_resume_claim_correction(
  uuid, uuid, uuid, public.claim_review_status, text
) to service_role;

commit;

