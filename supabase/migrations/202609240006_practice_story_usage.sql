-- My Stories: which practice sessions actually used a story, and which version of it.
-- Additive. A row exists only when the candidate chose the story for a practice and the
-- practice plan was built from it; relevance on the Interview Map never creates one.
-- Rows are history: they point at the exact story version practised and are never rewritten,
-- so later edits, archiving or restoring the story leave them as they were.
-- Nothing is backfilled: earlier sessions never recorded a story, so there is nothing to recover.
begin;

create table public.practice_story_usages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  session_id uuid not null references public.sessions(id) on delete cascade,
  story_id uuid not null references public.stories(id) on delete cascade,
  story_version_id uuid not null references public.story_versions(id) on delete cascade,
  role_profile_id uuid references public.role_profiles(id) on delete set null,
  position smallint not null check (position between 1 and 4),
  created_at timestamptz not null default now(),
  unique (session_id, story_id),
  unique (session_id, position)
);

create index practice_story_usages_owner_idx on public.practice_story_usages(user_id, created_at desc);
create index practice_story_usages_story_idx on public.practice_story_usages(story_id, created_at desc);
create index practice_story_usages_version_idx on public.practice_story_usages(story_version_id);
create index practice_story_usages_role_profile_idx on public.practice_story_usages(role_profile_id);

-- Session, story, version and role must all belong to the same person, the version must be a
-- version of that story, the role must be the session's own role, and an archived story
-- cannot be newly chosen.
create or replace function public.practice_story_usages_verify()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  session_role uuid;
begin
  select role_profile_id into session_role from public.sessions
  where id = new.session_id and user_id = new.user_id;
  if not found then
    raise exception 'session does not belong to the usage owner';
  end if;
  if not exists (
    select 1 from public.stories
    where id = new.story_id and user_id = new.user_id and archived_at is null
  ) then
    raise exception 'story does not belong to the usage owner or is archived';
  end if;
  if not exists (
    select 1 from public.story_versions
    where id = new.story_version_id and story_id = new.story_id and user_id = new.user_id
  ) then
    raise exception 'version does not belong to this story';
  end if;
  if new.role_profile_id is distinct from session_role then
    raise exception 'role must be the session role';
  end if;
  if new.role_profile_id is not null and not exists (
    select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id
  ) then
    raise exception 'role profile does not belong to the usage owner';
  end if;
  return new;
end;
$$;

create trigger practice_story_usages_verify
  before insert on public.practice_story_usages
  for each row execute function public.practice_story_usages_verify();

-- Usage is history. The only change allowed is the role reference clearing when that role
-- profile itself is removed (on delete set null), so account deletion still cascades.
create or replace function public.practice_story_usages_keep_history()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.role_profile_id is null
    and (new.id, new.user_id, new.session_id, new.story_id, new.story_version_id, new.position, new.created_at)
      is not distinct from
        (old.id, old.user_id, old.session_id, old.story_id, old.story_version_id, old.position, old.created_at) then
    return new;
  end if;
  raise exception 'practice story usage is immutable history';
end;
$$;

create trigger practice_story_usages_keep_history
  before update on public.practice_story_usages
  for each row execute function public.practice_story_usages_keep_history();

alter table public.practice_story_usages enable row level security;

create policy practice_story_usages_select_own
  on public.practice_story_usages for select to authenticated
  using (user_id = (select auth.uid()));

revoke insert, update, delete on public.practice_story_usages from authenticated;
grant select on public.practice_story_usages to authenticated;
grant all on public.practice_story_usages to service_role;

commit;
