begin;

create type public.interview_plan_status as enum ('PROCESSING', 'COMPLETED', 'FAILED');

create table public.interview_plans (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  version integer not null check (version > 0),
  status public.interview_plan_status not null default 'PROCESSING',
  plan_json jsonb,
  planner_model text not null,
  prompt_version text not null,
  planning_version text not null,
  execution_id uuid,
  error_type text,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  active boolean not null default false,
  unique (session_id, version),
  constraint interview_plans_state_valid check (
    (status = 'PROCESSING' and plan_json is null and completed_at is null and active = false)
    or (status = 'COMPLETED' and plan_json is not null and completed_at is not null)
    or (status = 'FAILED' and plan_json is null and completed_at is not null and active = false)
  ),
  constraint interview_plans_json_object check (
    plan_json is null or jsonb_typeof(plan_json) = 'object'
  )
);

create unique index interview_plans_one_processing_idx
  on public.interview_plans(session_id) where status = 'PROCESSING';
create unique index interview_plans_one_active_idx
  on public.interview_plans(session_id) where active = true;
create index interview_plans_owner_session_idx
  on public.interview_plans(user_id, session_id, version desc);

alter table public.interview_plans enable row level security;
create policy interview_plans_select_own
  on public.interview_plans for select to authenticated using (user_id = auth.uid());
revoke insert, update, delete on public.interview_plans from authenticated;
grant select on public.interview_plans to authenticated;
grant all on public.interview_plans to service_role;

create or replace function public.validate_interview_plan_owner()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.sessions
    where id = new.session_id and user_id = new.user_id
  ) then
    raise exception 'interview plan must belong to the session owner';
  end if;
  return new;
end;
$$;

create trigger interview_plans_validate_owner
  before insert or update on public.interview_plans
  for each row execute procedure public.validate_interview_plan_owner();

create or replace function public.begin_interview_plan(
  p_session_id uuid,
  p_user_id uuid,
  p_planner_model text,
  p_prompt_version text,
  p_planning_version text
)
returns setof public.interview_plans
language plpgsql
set search_path = public
as $$
declare
  next_version integer;
begin
  if not exists (
    select 1 from public.sessions
    where id = p_session_id
      and user_id = p_user_id
      and status in ('PREPARING', 'READY')
    for update
  ) then
    raise exception 'session is not available for planning';
  end if;

  return query select * from public.interview_plans
  where session_id = p_session_id and user_id = p_user_id and status = 'PROCESSING'
  limit 1;
  if found then
    return;
  end if;

  select coalesce(max(version), 0) + 1 into next_version
  from public.interview_plans where session_id = p_session_id;

  return query insert into public.interview_plans (
    session_id, user_id, version, planner_model, prompt_version, planning_version
  ) values (
    p_session_id, p_user_id, next_version, p_planner_model,
    p_prompt_version, p_planning_version
  ) returning *;
end;
$$;

create or replace function public.complete_interview_plan(
  p_plan_id uuid,
  p_user_id uuid,
  p_execution_id uuid,
  p_plan jsonb
)
returns setof public.interview_plans
language plpgsql
set search_path = public
as $$
declare
  target_session_id uuid;
begin
  select session_id into target_session_id
  from public.interview_plans
  where id = p_plan_id and user_id = p_user_id and status = 'PROCESSING'
  for update;
  if target_session_id is null then
    raise exception 'interview plan is not available for completion';
  end if;

  update public.interview_plans set active = false
  where session_id = target_session_id and active = true;

  return query update public.interview_plans
  set status = 'COMPLETED', plan_json = p_plan, execution_id = p_execution_id,
      completed_at = now(), active = true
  where id = p_plan_id and user_id = p_user_id
  returning *;
end;
$$;

revoke all on function public.begin_interview_plan(uuid, uuid, text, text, text)
  from public, anon, authenticated;
revoke all on function public.complete_interview_plan(uuid, uuid, uuid, jsonb)
  from public, anon, authenticated;
grant execute on function public.begin_interview_plan(uuid, uuid, text, text, text)
  to service_role;
grant execute on function public.complete_interview_plan(uuid, uuid, uuid, jsonb)
  to service_role;

commit;

