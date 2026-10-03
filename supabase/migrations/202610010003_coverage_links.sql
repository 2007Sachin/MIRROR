-- My plan coverage links: the person's own choice about which approved example or story
-- speaks to one role need. Additive. A confirmed link always counts in the plan and cites
-- why it exists; a dismissed one never shows. Word matching only suggests and is never stored.
-- Written only by the backend (service_role); people read their own rows.
begin;

create table public.coverage_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  role_profile_id uuid not null references public.role_profiles(id) on delete cascade,
  requirement_key text not null check (char_length(requirement_key) between 1 and 80),
  evidence_item_id uuid null references public.evidence_items(id) on delete cascade,
  story_id uuid null references public.stories(id) on delete cascade,
  reason text null check (reason is null or reason in ('TOOL', 'OUTCOME', 'DECISION', 'CAPABILITY', 'CONFIRMED')),
  confirmed boolean not null default false,
  dismissed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint coverage_links_one_target check (num_nonnulls(evidence_item_id, story_id) = 1),
  constraint coverage_links_not_both check (not (confirmed and dismissed)),
  constraint coverage_links_confirmed_cites_reason check (not confirmed or reason is not null),
  constraint coverage_links_one_per_item unique (user_id, role_profile_id, requirement_key, evidence_item_id),
  constraint coverage_links_one_per_story unique (user_id, role_profile_id, requirement_key, story_id)
);

create index coverage_links_role_profile_idx on public.coverage_links(role_profile_id);
create index coverage_links_evidence_item_idx on public.coverage_links(evidence_item_id);
create index coverage_links_story_idx on public.coverage_links(story_id);

-- The role, the item and the story must all belong to the link's owner. Exact ids only.
create or replace function public.coverage_links_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id) then
    raise exception 'role does not belong to the link owner';
  end if;
  if new.evidence_item_id is not null
    and not exists (select 1 from public.evidence_items where id = new.evidence_item_id and user_id = new.user_id) then
    raise exception 'item does not belong to the link owner';
  end if;
  if new.story_id is not null
    and not exists (select 1 from public.stories where id = new.story_id and user_id = new.user_id) then
    raise exception 'story does not belong to the link owner';
  end if;
  if tg_op = 'UPDATE' and new.user_id is distinct from old.user_id then
    raise exception 'a link cannot move to another owner';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger coverage_links_verify_ownership
  before insert or update on public.coverage_links
  for each row execute function public.coverage_links_verify_ownership();

alter table public.coverage_links enable row level security;

create policy coverage_links_select_own
  on public.coverage_links for select to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.coverage_links from anon;
revoke insert, update, delete on public.coverage_links from authenticated;
grant select on public.coverage_links to authenticated;
grant all on public.coverage_links to service_role;

commit;
