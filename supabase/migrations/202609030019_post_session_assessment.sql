begin;

alter table public.jobs drop constraint if exists jobs_job_type_check;
alter table public.jobs add constraint jobs_job_type_check check (job_type in (
  'skeptic_turn', 'SKEPTIC_TURN_ANALYSIS', 'generate_report', 'generate_tts',
  'process_resume', 'generate_question_plan', 'POST_SESSION_ASSESSMENT'
));

create or replace function public.enqueue_post_session_assessment(p_session_id uuid, p_user_id uuid)
returns setof public.jobs language plpgsql security definer set search_path = public as $$
declare
  queued_id uuid;
begin
  if not exists (select 1 from public.sessions where id = p_session_id and user_id = p_user_id and status = 'COMPLETED') then
    raise exception 'completed owned session not found';
  end if;
  insert into public.jobs (job_type, payload, status, dedupe_key)
  values ('POST_SESSION_ASSESSMENT', jsonb_build_object('session_id', p_session_id, 'user_id', p_user_id), 'pending', p_session_id::text || ':v1')
  on conflict (job_type, dedupe_key) where dedupe_key is not null do nothing
  returning id into queued_id;

  if queued_id is not null then
    insert into public.session_events (session_id, user_id, event_type, payload)
    values (p_session_id, p_user_id, 'assessment.queued', jsonb_build_object('job_id', queued_id));
  end if;

  return query
  select * from public.jobs
  where job_type = 'POST_SESSION_ASSESSMENT'
    and dedupe_key = p_session_id::text || ':v1';
end;
$$;

create or replace function public.claim_post_session_assessment(p_worker_id text, p_max_attempts integer)
returns setof public.jobs language plpgsql security definer set search_path = public as $$
begin
  return query with candidate as (
    select id from public.jobs where job_type = 'POST_SESSION_ASSESSMENT' and status = 'pending' and run_after <= now() and attempts < p_max_attempts
    order by run_after, created_at for update skip locked limit 1
  ) update public.jobs j set status='running', attempts=j.attempts+1, locked_at=now(), locked_by=left(p_worker_id, 200), error=null
  from candidate where j.id=candidate.id returning j.*;
end;
$$;

revoke all on function public.enqueue_post_session_assessment(uuid, uuid) from public, anon, authenticated;
revoke all on function public.claim_post_session_assessment(text, integer) from public, anon, authenticated;
grant execute on function public.enqueue_post_session_assessment(uuid, uuid) to service_role;
grant execute on function public.claim_post_session_assessment(text, integer) to service_role;
commit;
