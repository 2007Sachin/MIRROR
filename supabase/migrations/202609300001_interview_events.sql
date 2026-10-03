-- Interview tomorrow + Debrief (Phases 8-9): real interviews a person records for one of their
-- roles, and what they report afterwards. Additive. Written only by the backend (service_role);
-- people read their own rows. Debriefs are candidate-reported and hold no judgement.
begin;

create type public.interview_round_kind as enum ('SCREENING', 'TECHNICAL', 'BEHAVIOURAL', 'HR', 'OTHER');
create type public.interview_feeling as enum ('WENT_WELL', 'MIXED', 'WENT_BADLY');
create type public.interview_outcome as enum ('WAITING', 'NEXT_ROUND', 'OFFER', 'NOT_SELECTED', 'WITHDREW');

create table public.interview_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  role_profile_id uuid not null references public.role_profiles(id) on delete cascade,
  scheduled_for timestamptz not null,
  round_kind public.interview_round_kind not null default 'OTHER',
  company_label text null check (company_label is null or char_length(company_label) <= 120),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index interview_events_user_role_idx on public.interview_events(user_id, role_profile_id, scheduled_for);
create index interview_events_role_profile_idx on public.interview_events(role_profile_id);

-- Each reported question is 1..500 characters. A function because a check cannot hold a subquery.
create or replace function public.interview_questions_valid(questions text[])
returns boolean
language sql
immutable
set search_path = public
as $$
  select coalesce(bool_and(char_length(q) between 1 and 500), true) from unnest(questions) as q;
$$;

create table public.interview_debriefs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  interview_event_id uuid not null references public.interview_events(id) on delete cascade,
  questions_asked text[] not null default '{}'
    check (cardinality(questions_asked) <= 15 and public.interview_questions_valid(questions_asked)),
  feeling public.interview_feeling null,
  outcome public.interview_outcome not null default 'WAITING',
  notes text null check (notes is null or char_length(notes) <= 2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (interview_event_id)
);

create index interview_debriefs_user_idx on public.interview_debriefs(user_id);

create or replace function public.interview_events_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id) then
    raise exception 'role profile does not belong to the interview owner';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger interview_events_verify_ownership
  before insert or update on public.interview_events
  for each row execute function public.interview_events_verify_ownership();

create or replace function public.interview_debriefs_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.interview_events where id = new.interview_event_id and user_id = new.user_id) then
    raise exception 'interview does not belong to the debrief owner';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger interview_debriefs_verify_ownership
  before insert or update on public.interview_debriefs
  for each row execute function public.interview_debriefs_verify_ownership();

alter table public.interview_events enable row level security;
alter table public.interview_debriefs enable row level security;

create policy interview_events_select_own
  on public.interview_events for select to authenticated
  using (user_id = (select auth.uid()));

create policy interview_debriefs_select_own
  on public.interview_debriefs for select to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.interview_events, public.interview_debriefs from anon;
revoke insert, update, delete on public.interview_events, public.interview_debriefs from authenticated;
grant select on public.interview_events, public.interview_debriefs to authenticated;
grant all on public.interview_events, public.interview_debriefs to service_role;

commit;
