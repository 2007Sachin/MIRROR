begin;

do $$
begin
  create type public.career_stage as enum (
    'STUDENT',
    'FINAL_YEAR_STUDENT',
    'FRESHER',
    'EARLY_CAREER',
    'EXPERIENCED'
  );
exception when duplicate_object then null;
end;
$$;

do $$
begin
  create type public.career_intent as enum (
    'CAMPUS_PLACEMENT',
    'INTERNSHIP',
    'FIRST_JOB',
    'JOB_SWITCH',
    'SPECIFIC_COMPANY',
    'EXPLORING'
  );
exception when duplicate_object then null;
end;
$$;

do $$
begin
  create type public.interview_timeline as enum (
    'TODAY',
    'THIS_WEEK',
    'THIS_MONTH',
    'LATER',
    'EXPLORING'
  );
exception when duplicate_object then null;
end;
$$;

do $$
begin
  create type public.preferred_language as enum (
    'ENGLISH',
    'HINDI',
    'KANNADA',
    'TAMIL',
    'TELUGU'
  );
exception when duplicate_object then null;
end;
$$;

alter table public.profiles
  add column if not exists career_stage public.career_stage,
  add column if not exists career_intent public.career_intent,
  add column if not exists target_role text,
  add column if not exists interview_timeline public.interview_timeline,
  add column if not exists preferred_language public.preferred_language,
  add column if not exists college_id uuid references public.colleges(id) on delete set null,
  add column if not exists onboarding_completed boolean not null default false;

alter table public.profiles
  drop constraint if exists profiles_target_role_length;
alter table public.profiles
  add constraint profiles_target_role_length
  check (target_role is null or char_length(trim(target_role)) between 2 and 160);

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
  );

-- All onboarding writes go through the authenticated API. The service role
-- already has table access; browser clients retain only the full_name update
-- grant from the authentication migration.

commit;

