begin;
alter table public.session_results
 add column if not exists role_readiness_internal numeric,
 add column if not exists interview_readiness_internal numeric,
 add column if not exists verdict_code text,
 add column if not exists root_cause_code text,
 add column if not exists summary text,
 add column if not exists root_cause_explanation text,
 add column if not exists assessment_confidence numeric,
 add constraint session_results_internal_ranges check (
  (role_readiness_internal is null or role_readiness_internal between 0 and 100) and
  (interview_readiness_internal is null or interview_readiness_internal between 0 and 100) and
  (assessment_confidence is null or assessment_confidence between 0 and 1)
 );
commit;

