-- Local-only guarded rollback for 20261008230000_loop5a_candidate_stages.sql.
begin;
lock table public.candidate_targets, public.interview_blueprints, public.candidate_stage_notes in access exclusive mode;
do $$ begin
 if exists(select 1 from public.interview_blueprints where candidate_stage_state<>'NOT_ASKED' or candidate_stage_order_known or candidate_stages<>'[]'::jsonb or candidate_stage_mapping_version<>0 or candidate_stage_notes_revision<>0)
    or exists(select 1 from public.candidate_stage_notes) then
   raise exception 'rollback refused: candidate stage snapshot or note data would be lost';
 end if;
end $$;
revoke all on function public.candidate_stage_notes_archive_cleanup() from public,anon,authenticated,service_role;
drop trigger candidate_stage_notes_archive_cleanup on public.candidate_targets;
drop function public.candidate_stage_notes_archive_cleanup() restrict;
drop table public.candidate_stage_notes restrict;
revoke all on function public.append_target_blueprint_pin(uuid,uuid,integer,integer,text,text,text) from public,anon,authenticated,service_role;
revoke all on function public.save_candidate_stage_plan(uuid,uuid,integer,text,boolean,jsonb,jsonb) from public,anon,authenticated,service_role;
revoke all on function public.read_candidate_stage_plan(uuid,uuid,integer) from public,anon,authenticated,service_role;
drop function public.append_target_blueprint_pin(uuid,uuid,integer,integer,text,text,text) restrict;
drop function public.save_candidate_stage_plan(uuid,uuid,integer,text,boolean,jsonb,jsonb) restrict;
drop function public.read_candidate_stage_plan(uuid,uuid,integer) restrict;
revoke all on function public.validate_candidate_stages(text,boolean,jsonb) from public,anon,authenticated;
drop function public.validate_candidate_stages(text,boolean,jsonb) restrict;
grant all on public.interview_blueprints to service_role;
alter table public.interview_blueprints
 drop constraint interview_blueprints_candidate_stage_legacy,
 drop constraint interview_blueprints_candidate_stage_shape,
 drop constraint interview_blueprints_candidate_stage_notes_revision_check,
 drop constraint interview_blueprints_candidate_stage_mapping_check,
 drop constraint interview_blueprints_candidate_stages_array,
 drop constraint interview_blueprints_candidate_stage_state_check,
 drop column candidate_stage_notes_revision,
 drop column candidate_stage_mapping_version,
 drop column candidate_stages,
 drop column candidate_stage_order_known,
 drop column candidate_stage_state;
alter table public.candidate_targets drop constraint candidate_targets_id_user_key;
commit;
