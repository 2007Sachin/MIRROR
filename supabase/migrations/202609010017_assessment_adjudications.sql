begin;
create table public.assessment_adjudications (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  affected_dimension text not null,
  specialist_inputs jsonb not null,
  final_decision jsonb not null,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  model text not null,
  prompt_version text not null,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(specialist_inputs)='object' and jsonb_typeof(final_decision)='object')
);
create index assessment_adjudications_session_idx on public.assessment_adjudications(session_id, created_at desc);
alter table public.assessment_adjudications enable row level security;
revoke all on public.assessment_adjudications from anon, authenticated;
grant all on public.assessment_adjudications to service_role;
commit;

