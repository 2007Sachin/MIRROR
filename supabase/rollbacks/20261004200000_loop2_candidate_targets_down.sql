-- LOCAL-ONLY rollback for supabase/migrations/20261004200000_loop2_candidate_targets.sql.
-- Runbook: turn LOOP2_TARGETS_ENABLED off first, then verify there are no user rows
-- in any of the four tables below. This rollback deliberately refuses if rows exist.
-- Review this file and obtain the required owner approval before manual local execution.
-- Never run against hosted databases as part of migration rollout.
begin;

lock table public.candidate_targets, public.interview_blueprints, public.generated_questions, public.target_session_links in access exclusive mode;

do $$
begin
  if exists (select 1 from public.candidate_targets)
     or exists (select 1 from public.interview_blueprints)
     or exists (select 1 from public.generated_questions)
     or exists (select 1 from public.target_session_links) then
    raise exception 'rollback refused: Loop 2 owner rows exist';
  end if;
end $$;

drop table public.target_session_links restrict;
drop table public.generated_questions restrict;
drop table public.interview_blueprints restrict;
drop table public.candidate_targets restrict;

drop function public.target_session_links_write_once() restrict;
drop function public.target_session_links_verify() restrict;
drop function public.generated_questions_guard() restrict;
drop function public.interview_blueprints_guard() restrict;
drop function public.candidate_targets_guard() restrict;

commit;
