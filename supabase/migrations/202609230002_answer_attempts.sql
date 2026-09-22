-- Try again: further attempts at a question the candidate already answered.
-- Additive. The interview transcript (public.turns) is never modified: the original
-- answer stays where it is, and every retry is a new row here with its own sequence.
begin;

create type public.attempt_comparison_source as enum ('MODEL', 'CHECKS');

create table public.answer_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  session_id uuid not null references public.sessions(id) on delete cascade,
  question_turn_id uuid not null references public.turns(id) on delete cascade,
  original_turn_id uuid not null references public.turns(id) on delete cascade,
  sequence integer not null check (sequence >= 1),
  question_text text not null,
  original_answer text not null,
  answer_text text not null,
  area_key text,
  area_title text,
  role_profile_id uuid references public.role_profiles(id) on delete set null,
  comparison jsonb,
  comparison_source public.attempt_comparison_source,
  model text,
  prompt_version text,
  created_at timestamptz not null default now(),
  unique (original_turn_id, sequence),
  constraint answer_attempts_answer_length check (char_length(trim(answer_text)) between 1 and 6000),
  constraint answer_attempts_comparison_pairs check ((comparison is null) = (comparison_source is null))
);

create index answer_attempts_owner_idx on public.answer_attempts(user_id, created_at desc);
create index answer_attempts_session_idx on public.answer_attempts(session_id);
create index answer_attempts_question_turn_idx on public.answer_attempts(question_turn_id);
create index answer_attempts_role_profile_idx on public.answer_attempts(role_profile_id);

-- An attempt may only point at the owner's own session, and at turns in that session.
create or replace function public.answer_attempts_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.sessions where id = new.session_id and user_id = new.user_id) then
    raise exception 'session does not belong to the attempt owner';
  end if;
  if not exists (
    select 1 from public.turns where id = new.original_turn_id and session_id = new.session_id and speaker = 'CANDIDATE'
  ) then
    raise exception 'original answer is not a candidate turn in this session';
  end if;
  if not exists (select 1 from public.turns where id = new.question_turn_id and session_id = new.session_id) then
    raise exception 'question is not a turn in this session';
  end if;
  if new.role_profile_id is not null and not exists (
    select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id
  ) then
    raise exception 'role profile does not belong to the attempt owner';
  end if;
  return new;
end;
$$;

create trigger answer_attempts_verify_ownership
  before insert or update on public.answer_attempts
  for each row execute function public.answer_attempts_verify_ownership();

-- Attempts are history: once written, the answer itself cannot change.
create or replace function public.answer_attempts_keep_history()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.answer_text is distinct from old.answer_text
    or new.original_answer is distinct from old.original_answer
    or new.question_text is distinct from old.question_text
    or new.sequence is distinct from old.sequence then
    raise exception 'answer attempts are immutable history';
  end if;
  return new;
end;
$$;

create trigger answer_attempts_keep_history
  before update on public.answer_attempts
  for each row execute function public.answer_attempts_keep_history();

alter table public.answer_attempts enable row level security;

create policy answer_attempts_select_own
  on public.answer_attempts for select to authenticated
  using (user_id = (select auth.uid()));

revoke insert, update, delete on public.answer_attempts from authenticated;
grant select on public.answer_attempts to authenticated;
grant all on public.answer_attempts to service_role;

commit;
