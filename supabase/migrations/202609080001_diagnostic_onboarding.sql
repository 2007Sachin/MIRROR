begin;

do $$
begin
  create type public.inquiry_depth as enum (
    'EVIDENCE_BEHIND_CLAIMS',
    'ROLE_KNOWLEDGE',
    'DECISION_QUALITY',
    'OWNERSHIP_IMPACT',
    'COMMUNICATION_UNDER_SCRUTINY',
    'COMPLETE_READINESS'
  );
exception when duplicate_object then null;
end;
$$;

alter table public.profiles
  add column if not exists target_company text,
  add column if not exists onboarding_step smallint not null default 1,
  add column if not exists onboarding_resume_document_id uuid references public.documents(id) on delete set null,
  add column if not exists onboarding_role_brief_document_id uuid references public.documents(id) on delete set null,
  add column if not exists onboarding_role_brief_skipped boolean not null default false,
  add column if not exists onboarding_role_profile_id uuid references public.role_profiles(id) on delete set null,
  add column if not exists onboarding_session_id uuid references public.sessions(id) on delete set null,
  add column if not exists inquiry_depth public.inquiry_depth[] not null default array['COMPLETE_READINESS']::public.inquiry_depth[];

alter table public.profiles
  drop constraint if exists profiles_target_company_length,
  add constraint profiles_target_company_length
    check (target_company is null or char_length(trim(target_company)) between 1 and 160),
  drop constraint if exists profiles_onboarding_step_range,
  add constraint profiles_onboarding_step_range check (onboarding_step between 1 and 5),
  drop constraint if exists profiles_inquiry_depth_valid,
  add constraint profiles_inquiry_depth_valid check (
    cardinality(inquiry_depth) between 1 and 5
    and (
      not ('COMPLETE_READINESS'::public.inquiry_depth = any(inquiry_depth))
      or cardinality(inquiry_depth) = 1
    )
  );

-- Preserve already-completed legacy profiles while requiring the real
-- diagnostic context for candidates who complete the redesigned flow.
alter table public.profiles
  drop constraint if exists profiles_onboarding_completion_required_fields;
alter table public.profiles
  add constraint profiles_onboarding_completion_required_fields
  check (
    not onboarding_completed
    or (
      career_stage is not null
      and career_intent is not null
      and target_role is not null
      and interview_timeline is not null
      and preferred_language is not null
    )
    or (
      target_role is not null
      and onboarding_step = 5
      and onboarding_resume_document_id is not null
      and onboarding_role_profile_id is not null
      and onboarding_session_id is not null
      and cardinality(inquiry_depth) > 0
    )
  );

create or replace function public.validate_onboarding_diagnostic_references()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if new.onboarding_resume_document_id is not null and not exists (
    select 1 from public.documents d
    where d.id = new.onboarding_resume_document_id
      and d.user_id = new.id
      and d.document_type = 'RESUME'
  ) then
    raise exception 'onboarding resume must belong to the profile owner';
  end if;

  if new.onboarding_role_brief_document_id is not null and not exists (
    select 1 from public.documents d
    where d.id = new.onboarding_role_brief_document_id
      and d.user_id = new.id
      and d.document_type = 'JOB_DESCRIPTION'
  ) then
    raise exception 'onboarding role brief must belong to the profile owner';
  end if;

  if new.onboarding_role_profile_id is not null and not exists (
    select 1 from public.role_profiles r
    where r.id = new.onboarding_role_profile_id and r.user_id = new.id
  ) then
    raise exception 'onboarding role profile must belong to the profile owner';
  end if;

  if new.onboarding_session_id is not null and not exists (
    select 1 from public.sessions s
    where s.id = new.onboarding_session_id and s.user_id = new.id
  ) then
    raise exception 'onboarding session must belong to the profile owner';
  end if;

  return new;
end;
$$;

drop trigger if exists profiles_validate_onboarding_diagnostic_references on public.profiles;
create trigger profiles_validate_onboarding_diagnostic_references
before insert or update of
  onboarding_resume_document_id,
  onboarding_role_brief_document_id,
  onboarding_role_profile_id,
  onboarding_session_id
on public.profiles
for each row execute function public.validate_onboarding_diagnostic_references();

create index if not exists profiles_onboarding_resume_document_idx
  on public.profiles(onboarding_resume_document_id);
create index if not exists profiles_onboarding_role_brief_document_idx
  on public.profiles(onboarding_role_brief_document_id);
create index if not exists profiles_onboarding_role_profile_idx
  on public.profiles(onboarding_role_profile_id);
create index if not exists profiles_onboarding_session_idx
  on public.profiles(onboarding_session_id);

revoke all on function public.validate_onboarding_diagnostic_references() from public, anon, authenticated;
grant execute on function public.validate_onboarding_diagnostic_references() to service_role;

commit;
