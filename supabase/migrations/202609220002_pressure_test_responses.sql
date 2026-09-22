-- Resume Pressure Test: how ready someone says they are to explain each resume statement.
-- Additive. One row per person per statement; the statement itself stays in public.claims.
begin;

create type public.pressure_readiness as enum ('CAN_EXPLAIN', 'NEEDS_PREPARATION');

create table public.pressure_test_responses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  claim_id uuid not null references public.claims(id) on delete cascade,
  readiness public.pressure_readiness not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, claim_id)
);

create index pressure_test_responses_claim_idx on public.pressure_test_responses(claim_id);

create or replace function public.pressure_test_responses_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.claims where id = new.claim_id and user_id = new.user_id) then
    raise exception 'claim does not belong to the responder';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger pressure_test_responses_verify_ownership
  before insert or update on public.pressure_test_responses
  for each row execute function public.pressure_test_responses_verify_ownership();

alter table public.pressure_test_responses enable row level security;

create policy pressure_test_responses_select_own
  on public.pressure_test_responses for select to authenticated
  using (user_id = (select auth.uid()));

revoke insert, update, delete on public.pressure_test_responses from authenticated;
grant select on public.pressure_test_responses to authenticated;
grant all on public.pressure_test_responses to service_role;

commit;
