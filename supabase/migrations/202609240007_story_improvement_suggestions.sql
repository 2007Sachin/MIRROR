-- My Stories: Review may suggest improving a story; only the candidate edits it.
-- Additive. A suggestion exists only when an answer about a story the candidate chose to practise
-- (practice_story_usages) received a grounded Skeptic observation that maps to one story part.
-- It points at the exact version practised and never changes the story. Accepting one records the
-- new version the candidate saved; dismissing keeps it as history. Nothing is backfilled.
begin;

create table public.story_improvement_suggestions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  session_id uuid not null references public.sessions(id) on delete cascade,
  usage_id uuid not null references public.practice_story_usages(id) on delete cascade,
  story_id uuid not null references public.stories(id) on delete cascade,
  story_version_id uuid not null references public.story_versions(id) on delete cascade,
  role_profile_id uuid references public.role_profiles(id) on delete set null,
  source_turn_id uuid not null references public.turns(id) on delete cascade,
  source_observation_id uuid not null references public.skeptic_observations(id) on delete cascade,
  issue_type text not null check (issue_type in ('OWNERSHIP_UNCLEAR', 'RESULT_UNSUPPORTED')),
  story_part text not null check (story_part in ('ownership', 'measurable_result')),
  status text not null default 'OPEN' check (status in ('OPEN', 'ACCEPTED', 'DISMISSED')),
  resolved_by_story_version_id uuid references public.story_versions(id) on delete set null,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  unique (session_id, source_turn_id, issue_type),
  constraint story_improvement_suggestions_issue_part check (
    (issue_type = 'OWNERSHIP_UNCLEAR' and story_part = 'ownership')
    or (issue_type = 'RESULT_UNSUPPORTED' and story_part = 'measurable_result')
  ),
  constraint story_improvement_suggestions_resolution check (
    (status = 'OPEN') = (resolved_at is null)
    and (status <> 'DISMISSED' or resolved_by_story_version_id is null)
  )
);

create index story_improvement_suggestions_owner_idx on public.story_improvement_suggestions(user_id, status);
create index story_improvement_suggestions_story_idx on public.story_improvement_suggestions(story_id, created_at desc);
create index story_improvement_suggestions_usage_idx on public.story_improvement_suggestions(usage_id);
create index story_improvement_suggestions_version_idx on public.story_improvement_suggestions(story_version_id);
create index story_improvement_suggestions_resolved_version_idx on public.story_improvement_suggestions(resolved_by_story_version_id);
create index story_improvement_suggestions_role_profile_idx on public.story_improvement_suggestions(role_profile_id);
create index story_improvement_suggestions_turn_idx on public.story_improvement_suggestions(source_turn_id);
create index story_improvement_suggestions_observation_idx on public.story_improvement_suggestions(source_observation_id);

-- Every link must agree: the usage is this person's use of this story, at this version, in this
-- session, for this role; the answer is a candidate turn of that session; the observation is about
-- that answer. Nothing can be pointed at someone else's records.
create or replace function public.story_improvement_suggestions_verify()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.practice_story_usages u
    where u.id = new.usage_id and u.user_id = new.user_id and u.session_id = new.session_id
      and u.story_id = new.story_id and u.story_version_id = new.story_version_id
      and u.role_profile_id is not distinct from new.role_profile_id
  ) then
    raise exception 'suggestion does not match the practice usage';
  end if;
  if not exists (
    select 1 from public.turns t join public.sessions s on s.id = t.session_id
    where t.id = new.source_turn_id and t.session_id = new.session_id
      and s.user_id = new.user_id and t.speaker = 'candidate'
  ) then
    raise exception 'answer does not belong to this session';
  end if;
  if not exists (
    select 1 from public.skeptic_observations o
    where o.id = new.source_observation_id and o.user_id = new.user_id
      and o.session_id = new.session_id and o.source_turn_id = new.source_turn_id
  ) then
    raise exception 'observation does not belong to this answer';
  end if;
  return new;
end;
$$;

create trigger story_improvement_suggestions_verify
  before insert on public.story_improvement_suggestions
  for each row execute function public.story_improvement_suggestions_verify();

-- A suggestion's source never changes. Its status moves once, from OPEN, and an accepted one must
-- name a later version of the same story.
create or replace function public.story_improvement_suggestions_transition()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if (new.id, new.user_id, new.session_id, new.usage_id, new.story_id, new.story_version_id,
      new.source_turn_id, new.source_observation_id, new.issue_type, new.story_part, new.created_at)
    is distinct from
     (old.id, old.user_id, old.session_id, old.usage_id, old.story_id, old.story_version_id,
      old.source_turn_id, old.source_observation_id, old.issue_type, old.story_part, old.created_at) then
    raise exception 'a suggestion''s source cannot change';
  end if;
  if new.status is distinct from old.status and old.status <> 'OPEN' then
    raise exception 'only an open suggestion can be accepted or dismissed';
  end if;
  if new.status = 'ACCEPTED' and old.status = 'OPEN' and not exists (
    select 1 from public.story_versions later
    join public.story_versions practised on practised.id = new.story_version_id
    where later.id = new.resolved_by_story_version_id and later.story_id = new.story_id
      and later.user_id = new.user_id and later.version > practised.version
  ) then
    raise exception 'an accepted suggestion needs a later version of the same story';
  end if;
  return new;
end;
$$;

create trigger story_improvement_suggestions_transition
  before update on public.story_improvement_suggestions
  for each row execute function public.story_improvement_suggestions_transition();

alter table public.story_improvement_suggestions enable row level security;

create policy story_improvement_suggestions_select_own
  on public.story_improvement_suggestions for select to authenticated
  using (user_id = (select auth.uid()));

revoke insert, update, delete on public.story_improvement_suggestions from authenticated;
grant select on public.story_improvement_suggestions to authenticated;
grant all on public.story_improvement_suggestions to service_role;

commit;
