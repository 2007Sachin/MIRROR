-- Local-only rollback for 20261005210000_target_prompt_completeness.sql.
-- Disable the target feature flag before running. This intentionally refuses populated prompt data.
begin;
lock table public.target_session_links in access exclusive mode;
lock table public.generated_questions in access exclusive mode;

do $$
begin
  if exists (select 1 from public.target_session_links where prompt_set_id is not null)
     or exists (select 1 from public.generated_questions) then
    raise exception 'rollback refused: prompt-backed links or generated question rows exist; archive/export or retain this migration';
  end if;
end;
$$;

drop trigger target_session_links_verify on public.target_session_links;
drop trigger generated_questions_guard_link on public.generated_questions;
drop function public.generated_questions_guard_link();
alter table public.generated_questions drop constraint generated_questions_prompt_set_id_fkey;
alter table public.target_session_links drop constraint target_session_links_prompt_set_id_key;
drop trigger target_session_links_write_once on public.target_session_links;

-- Restore function bodies exactly to the base migration 20261004200000.
create or replace function public.target_session_links_verify()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (select 1 from public.sessions where id = new.session_id and user_id = new.user_id) then
    raise exception 'session does not belong to the link owner';
  end if;
  if not exists (select 1 from public.candidate_targets where id = new.candidate_target_id and user_id = new.user_id) then
    raise exception 'target does not belong to the link owner';
  end if;
  if new.blueprint_id is not null and not exists (
    select 1 from public.interview_blueprints
    where id = new.blueprint_id and user_id = new.user_id and candidate_target_id = new.candidate_target_id
  ) then
    raise exception 'blueprint does not belong to the link target';
  end if;
  if new.prompt_set_id is not null and not exists (
    select 1 from public.generated_questions
    where prompt_set_id = new.prompt_set_id and user_id = new.user_id and candidate_target_id = new.candidate_target_id
  ) then
    raise exception 'prompt set does not belong to the link target';
  end if;
  return new;
end;
$$;

create or replace function public.target_session_links_write_once()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  raise exception 'a session link is write-once';
end;
$$;

create trigger target_session_links_verify
  before insert on public.target_session_links
  for each row execute function public.target_session_links_verify();
create trigger target_session_links_write_once
  before update on public.target_session_links
  for each row execute function public.target_session_links_write_once();

alter table public.target_session_links
  drop constraint target_session_links_prompt_state_shape,
  drop constraint target_session_links_expected_count_values,
  drop constraint target_session_links_prompt_state_values,
  drop column prompt_manifest,
  drop column expected_prompt_count,
  drop column prompt_set_state;

revoke select (session_id, user_id, candidate_target_id, blueprint_id, round_key, competency_key, prompt_set_id, created_at)
  on public.target_session_links from authenticated;
grant select on public.target_session_links to authenticated;

revoke all on function public.target_session_links_verify() from public, anon, authenticated;
revoke all on function public.target_session_links_write_once() from public, anon, authenticated;
commit;
