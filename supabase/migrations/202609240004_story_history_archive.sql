-- My Stories: version history and archive.
-- Additive. public.stories stays the canonical story (stable id, owner, provenance, latest
-- content). Every saved change to a story's content is also written here as a numbered,
-- read-only version, inside the same transaction as the change. Archiving hides a story
-- from current preparation without removing it or its history.
begin;

create type public.story_change_reason as enum ('CREATED', 'MANUAL_EDIT', 'RESTORED');

alter table public.stories
  add column archived_at timestamptz,
  add column current_version integer not null default 1,
  add constraint stories_current_version_positive check (current_version >= 1);

create table public.story_versions (
  id uuid primary key default gen_random_uuid(),
  story_id uuid not null references public.stories(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  version integer not null check (version >= 1),
  title text not null,
  themes text[] not null default '{}',
  situation text,
  ownership text,
  actions text,
  reasoning text,
  trade_offs text,
  outcome text,
  measurable_result text,
  learning text,
  do_differently text,
  change_reason public.story_change_reason not null,
  restored_from_version integer check (restored_from_version >= 1),
  created_at timestamptz not null default now(),
  unique (story_id, version),
  constraint story_versions_restore_source check (
    (change_reason = 'RESTORED') = (restored_from_version is not null)
  )
);

create index story_versions_user_idx on public.story_versions(user_id);

-- A version may only belong to a story the same person owns.
create or replace function public.story_versions_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.stories where id = new.story_id and user_id = new.user_id) then
    raise exception 'story does not belong to the version owner';
  end if;
  return new;
end;
$$;

create trigger story_versions_verify_ownership
  before insert on public.story_versions
  for each row execute function public.story_versions_verify_ownership();

-- Versions are history: once written, they are never rewritten.
create or replace function public.story_versions_keep_history()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  raise exception 'story versions are immutable history';
end;
$$;

create trigger story_versions_keep_history
  before update on public.story_versions
  for each row execute function public.story_versions_keep_history();

-- Existing stories: their current content becomes version 1, dated at their last save.
-- Nothing about the story itself changes.
insert into public.story_versions (
  story_id, user_id, version, title, themes, situation, ownership, actions, reasoning,
  trade_offs, outcome, measurable_result, learning, do_differently, change_reason, created_at
)
select
  s.id, s.user_id, 1, s.title, s.themes, s.situation, s.ownership, s.actions, s.reasoning,
  s.trade_offs, s.outcome, s.measurable_result, s.learning, s.do_differently, 'CREATED', s.updated_at
from public.stories s
where not exists (select 1 from public.story_versions v where v.story_id = s.id);

-- The version number moves only when the story's content changes. Saving the same
-- content, archiving, restoring or changing the role does not create a version.
create or replace function public.stories_track_version()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if tg_op = 'INSERT' then
    new.current_version := 1;
  elsif (
    new.title, new.themes, new.situation, new.ownership, new.actions, new.reasoning,
    new.trade_offs, new.outcome, new.measurable_result, new.learning, new.do_differently
  ) is distinct from (
    old.title, old.themes, old.situation, old.ownership, old.actions, old.reasoning,
    old.trade_offs, old.outcome, old.measurable_result, old.learning, old.do_differently
  ) then
    new.current_version := old.current_version + 1;
  else
    new.current_version := old.current_version;
  end if;
  return new;
end;
$$;

create trigger stories_track_version
  before insert or update on public.stories
  for each row execute function public.stories_track_version();

-- Writes the version row in the same transaction as the story change.
-- restore_story_version() marks its update so the version records where it came from.
create or replace function public.stories_record_version()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  reason public.story_change_reason;
  restored_from integer;
begin
  if tg_op = 'UPDATE' and new.current_version = old.current_version then
    return null;
  end if;
  restored_from := nullif(current_setting('mirror.story_restored_from', true), '')::integer;
  reason := case
    when tg_op = 'INSERT' then 'CREATED'
    when restored_from is not null then 'RESTORED'
    else 'MANUAL_EDIT'
  end;
  if reason <> 'RESTORED' then
    restored_from := null;
  end if;
  insert into public.story_versions (
    story_id, user_id, version, title, themes, situation, ownership, actions, reasoning,
    trade_offs, outcome, measurable_result, learning, do_differently, change_reason,
    restored_from_version
  ) values (
    new.id, new.user_id, new.current_version, new.title, new.themes, new.situation,
    new.ownership, new.actions, new.reasoning, new.trade_offs, new.outcome,
    new.measurable_result, new.learning, new.do_differently, reason, restored_from
  );
  return null;
end;
$$;

create trigger stories_record_version
  after insert or update on public.stories
  for each row execute function public.stories_record_version();

-- Bringing back an earlier version: its content becomes a new current version.
-- Only an active story the caller owns, and only a version of that same story.
create or replace function public.restore_story_version(
  p_story_id uuid,
  p_user_id uuid,
  p_version_id uuid
)
returns setof public.stories
language plpgsql
set search_path = public
as $$
declare
  source public.story_versions%rowtype;
begin
  perform 1 from public.stories
  where id = p_story_id and user_id = p_user_id and archived_at is null
  for update;
  if not found then
    raise exception 'story not found';
  end if;
  select * into source from public.story_versions
  where id = p_version_id and story_id = p_story_id and user_id = p_user_id;
  if not found then
    raise exception 'version not found';
  end if;
  perform set_config('mirror.story_restored_from', source.version::text, true);
  update public.stories set
    title = source.title,
    themes = source.themes,
    situation = source.situation,
    ownership = source.ownership,
    actions = source.actions,
    reasoning = source.reasoning,
    trade_offs = source.trade_offs,
    outcome = source.outcome,
    measurable_result = source.measurable_result,
    learning = source.learning,
    do_differently = source.do_differently
  where id = p_story_id and user_id = p_user_id;
  perform set_config('mirror.story_restored_from', '', true);
  return query select * from public.stories where id = p_story_id and user_id = p_user_id;
end;
$$;

alter table public.story_versions enable row level security;

create policy story_versions_select_own
  on public.story_versions for select to authenticated
  using (user_id = (select auth.uid()));

revoke insert, update, delete on public.story_versions from authenticated;
grant select on public.story_versions to authenticated;
grant all on public.story_versions to service_role;

revoke all on function public.restore_story_version(uuid, uuid, uuid) from public, anon, authenticated;
grant execute on function public.restore_story_version(uuid, uuid, uuid) to service_role;

commit;
