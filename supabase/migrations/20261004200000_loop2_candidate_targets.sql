-- Loop 2: a person's interview targets, pinned blueprints, target-session links and the
-- Mirror-written practice questions generated for them. Additive only: no existing table,
-- column, policy or grant is changed. Curated research is NOT stored here; it lives in the
-- versioned repo catalog (apps/api/app/research_content) and blueprints pin its version + hash.
-- Written only by the backend (service_role); people read their own rows. Applied locally only;
-- hosted apply is a separate owner-approved gate. Rollback script is kept outside migrations.
begin;

create table public.candidate_targets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  role_profile_id uuid not null references public.role_profiles(id) on delete cascade,
  company_label text not null check (char_length(trim(company_label)) between 1 and 120),
  company_key text null check (company_key is null or company_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  role_family_key text not null check (role_family_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  level_key text null check (level_key is null or level_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  level_label text null check (level_label is null or char_length(trim(level_label)) between 1 and 80),
  geography_key text null check (geography_key is null or geography_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  geography_label text null check (geography_label is null or char_length(trim(geography_label)) between 1 and 120),
  interview_date date null,
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'ARCHIVED')),
  archived_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint candidate_targets_archived_at check ((status = 'ARCHIVED') = (archived_at is not null))
);

create table public.interview_blueprints (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  candidate_target_id uuid not null references public.candidate_targets(id) on delete cascade,
  version integer not null check (version >= 1),
  catalog_version integer not null check (catalog_version >= 1),
  catalog_sha256 text not null check (catalog_sha256 ~ '^[0-9a-f]{64}$'),
  match_state text not null check (match_state in ('RESEARCHED', 'GENERAL_ONLY', 'NOT_RESEARCHED')),
  rules_version text not null check (char_length(trim(rules_version)) between 1 and 40),
  created_at timestamptz not null default now(),
  constraint interview_blueprints_one_version unique (candidate_target_id, version)
);

create table public.generated_questions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  candidate_target_id uuid not null references public.candidate_targets(id) on delete cascade,
  blueprint_id uuid null references public.interview_blueprints(id) on delete cascade,
  prompt_set_id uuid not null,
  position smallint not null check (position between 1 and 20),
  round_key text null check (round_key is null or round_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  competency_key text not null check (competency_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  family_key text not null check (family_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  template_id text not null check (char_length(trim(template_id)) between 1 and 80),
  generator_version text not null check (char_length(trim(generator_version)) between 1 and 40),
  originality_rules_version text not null check (char_length(trim(originality_rules_version)) between 1 and 40),
  question_text text not null check (char_length(trim(question_text)) between 20 and 400),
  rationale_code text not null check (rationale_code ~ '^[A-Z][A-Z0-9_]{0,62}$'),
  derived_from jsonb not null default '{}'::jsonb check (jsonb_typeof(derived_from) = 'object'),
  provenance_class text not null default 'MIRROR_GENERATED' check (provenance_class = 'MIRROR_GENERATED'),
  novelty_sha256 text not null check (novelty_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  -- A prompt never repeats inside one practice set (one session). Reuse across sessions is
  -- allowed once the prompt is outside the originality guard's 30-day repeat window.
  constraint generated_questions_novel_in_set unique (user_id, prompt_set_id, novelty_sha256),
  constraint generated_questions_one_position unique (prompt_set_id, position)
);

create table public.target_session_links (
  session_id uuid primary key references public.sessions(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  candidate_target_id uuid not null references public.candidate_targets(id) on delete cascade,
  blueprint_id uuid null references public.interview_blueprints(id) on delete cascade,
  round_key text null check (round_key is null or round_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  competency_key text null check (competency_key is null or competency_key ~ '^[a-z0-9][a-z0-9_]{0,62}$'),
  prompt_set_id uuid null,
  created_at timestamptz not null default now()
);

create index candidate_targets_owner_idx on public.candidate_targets(user_id, status, created_at desc);
create index candidate_targets_role_profile_idx on public.candidate_targets(role_profile_id);
-- One ACTIVE target per owner, role and scope; archive + recreate to change scope.
create unique index candidate_targets_one_active_scope_idx on public.candidate_targets (
  user_id, role_profile_id, coalesce(company_key, lower(company_label)), role_family_key,
  coalesce(level_key, ''), coalesce(geography_key, '')
) where status = 'ACTIVE';
create index interview_blueprints_owner_idx on public.interview_blueprints(user_id, candidate_target_id, version desc);
create index generated_questions_target_idx on public.generated_questions(candidate_target_id, created_at desc);
create index generated_questions_blueprint_idx on public.generated_questions(blueprint_id);
create index generated_questions_owner_idx on public.generated_questions(user_id);
create index target_session_links_owner_idx on public.target_session_links(user_id, candidate_target_id);
create index target_session_links_target_idx on public.target_session_links(candidate_target_id);
create index target_session_links_blueprint_idx on public.target_session_links(blueprint_id);

-- Targets: the role must be the owner's; scope never changes after insert (archive + recreate).
create or replace function public.candidate_targets_guard()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if tg_op = 'UPDATE' then
    if new.user_id is distinct from old.user_id
      or new.role_profile_id is distinct from old.role_profile_id
      or new.company_label is distinct from old.company_label
      or new.company_key is distinct from old.company_key
      or new.role_family_key is distinct from old.role_family_key
      or new.level_key is distinct from old.level_key
      or new.level_label is distinct from old.level_label
      or new.geography_key is distinct from old.geography_key
      or new.geography_label is distinct from old.geography_label
      or new.created_at is distinct from old.created_at then
      raise exception 'target scope is immutable';
    end if;
    if old.status = 'ARCHIVED' and new.status = 'ACTIVE' then
      raise exception 'an archived target cannot be reactivated';
    end if;
  end if;
  if not exists (select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id) then
    raise exception 'role does not belong to the target owner';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger candidate_targets_guard
  before insert or update on public.candidate_targets
  for each row execute function public.candidate_targets_guard();

-- Blueprints pin (catalog_version, catalog_sha256); a refresh is a new version row.
create or replace function public.interview_blueprints_guard()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if tg_op = 'UPDATE' then
    raise exception 'a blueprint pin is immutable';
  end if;
  if not exists (select 1 from public.candidate_targets where id = new.candidate_target_id and user_id = new.user_id) then
    raise exception 'target does not belong to the blueprint owner';
  end if;
  return new;
end;
$$;

create trigger interview_blueprints_guard
  before insert or update on public.interview_blueprints
  for each row execute function public.interview_blueprints_guard();

-- Generated questions are stored once, exactly as served, and never rewritten.
create or replace function public.generated_questions_guard()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if tg_op = 'UPDATE' then
    raise exception 'generated questions are immutable';
  end if;
  if not exists (select 1 from public.candidate_targets where id = new.candidate_target_id and user_id = new.user_id) then
    raise exception 'target does not belong to the question owner';
  end if;
  if new.blueprint_id is not null and not exists (
    select 1 from public.interview_blueprints
    where id = new.blueprint_id and user_id = new.user_id and candidate_target_id = new.candidate_target_id
  ) then
    raise exception 'blueprint does not belong to the question target';
  end if;
  return new;
end;
$$;

create trigger generated_questions_guard
  before insert or update on public.generated_questions
  for each row execute function public.generated_questions_guard();

-- Links: session, target, blueprint and prompt set must all be the owner's and agree.
create or replace function public.target_session_links_verify()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.sessions where id = new.session_id and user_id = new.user_id) then
    raise exception 'session does not belong to the link owner';
  end if;
  if not exists (select 1 from public.candidate_targets where id = new.candidate_target_id and user_id = new.user_id) then
    raise exception 'target does not belong to the link owner';
  end if;
  if new.blueprint_id is not null and not exists (
    select 1 from public.interview_blueprints
    where id = new.blueprint_id and user_id = new.user_id and candidate_target_id = new.candidate_target_id
  ) then
    raise exception 'blueprint does not belong to the link target';
  end if;
  if new.prompt_set_id is not null and not exists (
    select 1 from public.generated_questions
    where prompt_set_id = new.prompt_set_id and user_id = new.user_id and candidate_target_id = new.candidate_target_id
  ) then
    raise exception 'prompt set does not belong to the link target';
  end if;
  return new;
end;
$$;

create trigger target_session_links_verify
  before insert on public.target_session_links
  for each row execute function public.target_session_links_verify();

-- Switching or archiving a target can never rewrite which target a session practised for.
create or replace function public.target_session_links_write_once()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  raise exception 'a session link is write-once';
end;
$$;

create trigger target_session_links_write_once
  before update on public.target_session_links
  for each row execute function public.target_session_links_write_once();

revoke all on function public.candidate_targets_guard() from public, anon, authenticated;
revoke all on function public.interview_blueprints_guard() from public, anon, authenticated;
revoke all on function public.generated_questions_guard() from public, anon, authenticated;
revoke all on function public.target_session_links_verify() from public, anon, authenticated;
revoke all on function public.target_session_links_write_once() from public, anon, authenticated;

alter table public.candidate_targets enable row level security;
alter table public.interview_blueprints enable row level security;
alter table public.generated_questions enable row level security;
alter table public.target_session_links enable row level security;

create policy candidate_targets_select_own
  on public.candidate_targets for select to authenticated
  using (user_id = (select auth.uid()));
create policy interview_blueprints_select_own
  on public.interview_blueprints for select to authenticated
  using (user_id = (select auth.uid()));
create policy generated_questions_select_own
  on public.generated_questions for select to authenticated
  using (user_id = (select auth.uid()));
create policy target_session_links_select_own
  on public.target_session_links for select to authenticated
  using (user_id = (select auth.uid()));

-- Supabase default privileges grant ALL (incl. TRUNCATE/REFERENCES/TRIGGER) to anon and
-- authenticated on new tables: strip everything, then grant exactly SELECT.
revoke all on public.candidate_targets from public, anon, authenticated;
revoke all on public.interview_blueprints from public, anon, authenticated;
revoke all on public.generated_questions from public, anon, authenticated;
revoke all on public.target_session_links from public, anon, authenticated;
grant select on public.candidate_targets to authenticated;
grant select on public.interview_blueprints to authenticated;
grant select on public.generated_questions to authenticated;
grant select on public.target_session_links to authenticated;
grant all on public.candidate_targets to service_role;
grant all on public.interview_blueprints to service_role;
grant all on public.generated_questions to service_role;
grant all on public.target_session_links to service_role;

commit;
