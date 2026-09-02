begin;
delete from storage.buckets where id = 'private-resumes';
drop trigger if exists on_auth_user_created on auth.users;
drop function if exists public.handle_new_user();
drop table if exists public.question_reports, public.question_bank, public.outcomes,
  public.calibration_runs, public.golden_cases, public.model_events, public.jobs,
  public.assessment_disputes, public.session_results, public.scores, public.rubrics,
  public.flags, public.claims, public.turns, public.sessions, public.skills,
  public.roles, public.users, public.colleges cascade;
drop type if exists public.skeptic_mode, public.job_status, public.score_status,
  public.rubric_source, public.rubric_status, public.round_type, public.flag_type,
  public.claim_status, public.claim_source, public.claim_type, public.turn_type,
  public.turn_speaker, public.interview_phase, public.session_status;
commit;

