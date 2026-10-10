-- Loop 5A candidate-owned stage snapshots and erasable current-only notes. Local acceptance only.
begin;

alter table public.candidate_targets add constraint candidate_targets_id_user_key unique (id, user_id);
alter table public.interview_blueprints
  add column candidate_stage_state text not null default 'NOT_ASKED',
  add column candidate_stage_order_known boolean not null default false,
  add column candidate_stages jsonb not null default '[]'::jsonb,
  add column candidate_stage_mapping_version integer not null default 0,
  add column candidate_stage_notes_revision bigint not null default 0,
  add constraint interview_blueprints_candidate_stage_state_check check (candidate_stage_state in ('NOT_ASKED','NOT_YET','KNOWN')),
  add constraint interview_blueprints_candidate_stages_array check (jsonb_typeof(candidate_stages) = 'array' and jsonb_array_length(candidate_stages) <= 12),
  add constraint interview_blueprints_candidate_stage_mapping_check check (candidate_stage_mapping_version in (0,1)),
  add constraint interview_blueprints_candidate_stage_notes_revision_check check (candidate_stage_notes_revision >= 0),
  add constraint interview_blueprints_candidate_stage_shape check (
    (candidate_stage_state = 'KNOWN' and jsonb_array_length(candidate_stages) between 1 and 12 and candidate_stage_mapping_version = 1)
    or (candidate_stage_state in ('NOT_ASKED','NOT_YET') and jsonb_array_length(candidate_stages) = 0 and not candidate_stage_order_known)
  ),
  add constraint interview_blueprints_candidate_stage_legacy check (
    candidate_stage_mapping_version <> 0 or (candidate_stage_state = 'NOT_ASKED' and not candidate_stage_order_known and candidate_stages = '[]'::jsonb and candidate_stage_notes_revision = 0)
  );

create or replace function public.validate_candidate_stages(p_state text, p_order_known boolean, p_stages jsonb)
returns void language plpgsql immutable set search_path = pg_catalog, public as $$
declare x jsonb; n integer := 0; ids uuid[] := '{}'; k text; seq integer;
begin
  if p_state is null or p_order_known is null or p_state not in ('NOT_ASKED','NOT_YET','KNOWN') or jsonb_typeof(p_stages) is distinct from 'array' or jsonb_array_length(p_stages)>12 then raise exception 'invalid candidate stage state or array'; end if;
  if (p_state='KNOWN') <> (jsonb_array_length(p_stages)>0) then raise exception 'candidate stage state/list mismatch'; end if;
  if p_state <> 'KNOWN' and p_order_known then raise exception 'non-known stage state cannot have known order'; end if;
  for x in select value from jsonb_array_elements(p_stages) loop
    n:=n+1;
    if jsonb_typeof(x) is distinct from 'object' or (select array_agg(obj.key_name order by obj.key_name) from jsonb_object_keys(x) as obj(key_name)) is distinct from array['certainty','custom_label','kind','sequence','stage_id']::text[] then raise exception 'candidate stage keys must be exact'; end if;
    if jsonb_typeof(x->'stage_id') is distinct from 'string' or jsonb_typeof(x->'kind') is distinct from 'string' or jsonb_typeof(x->'certainty') is distinct from 'string' then raise exception 'invalid candidate stage field types'; end if;
    if (x->>'stage_id') !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then raise exception 'invalid stage UUID'; end if;
    ids:=array_append(ids,(x->>'stage_id')::uuid); k:=x->>'kind';
    if k not in ('RECRUITER_SCREENING','TECHNICAL_INTERVIEW','CODING_EXERCISE','CASE_INTERVIEW','BEHAVIORAL_INTERVIEW','HIRING_MANAGER_DISCUSSION','PORTFOLIO_PROJECT_DISCUSSION','OTHER') then raise exception 'invalid stage kind'; end if;
    if x->>'certainty' not in ('SURE','UNCERTAIN') then raise exception 'invalid stage certainty'; end if;
    if k='OTHER' then if jsonb_typeof(x->'custom_label') is distinct from 'string' or char_length(btrim(x->>'custom_label')) not between 1 and 80 or x->>'custom_label' is distinct from btrim(x->>'custom_label') then raise exception 'invalid OTHER custom label'; end if;
    elsif x->'custom_label' <> 'null'::jsonb then raise exception 'custom_label only allowed for OTHER'; end if;
    if p_order_known then
      if jsonb_typeof(x->'sequence') is distinct from 'number' or (x->>'sequence') !~ '^[0-9]+$' or char_length(x->>'sequence') > 2 then raise exception 'invalid stage sequence'; end if;
      seq:=(x->>'sequence')::integer; if seq<>n then raise exception 'stage sequence must be contiguous and canonical'; end if;
    elsif x->'sequence' <> 'null'::jsonb then raise exception 'unknown order requires null sequence'; end if;
  end loop;
  if cardinality(ids) <> (select count(distinct i) from unnest(ids) i) then raise exception 'duplicate stage UUID'; end if;
end $$;

create table public.candidate_stage_notes (
  user_id uuid not null references public.profiles(id) on delete cascade,
  candidate_target_id uuid not null,
  stage_id uuid not null,
  note text not null check (char_length(btrim(note)) between 1 and 500 and char_length(note)<=500 and note=btrim(note)),
  updated_at timestamptz not null default now(),
  primary key (user_id,candidate_target_id,stage_id),
  constraint candidate_stage_notes_target_owner_fk foreign key (candidate_target_id,user_id) references public.candidate_targets(id,user_id) on delete cascade
);
alter table public.candidate_stage_notes enable row level security;
revoke all on public.candidate_stage_notes from public, anon, authenticated, service_role;

create or replace function public.candidate_stage_notes_archive_cleanup()
returns trigger language plpgsql security definer set search_path = pg_catalog, public as $$
begin
 if old.status='ACTIVE' and new.status='ARCHIVED' then delete from public.candidate_stage_notes where candidate_target_id=old.id and user_id=old.user_id; end if;
 return new;
end $$;
create trigger candidate_stage_notes_archive_cleanup after update of status on public.candidate_targets for each row execute function public.candidate_stage_notes_archive_cleanup();

create or replace function public.append_target_blueprint_pin(p_user_id uuid,p_target_id uuid,p_expected_version integer,p_catalog_version integer,p_catalog_sha256 text,p_match_state text,p_rules_version text)
returns integer language plpgsql security definer set search_path = pg_catalog, public as $$
declare t public.candidate_targets%rowtype; b public.interview_blueprints%rowtype; v integer;
begin
 if p_user_id is null or p_target_id is null or auth.role() is distinct from 'service_role' then raise exception 'service role authorization failed'; end if;
 if p_catalog_version is null or p_catalog_version < 1 or p_catalog_sha256 is null or p_catalog_sha256 !~ '^[0-9a-f]{64}$'
   or p_match_state is null or p_match_state not in ('RESEARCHED','GENERAL_ONLY','NOT_RESEARCHED')
   or p_rules_version is null or char_length(btrim(p_rules_version)) not between 1 and 40 then
  raise exception 'invalid blueprint pin';
 end if;
 select * into t from public.candidate_targets where id=p_target_id and user_id=p_user_id for update;
 if not found then raise exception 'target does not belong to owner'; end if;
 if t.status<>'ACTIVE' then raise exception 'target is archived'; end if;
 select * into b from public.interview_blueprints where candidate_target_id=p_target_id order by version desc limit 1;
 if p_expected_version is null or p_expected_version <> coalesce(b.version,0) then raise exception 'stale blueprint pin'; end if;
 if b.id is not null then
  if p_catalog_version < b.catalog_version then raise exception 'catalog version regression'; end if;
  if p_catalog_version = b.catalog_version and b.catalog_sha256 is distinct from p_catalog_sha256 then raise exception 'catalog version hash mismatch'; end if;
  if b.catalog_version=p_catalog_version and b.catalog_sha256=p_catalog_sha256 and b.match_state=p_match_state and b.rules_version=p_rules_version then return b.version; end if;
 end if;
 v:=coalesce(b.version,0)+1;
 insert into public.interview_blueprints(user_id,candidate_target_id,version,catalog_version,catalog_sha256,match_state,rules_version,candidate_stage_state,candidate_stage_order_known,candidate_stages,candidate_stage_mapping_version,candidate_stage_notes_revision)
 values(p_user_id,p_target_id,v,p_catalog_version,p_catalog_sha256,p_match_state,p_rules_version,coalesce(b.candidate_stage_state,'NOT_ASKED'),coalesce(b.candidate_stage_order_known,false),coalesce(b.candidate_stages,'[]'::jsonb),case when b.id is null then 1 else b.candidate_stage_mapping_version end,coalesce(b.candidate_stage_notes_revision,0));
 return v;
end $$;

create or replace function public.save_candidate_stage_plan(p_user_id uuid,p_target_id uuid,p_expected_version integer,p_state text,p_order_known boolean,p_stages jsonb,p_notes jsonb)
returns integer language plpgsql security definer set search_path = pg_catalog, public as $$
declare t public.candidate_targets%rowtype; b public.interview_blueprints%rowtype; v integer; notes_same boolean; snapshot_same boolean; note_key text; note_val text; stage_uuid uuid;
begin
 if p_user_id is null or p_target_id is null or auth.role() is distinct from 'service_role' then raise exception 'service role authorization failed'; end if;
 if p_expected_version is null or p_expected_version < 0 then raise exception 'invalid expected blueprint version'; end if;
 perform public.validate_candidate_stages(p_state,p_order_known,p_stages);
 if jsonb_typeof(p_notes) is distinct from 'object' then raise exception 'notes must be a JSON object'; end if;
 if exists(select 1 from jsonb_each(p_notes) e where e.key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' or jsonb_typeof(e.value) is distinct from 'string' or char_length(btrim(e.value#>>'{}')) not between 1 and 500 or char_length(e.value#>>'{}')>500 or e.value#>>'{}' is distinct from btrim(e.value#>>'{}')) then raise exception 'invalid candidate stage note'; end if;
 if exists(select 1 from jsonb_each(p_notes) e where not exists(select 1 from jsonb_array_elements(p_stages) s where s->>'stage_id'=e.key)) then raise exception 'note stage is absent from plan'; end if;
 select * into t from public.candidate_targets where id=p_target_id and user_id=p_user_id for update;
 if not found then raise exception 'target does not belong to owner'; end if;
 if t.status<>'ACTIVE' then raise exception 'target is archived'; end if;
 select * into b from public.interview_blueprints where candidate_target_id=p_target_id order by version desc limit 1 for update;
 if not found then raise exception 'target has no blueprint'; end if;
 select not exists(select 1 from public.candidate_stage_notes n where n.candidate_target_id=p_target_id and n.user_id=p_user_id and not exists(select 1 from jsonb_each(p_notes) e where e.key=n.stage_id::text and e.value#>>'{}'=n.note))
   and not exists(select 1 from jsonb_each(p_notes) e where not exists(select 1 from public.candidate_stage_notes n where n.candidate_target_id=p_target_id and n.user_id=p_user_id and n.stage_id=e.key::uuid and n.note=e.value#>>'{}')) into notes_same;
 snapshot_same:=b.candidate_stage_state=p_state and b.candidate_stage_order_known=p_order_known and b.candidate_stages=p_stages;
 if p_expected_version<>b.version and not(snapshot_same and notes_same) then raise exception 'stale candidate stage plan'; end if;
 if snapshot_same and notes_same then return b.version; end if;
 v:=b.version+1;
 insert into public.interview_blueprints(user_id,candidate_target_id,version,catalog_version,catalog_sha256,match_state,rules_version,candidate_stage_state,candidate_stage_order_known,candidate_stages,candidate_stage_mapping_version,candidate_stage_notes_revision)
 values(b.user_id,b.candidate_target_id,v,b.catalog_version,b.catalog_sha256,b.match_state,b.rules_version,p_state,p_order_known,p_stages,1,b.candidate_stage_notes_revision+(case when notes_same then 0 else 1 end));
 delete from public.candidate_stage_notes n where n.candidate_target_id=p_target_id and n.user_id=p_user_id and not exists(select 1 from jsonb_each(p_notes) e where e.key=n.stage_id::text);
 for note_key,note_val in select key,value#>>'{}' from jsonb_each(p_notes) loop
  stage_uuid:=note_key::uuid;
  insert into public.candidate_stage_notes(user_id,candidate_target_id,stage_id,note) values(p_user_id,p_target_id,stage_uuid,note_val)
  on conflict(user_id,candidate_target_id,stage_id) do update set note=excluded.note,updated_at=now() where public.candidate_stage_notes.note is distinct from excluded.note;
 end loop;
 return v;
end $$;

create or replace function public.read_candidate_stage_plan(p_user_id uuid,p_target_id uuid,p_version integer default null)
returns jsonb language plpgsql security definer set search_path = pg_catalog, public as $$
declare t public.candidate_targets%rowtype; b public.interview_blueprints%rowtype; latest_version integer; ns jsonb:='{}'::jsonb;
begin
 if p_user_id is null or auth.role() is distinct from 'service_role' then raise exception 'service role authorization failed'; end if;
 select * into t from public.candidate_targets where id=p_target_id and user_id=p_user_id for share;
 if not found then raise exception 'target does not belong to owner'; end if;
 select coalesce(max(version),0) into latest_version from public.interview_blueprints where candidate_target_id=p_target_id and user_id=p_user_id;
 if p_version is null then select * into b from public.interview_blueprints where candidate_target_id=p_target_id and user_id=p_user_id order by version desc limit 1;
 else select * into b from public.interview_blueprints where candidate_target_id=p_target_id and user_id=p_user_id and version=p_version; end if;
 if not found then raise exception 'blueprint not found'; end if;
 if p_version is null then select coalesce(jsonb_object_agg(stage_id::text,note),'{}'::jsonb) into ns from public.candidate_stage_notes where user_id=p_user_id and candidate_target_id=p_target_id; end if;
 return jsonb_build_object('blueprint_id',b.id,'version',b.version,'candidate_stage_state',b.candidate_stage_state,'candidate_stage_order_known',b.candidate_stage_order_known,'candidate_stages',b.candidate_stages,'candidate_stage_mapping_version',b.candidate_stage_mapping_version,'candidate_stage_notes_revision',b.candidate_stage_notes_revision,'notes',ns,'latest_version',latest_version,'blueprint',to_jsonb(b));
end $$;

revoke all on function public.validate_candidate_stages(text,boolean,jsonb) from public,anon,authenticated;
revoke all on function public.candidate_stage_notes_archive_cleanup() from public,anon,authenticated,service_role;
revoke all on function public.append_target_blueprint_pin(uuid,uuid,integer,integer,text,text,text) from public,anon,authenticated;
revoke all on function public.save_candidate_stage_plan(uuid,uuid,integer,text,boolean,jsonb,jsonb) from public,anon,authenticated;
revoke all on function public.read_candidate_stage_plan(uuid,uuid,integer) from public,anon,authenticated;
grant execute on function public.append_target_blueprint_pin(uuid,uuid,integer,integer,text,text,text) to service_role;
grant execute on function public.save_candidate_stage_plan(uuid,uuid,integer,text,boolean,jsonb,jsonb) to service_role;
grant execute on function public.read_candidate_stage_plan(uuid,uuid,integer) to service_role;
revoke insert,update,delete,truncate,references,trigger on public.interview_blueprints from service_role;
commit;
