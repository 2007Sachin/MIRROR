begin;
create table public.dig_deeper_responses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  role_profile_id uuid not null references public.role_profiles(id) on delete cascade,
  claim_id uuid not null references public.claims(id) on delete cascade,
  question_kind text not null,
  question_text text not null,
  answer text not null,
  story_part text not null,
  story_id uuid references public.stories(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, role_profile_id, claim_id, question_kind)
);
create index dig_deeper_responses_context_idx on public.dig_deeper_responses(user_id, role_profile_id, claim_id);
alter table public.dig_deeper_responses enable row level security;
create policy dig_deeper_responses_select_own on public.dig_deeper_responses for select to authenticated using (user_id = (select auth.uid()));
revoke insert, update, delete on public.dig_deeper_responses from authenticated;
grant select on public.dig_deeper_responses to authenticated;
grant all on public.dig_deeper_responses to service_role;
create or replace function public.dig_deeper_responses_verify_ownership() returns trigger language plpgsql set search_path = public as $$ begin
  if not exists (select 1 from role_profiles where id = new.role_profile_id and user_id = new.user_id) then raise exception 'role profile does not belong to responder'; end if;
  if not exists (select 1 from claims where id = new.claim_id and user_id = new.user_id) then raise exception 'claim does not belong to responder'; end if;
  new.updated_at := now(); return new;
end; $$;
create trigger dig_deeper_responses_verify_ownership before insert or update on public.dig_deeper_responses for each row execute function public.dig_deeper_responses_verify_ownership();
commit;
