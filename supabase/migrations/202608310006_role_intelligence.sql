begin;

create type public.role_seniority as enum (
  'ENTRY_LEVEL', 'JUNIOR', 'MID_LEVEL', 'SENIOR', 'LEAD', 'UNSPECIFIED'
);
create type public.role_source_type as enum ('JOB_DESCRIPTION', 'SYNTHETIC_CANONICAL');
create type public.competency_category as enum (
  'TECHNICAL', 'ANALYTICAL', 'DOMAIN', 'BEHAVIOURAL', 'COMMUNICATION', 'TOOL'
);
create type public.expected_competency_level as enum (
  'FOUNDATIONAL', 'BASIC', 'INTERMEDIATE', 'ADVANCED'
);
create type public.competency_source_type as enum (
  'JOB_DESCRIPTION_EXPLICIT', 'JOB_DESCRIPTION_INFERRED', 'SYNTHETIC_CANONICAL'
);
create type public.role_analysis_status as enum ('PROCESSING', 'COMPLETED', 'FAILED');

create table public.role_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  target_role text not null,
  canonical_role text,
  seniority public.role_seniority,
  source_type public.role_source_type not null,
  source_document_id uuid references public.documents(id) on delete set null,
  current_analysis_version_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint role_profiles_target_length check (char_length(trim(target_role)) between 2 and 160)
);

create table public.role_analysis_versions (
  id uuid primary key default gen_random_uuid(),
  role_profile_id uuid not null references public.role_profiles(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  version integer not null check (version > 0),
  status public.role_analysis_status not null default 'PROCESSING',
  source_type public.role_source_type not null,
  source_document_id uuid references public.documents(id) on delete set null,
  model text not null,
  prompt_version text not null,
  analysis_version text not null,
  output jsonb,
  execution_id uuid,
  error_type text,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (role_profile_id, version),
  constraint role_analysis_output_state check (
    (status = 'COMPLETED' and output is not null and completed_at is not null)
    or (status = 'FAILED' and completed_at is not null)
    or (status = 'PROCESSING' and output is null and completed_at is null)
  )
);

alter table public.role_profiles
  add constraint role_profiles_current_analysis_fk
  foreign key (current_analysis_version_id)
  references public.role_analysis_versions(id) on delete set null;

create table public.role_competencies (
  id uuid primary key default gen_random_uuid(),
  role_profile_id uuid not null references public.role_profiles(id) on delete cascade,
  analysis_version_id uuid not null references public.role_analysis_versions(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  category public.competency_category not null,
  importance_weight numeric(4,3) not null check (importance_weight between 0 and 1),
  expected_level public.expected_competency_level not null,
  source_type public.competency_source_type not null,
  source_reference text not null,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  created_at timestamptz not null default now()
);

alter table public.profiles
  add column current_role_profile_id uuid references public.role_profiles(id) on delete set null;

create unique index role_analysis_one_processing_idx
  on public.role_analysis_versions(role_profile_id)
  where status = 'PROCESSING';
create index role_profiles_owner_idx on public.role_profiles(user_id, updated_at desc);
create index role_analysis_versions_profile_idx
  on public.role_analysis_versions(role_profile_id, version desc);
create index role_competencies_version_idx
  on public.role_competencies(analysis_version_id, importance_weight desc);

alter table public.role_profiles enable row level security;
alter table public.role_analysis_versions enable row level security;
alter table public.role_competencies enable row level security;

create policy role_profiles_select_own
  on public.role_profiles for select to authenticated using (user_id = auth.uid());
create policy role_analysis_versions_select_own
  on public.role_analysis_versions for select to authenticated using (user_id = auth.uid());
create policy role_competencies_select_own
  on public.role_competencies for select to authenticated using (user_id = auth.uid());

revoke insert, update, delete on public.role_profiles from authenticated;
revoke insert, update, delete on public.role_analysis_versions from authenticated;
revoke insert, update, delete on public.role_competencies from authenticated;
grant select on public.role_profiles to authenticated;
grant select on public.role_analysis_versions to authenticated;
grant select on public.role_competencies to authenticated;
grant all on public.role_profiles to service_role;
grant all on public.role_analysis_versions to service_role;
grant all on public.role_competencies to service_role;

create or replace function public.complete_role_analysis(
  p_analysis_id uuid,
  p_user_id uuid,
  p_execution_id uuid,
  p_output jsonb
)
returns setof public.role_analysis_versions
language plpgsql
set search_path = public
as $$
declare
  target_profile_id uuid;
begin
  select role_profile_id into target_profile_id
  from public.role_analysis_versions
  where id = p_analysis_id and user_id = p_user_id and status = 'PROCESSING'
  for update;

  if target_profile_id is null then
    raise exception 'role analysis is not available for completion';
  end if;

  insert into public.role_competencies (
    role_profile_id, analysis_version_id, user_id, name, category,
    importance_weight, expected_level, source_type, source_reference, confidence
  )
  select
    target_profile_id,
    p_analysis_id,
    p_user_id,
    competency ->> 'name',
    (competency ->> 'category')::public.competency_category,
    (competency ->> 'importance_weight')::numeric,
    (competency ->> 'expected_level')::public.expected_competency_level,
    (competency ->> 'source_type')::public.competency_source_type,
    competency ->> 'source_reference',
    (competency ->> 'confidence')::numeric
  from jsonb_array_elements(coalesce(p_output -> 'competencies', '[]'::jsonb)) competency;

  update public.role_profiles
  set canonical_role = p_output ->> 'canonical_role',
      seniority = (p_output ->> 'seniority')::public.role_seniority,
      source_type = (
        select source_type from public.role_analysis_versions where id = p_analysis_id
      ),
      source_document_id = (
        select source_document_id from public.role_analysis_versions where id = p_analysis_id
      ),
      current_analysis_version_id = p_analysis_id,
      updated_at = now()
  where id = target_profile_id and user_id = p_user_id;

  update public.profiles
  set current_role_profile_id = target_profile_id, updated_at = now()
  where id = p_user_id;

  return query
  update public.role_analysis_versions
  set status = 'COMPLETED',
      output = p_output,
      execution_id = p_execution_id,
      completed_at = now()
  where id = p_analysis_id and user_id = p_user_id
  returning *;
end;
$$;

revoke all on function public.complete_role_analysis(uuid, uuid, uuid, jsonb)
  from public, anon, authenticated;
grant execute on function public.complete_role_analysis(uuid, uuid, uuid, jsonb)
  to service_role;

commit;

