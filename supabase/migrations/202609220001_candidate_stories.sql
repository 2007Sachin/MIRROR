-- My Stories: how a candidate explains a real experience in an interview.
-- Additive. Stories point at experience (documents, resume claims, roles); they never
-- replace it, and removing a story never touches the experience it came from.
begin;

create type public.story_origin as enum ('MANUAL', 'PRESSURE_TEST', 'FIND_A_STORY', 'EXPERIENCE');

create table public.stories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null,
  themes text[] not null default '{}',
  role_profile_id uuid references public.role_profiles(id) on delete set null,
  source_claim_id uuid references public.claims(id) on delete set null,
  source_document_id uuid references public.documents(id) on delete set null,
  source_text text,
  origin public.story_origin not null default 'MANUAL',
  situation text,
  ownership text,
  actions text,
  reasoning text,
  trade_offs text,
  outcome text,
  measurable_result text,
  learning text,
  do_differently text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint stories_title_length check (char_length(trim(title)) between 2 and 200),
  constraint stories_theme_count check (coalesce(array_length(themes, 1), 0) <= 12)
);

create index stories_owner_idx on public.stories(user_id, updated_at desc);
create index stories_role_profile_idx on public.stories(role_profile_id);
create index stories_source_claim_idx on public.stories(source_claim_id);
create index stories_source_document_idx on public.stories(source_document_id);

-- A story may only point at records the same person owns.
create or replace function public.stories_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.role_profile_id is not null and not exists (
    select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id
  ) then
    raise exception 'role profile does not belong to the story owner';
  end if;
  if new.source_claim_id is not null and not exists (
    select 1 from public.claims where id = new.source_claim_id and user_id = new.user_id
  ) then
    raise exception 'claim does not belong to the story owner';
  end if;
  if new.source_document_id is not null and not exists (
    select 1 from public.documents where id = new.source_document_id and user_id = new.user_id
  ) then
    raise exception 'document does not belong to the story owner';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger stories_verify_ownership
  before insert or update on public.stories
  for each row execute function public.stories_verify_ownership();

alter table public.stories enable row level security;

create policy stories_select_own
  on public.stories for select to authenticated
  using (user_id = (select auth.uid()));

revoke insert, update, delete on public.stories from authenticated;
grant select on public.stories to authenticated;
grant all on public.stories to service_role;

commit;
