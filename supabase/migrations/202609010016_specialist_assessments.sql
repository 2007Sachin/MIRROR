begin;

create type public.specialist_assessor_type as enum ('TECHNICAL','BEHAVIOUR','CLAIMS');
create type public.specialist_assessment_status as enum ('COMPLETE','NOT_ENOUGH_SIGNAL');

create table public.specialist_assessments (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  assessor_type public.specialist_assessor_type not null,
  status public.specialist_assessment_status not null,
  result_json jsonb not null,
  model text not null,
  model_version text not null,
  prompt_version text not null,
  rubric_version text not null,
  created_at timestamptz not null default now(),
  constraint specialist_assessments_result_object check (jsonb_typeof(result_json)='object')
);

create index specialist_assessments_session_history_idx
  on public.specialist_assessments(session_id, assessor_type, created_at desc);
alter table public.specialist_assessments enable row level security;
-- Results are internal until the report milestone. No candidate policy exists.
revoke all on public.specialist_assessments from anon, authenticated;
grant all on public.specialist_assessments to service_role;

commit;

