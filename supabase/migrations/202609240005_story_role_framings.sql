-- My Stories: one story, useful for zero, one or many roles.
-- Additive. A framing records that a story is useful for one exact role profile, the extra
-- themes it shows for that role, and an optional note on what to emphasise. It never copies
-- the story's content: the facts stay on public.stories and in public.story_versions.
-- stories.role_profile_id stays as provenance: the role a story was first written for.
begin;

create table public.story_role_framings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  story_id uuid not null references public.stories(id) on delete cascade,
  role_profile_id uuid not null references public.role_profiles(id) on delete cascade,
  themes text[] not null default '{}',
  emphasis text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (story_id, role_profile_id),
  constraint story_role_framings_theme_count check (coalesce(array_length(themes, 1), 0) <= 12),
  constraint story_role_framings_emphasis_length check (emphasis is null or char_length(emphasis) between 1 and 500)
);

create index story_role_framings_owner_role_idx on public.story_role_framings(user_id, role_profile_id);
create index story_role_framings_role_profile_idx on public.story_role_framings(role_profile_id);

-- The story and the role must both belong to the framing's owner. Exact ids only.
create or replace function public.story_role_framings_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.stories where id = new.story_id and user_id = new.user_id) then
    raise exception 'story does not belong to the framing owner';
  end if;
  if not exists (select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id) then
    raise exception 'role profile does not belong to the framing owner';
  end if;
  if tg_op = 'UPDATE' and (
    new.story_id is distinct from old.story_id
    or new.role_profile_id is distinct from old.role_profile_id
    or new.user_id is distinct from old.user_id
  ) then
    raise exception 'a framing cannot move to another story or role';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger story_role_framings_verify_ownership
  before insert or update on public.story_role_framings
  for each row execute function public.story_role_framings_verify_ownership();

-- Existing stories written for a role keep that role, archived or not.
insert into public.story_role_framings (user_id, story_id, role_profile_id, created_at, updated_at)
select s.user_id, s.id, s.role_profile_id, s.created_at, s.created_at
from public.stories s
join public.role_profiles r on r.id = s.role_profile_id and r.user_id = s.user_id
where s.role_profile_id is not null
on conflict (story_id, role_profile_id) do nothing;

-- A story written for a role (Dig Deeper, "Help me find a story") is useful for that role
-- from the start, in the same transaction as the story itself.
create or replace function public.stories_frame_originating_role()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.role_profile_id is not null then
    insert into public.story_role_framings (user_id, story_id, role_profile_id)
    values (new.user_id, new.id, new.role_profile_id)
    on conflict (story_id, role_profile_id) do nothing;
  end if;
  return null;
end;
$$;

create trigger stories_frame_originating_role
  after insert on public.stories
  for each row execute function public.stories_frame_originating_role();

alter table public.story_role_framings enable row level security;

create policy story_role_framings_select_own
  on public.story_role_framings for select to authenticated
  using (user_id = (select auth.uid()));

revoke insert, update, delete on public.story_role_framings from authenticated;
grant select on public.story_role_framings to authenticated;
grant all on public.story_role_framings to service_role;

commit;
