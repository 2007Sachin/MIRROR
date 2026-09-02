begin;

create extension if not exists pgcrypto;

create type public.session_status as enum ('draft','prepared','in_progress','processing','complete','failed');
create type public.interview_phase as enum ('INTRO','BACKGROUND','PROJECTS','ROLE_CORE','DEEP_DIVE','BEHAVIOURAL','CLOSING','COMPLETE');
create type public.turn_speaker as enum ('candidate','interviewer');
create type public.turn_type as enum ('planned','depth_probe','contradiction_probe','ladder_up','ladder_down','recovery','transition','closing');
create type public.claim_type as enum ('skill','project','scale','ownership','tool','outcome','experience','responsibility');
create type public.claim_source as enum ('resume','jd','spoken','project');
create type public.claim_status as enum ('unverified','corroborated','contradicted','walked_back');
create type public.flag_type as enum ('contradiction','vagueness','unsupported_scale','ownership_drift');
create type public.round_type as enum ('screening','technical','managerial','hr');
create type public.rubric_status as enum ('draft','active','contested');
create type public.rubric_source as enum ('synthetic-draft','expert','validated');
create type public.score_status as enum ('scored','not_enough_signal');
create type public.job_status as enum ('pending','running','complete','failed');
create type public.skeptic_mode as enum ('shadow','active');

create table public.colleges (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  email text,
  college_id uuid references public.colleges(id) on delete set null,
  role text not null default 'candidate' check (role in ('candidate','admin','tpo')),
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.users (id, full_name, email)
  values (new.id, new.raw_user_meta_data ->> 'full_name', new.email)
  on conflict (id) do update set email = excluded.email;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert or update of email on auth.users
  for each row execute procedure public.handle_new_user();

create table public.roles (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  created_at timestamptz not null default now()
);

create table public.skills (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  created_at timestamptz not null default now()
);

create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  target_role text not null,
  resume_url text,
  jd_text text not null default '',
  status public.session_status not null default 'draft',
  phase public.interview_phase not null default 'INTRO',
  question_plan jsonb,
  completion_pct numeric(5,2) not null default 0 check (completion_pct between 0 and 100),
  synthetic boolean not null default false,
  skeptic_mode public.skeptic_mode not null default 'shadow',
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.turns (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  turn_index integer not null check (turn_index >= 0),
  speaker public.turn_speaker not null,
  text text not null,
  audio_url text,
  duration_ms integer check (duration_ms is null or duration_ms >= 0),
  silence_before_ms integer check (silence_before_ms is null or silence_before_ms >= 0),
  turn_type public.turn_type not null,
  phase public.interview_phase not null,
  parent_question_id uuid references public.turns(id) on delete set null,
  created_at timestamptz not null default now(),
  unique(session_id, turn_index, speaker)
);

create table public.claims (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  claim_text text not null,
  claim_type public.claim_type not null,
  source public.claim_source not null,
  source_ref text,
  status public.claim_status not null default 'unverified',
  contradicted_by_turn_id uuid references public.turns(id) on delete set null,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  synthetic boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.flags (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  claim_id uuid references public.claims(id) on delete set null,
  flag_type public.flag_type not null,
  severity integer not null check (severity between 1 and 3),
  suggested_probe text not null,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  distinction text not null,
  consumed boolean not null default false,
  detected_at_turn integer not null check (detected_at_turn >= 0),
  disputed boolean not null default false,
  dispute_reason text,
  created_at timestamptz not null default now()
);

create table public.rubrics (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid not null references public.skills(id) on delete restrict,
  role_id uuid not null references public.roles(id) on delete restrict,
  round_type public.round_type not null,
  competency_anchors jsonb not null,
  must_mention text[] not null default '{}',
  red_flags text[] not null default '{}',
  source public.rubric_source not null,
  status public.rubric_status not null default 'draft',
  rubric_version text not null,
  created_at timestamptz not null default now(),
  unique(skill_id, role_id, round_type, rubric_version)
);

create table public.scores (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  question_index integer not null check (question_index >= 0),
  skill_id uuid references public.skills(id) on delete set null,
  clarity numeric check (clarity between 0 and 100),
  depth numeric check (depth between 0 and 100),
  relevance numeric check (relevance between 0 and 100),
  communication numeric check (communication between 0 and 100),
  composite numeric check (composite between 0 and 100),
  evidence_quotes text[] not null default '{}',
  evidence_turn_ids uuid[] not null default '{}',
  signal_strength numeric(4,3) not null check (signal_strength between 0 and 1),
  status public.score_status not null,
  rubric_version text not null,
  model_provider text not null,
  model_name text not null,
  model_version text not null,
  prompt_version text not null,
  created_at timestamptz not null default now(),
  constraint scored_requires_evidence check (
    (status = 'scored' and cardinality(evidence_quotes) >= 1 and cardinality(evidence_turn_ids) >= 1
      and clarity is not null and depth is not null and relevance is not null and communication is not null and composite is not null)
    or
    (status = 'not_enough_signal' and clarity is null and depth is null and relevance is null and communication is null and composite is null)
  )
);

create table public.session_results (
  session_id uuid primary key references public.sessions(id) on delete cascade,
  role_readiness_low numeric check (role_readiness_low between 0 and 100),
  role_readiness_high numeric check (role_readiness_high between 0 and 100),
  interview_readiness_low numeric check (interview_readiness_low between 0 and 100),
  interview_readiness_high numeric check (interview_readiness_high between 0 and 100),
  verdict_word text not null,
  percentile numeric,
  root_cause text not null,
  prescribed_fix text not null,
  replay_markers jsonb not null default '[]',
  confidence_note text not null,
  model_provider text not null,
  model_name text not null,
  model_version text not null,
  prompt_version text not null,
  rubric_version text not null,
  created_at timestamptz not null default now(),
  check (role_readiness_low is null or role_readiness_high is null or role_readiness_low <= role_readiness_high),
  check (interview_readiness_low is null or interview_readiness_high is null or interview_readiness_low <= interview_readiness_high)
);

create table public.assessment_disputes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  session_id uuid not null references public.sessions(id) on delete cascade,
  target_type text not null check (target_type in ('flag','claim','score','skill_assessment')),
  target_id uuid not null,
  reason text not null,
  comment text,
  created_at timestamptz not null default now()
);

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  job_type text not null check (job_type in ('skeptic_turn','generate_report','generate_tts','process_resume','generate_question_plan')),
  payload jsonb not null,
  status public.job_status not null default 'pending',
  attempts integer not null default 0 check (attempts >= 0),
  run_after timestamptz not null default now(),
  locked_at timestamptz,
  locked_by text,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  error text
);

create table public.model_events (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references public.sessions(id) on delete cascade,
  turn_id uuid references public.turns(id) on delete cascade,
  operation text not null,
  latency_ms integer not null check (latency_ms >= 0),
  token_usage jsonb,
  model_provider text,
  model_name text,
  model_version text,
  prompt_version text,
  parsing_failed boolean not null default false,
  retry_count integer not null default 0,
  created_at timestamptz not null default now()
);

create table public.golden_cases (
  id uuid primary key default gen_random_uuid(),
  case_type text not null,
  transcript jsonb not null,
  expected_flags jsonb not null,
  expected_claim_states jsonb not null,
  expected_score_band jsonb not null,
  source text not null check (source in ('synthetic','expert-labelled')),
  version text not null,
  created_at timestamptz not null default now()
);

create table public.calibration_runs (
  id uuid primary key default gen_random_uuid(),
  rubric_version text not null,
  model_version text not null,
  golden_set_version text not null,
  band_distribution jsonb not null,
  auc numeric,
  drift_flag boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.outcomes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  company_id uuid,
  linked_session_id uuid references public.sessions(id) on delete set null,
  result text not null check (result in ('screen_rejected','technical_rejected','managerial_rejected','offer','unknown')),
  source text not null,
  verified boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.question_bank (
  id uuid primary key default gen_random_uuid(),
  canonical_text text not null,
  skill_id uuid references public.skills(id) on delete set null,
  role_id uuid references public.roles(id) on delete set null,
  company_id uuid,
  round_type public.round_type not null,
  report_count integer not null default 0,
  evidence_tier text not null,
  created_at timestamptz not null default now()
);

create table public.question_reports (
  id uuid primary key default gen_random_uuid(),
  raw_text text not null,
  consent_given boolean not null default false,
  pii_stripped boolean not null default false,
  source text not null,
  created_at timestamptz not null default now()
);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'private-resumes',
  'private-resumes',
  false,
  8388608,
  array['application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document']
)
on conflict (id) do nothing;

create index sessions_user_created_idx on public.sessions(user_id, created_at desc);
create index turns_session_turn_idx on public.turns(session_id, turn_index);
create index claims_session_status_idx on public.claims(session_id, status);
create index flags_pending_idx on public.flags(session_id, detected_at_turn, severity desc) where consumed = false;
create index jobs_ready_idx on public.jobs(status, run_after) where status = 'pending';
create index model_events_session_idx on public.model_events(session_id, created_at);

alter table public.colleges enable row level security;
alter table public.users enable row level security;
alter table public.roles enable row level security;
alter table public.skills enable row level security;
alter table public.sessions enable row level security;
alter table public.turns enable row level security;
alter table public.claims enable row level security;
alter table public.flags enable row level security;
alter table public.rubrics enable row level security;
alter table public.scores enable row level security;
alter table public.session_results enable row level security;
alter table public.assessment_disputes enable row level security;
alter table public.jobs enable row level security;
alter table public.model_events enable row level security;
alter table public.golden_cases enable row level security;
alter table public.calibration_runs enable row level security;
alter table public.outcomes enable row level security;
alter table public.question_bank enable row level security;
alter table public.question_reports enable row level security;

create policy users_read_self on public.users for select using (id = auth.uid());
create policy users_update_self on public.users for update using (id = auth.uid()) with check (id = auth.uid());
create policy sessions_owner_all on public.sessions for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy turns_owner_read on public.turns for select using (exists (select 1 from public.sessions s where s.id = session_id and s.user_id = auth.uid()));
create policy claims_owner_read on public.claims for select using (user_id = auth.uid());
create policy flags_owner_read on public.flags for select using (exists (select 1 from public.sessions s where s.id = session_id and s.user_id = auth.uid()));
create policy scores_owner_read on public.scores for select using (exists (select 1 from public.sessions s where s.id = session_id and s.user_id = auth.uid()));
create policy results_owner_read on public.session_results for select using (exists (select 1 from public.sessions s where s.id = session_id and s.user_id = auth.uid()));
create policy disputes_owner_all on public.assessment_disputes for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy outcomes_owner_read on public.outcomes for select using (user_id = auth.uid());
create policy public_roles_read on public.roles for select using (true);
create policy public_skills_read on public.skills for select using (true);
create policy active_rubrics_read on public.rubrics for select using (status = 'active');

-- TPO access is intentionally absent for turns, recordings, claims, flags, and individual scores.
-- Background workers use the service role, which bypasses RLS and must never be exposed to browsers.

commit;

