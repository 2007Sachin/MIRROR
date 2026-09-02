begin;

alter type public.claim_status add value if not exists 'partially_held';
alter type public.claim_status add value if not exists 'insufficient_evidence';

commit;

begin;

create type public.claim_entity_type as enum (
  'SKILL', 'PROJECT', 'TOOL', 'COMPANY', 'METRIC', 'OUTCOME', 'RESPONSIBILITY'
);
create type public.claim_graph_node_type as enum ('CLAIM', 'ENTITY');
create type public.claim_relation_type as enum (
  'ABOUT_SKILL',
  'ABOUT_PROJECT',
  'USES_TOOL',
  'ABOUT_COMPANY',
  'HAS_METRIC',
  'CLAIMS_OUTCOME',
  'CLAIMS_OWNERSHIP',
  'CLAIMS_RESPONSIBILITY',
  'RELATED_TO'
);
create type public.claim_relation_source as enum (
  'RESUME_ANALYSIS', 'APPLICATION', 'USER', 'INTERVIEW'
);
create type public.claim_changed_by as enum ('SYSTEM', 'AI', 'USER', 'ADMIN');
create type public.claim_evidence_type as enum (
  'DOCUMENT_EXCERPT', 'INTERVIEW_TURN', 'USER_CORRECTION', 'SYSTEM_OBSERVATION'
);
create type public.evidence_direction as enum ('SUPPORTS', 'WEAKENS', 'CONTEXT_ONLY');

update public.claims
set verification_priority = 'MEDIUM'
where verification_priority is null;

alter table public.claims
  alter column verification_priority set default 'MEDIUM',
  alter column verification_priority set not null;

drop trigger if exists claims_set_updated_at on public.claims;
create trigger claims_set_updated_at
  before update on public.claims
  for each row execute procedure public.set_updated_at();

create table public.claim_entities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  entity_type public.claim_entity_type not null,
  canonical_name text not null,
  canonical_key text generated always as (lower(trim(canonical_name))) stored,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint claim_entities_name_length check (char_length(trim(canonical_name)) between 1 and 500),
  constraint claim_entities_metadata_object check (jsonb_typeof(metadata) = 'object'),
  unique (user_id, entity_type, canonical_key)
);

create table public.claim_relations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_entity_type public.claim_graph_node_type not null,
  source_entity_id uuid not null,
  relation_type public.claim_relation_type not null,
  target_entity_type public.claim_graph_node_type not null,
  target_entity_id uuid not null,
  confidence numeric(4,3) not null check (confidence between 0 and 1),
  source public.claim_relation_source not null,
  created_at timestamptz not null default now(),
  constraint claim_relations_distinct_nodes check (
    source_entity_type <> target_entity_type or source_entity_id <> target_entity_id
  ),
  constraint claim_relations_include_claim check (
    source_entity_type = 'CLAIM' or target_entity_type = 'CLAIM'
  ),
  unique (
    user_id, source_entity_type, source_entity_id, relation_type,
    target_entity_type, target_entity_id, source
  )
);

create table public.claim_versions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  claim_id uuid not null references public.claims(id) on delete cascade,
  version integer not null check (version > 0),
  previous_state jsonb,
  new_state jsonb not null,
  changed_by public.claim_changed_by not null,
  reason text not null,
  created_at timestamptz not null default now(),
  constraint claim_versions_previous_object check (
    previous_state is null or jsonb_typeof(previous_state) = 'object'
  ),
  constraint claim_versions_new_object check (jsonb_typeof(new_state) = 'object'),
  constraint claim_versions_reason_length check (char_length(trim(reason)) between 3 and 2000),
  unique (claim_id, version)
);

create table public.claim_evidence (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  claim_id uuid not null references public.claims(id) on delete cascade,
  evidence_type public.claim_evidence_type not null,
  turn_id uuid references public.turns(id) on delete cascade,
  document_id uuid references public.documents(id) on delete cascade,
  quote_text text,
  evidence_direction public.evidence_direction not null,
  strength numeric(4,3) not null check (strength between 0 and 1),
  created_at timestamptz not null default now(),
  constraint claim_evidence_has_anchor check (
    turn_id is not null or document_id is not null or quote_text is not null
  ),
  constraint claim_evidence_quote_length check (
    quote_text is null or char_length(trim(quote_text)) between 1 and 5000
  ),
  constraint claim_evidence_type_anchor check (
    (evidence_type <> 'INTERVIEW_TURN' or turn_id is not null)
    and (evidence_type <> 'DOCUMENT_EXCERPT' or document_id is not null)
  )
);

create index claim_entities_owner_type_idx
  on public.claim_entities(user_id, entity_type, canonical_key);
create index claim_relations_source_idx
  on public.claim_relations(user_id, source_entity_type, source_entity_id);
create index claim_relations_target_idx
  on public.claim_relations(user_id, target_entity_type, target_entity_id);
create index claim_versions_claim_idx on public.claim_versions(claim_id, version desc);
create index claim_evidence_claim_idx on public.claim_evidence(claim_id, created_at);
create index claims_user_status_source_idx on public.claims(user_id, status, source, created_at desc);

alter table public.claim_entities enable row level security;
alter table public.claim_relations enable row level security;
alter table public.claim_versions enable row level security;
alter table public.claim_evidence enable row level security;

create policy claim_entities_select_own
  on public.claim_entities for select to authenticated using (user_id = auth.uid());
create policy claim_relations_select_own
  on public.claim_relations for select to authenticated using (user_id = auth.uid());
create policy claim_versions_select_own
  on public.claim_versions for select to authenticated using (user_id = auth.uid());
create policy claim_evidence_select_own
  on public.claim_evidence for select to authenticated using (user_id = auth.uid());

revoke insert, update, delete on public.claim_entities from authenticated;
revoke insert, update, delete on public.claim_relations from authenticated;
revoke insert, update, delete on public.claim_versions from authenticated;
revoke insert, update, delete on public.claim_evidence from authenticated;
grant select on public.claim_entities to authenticated;
grant select on public.claim_relations to authenticated;
grant select on public.claim_versions to authenticated;
grant select on public.claim_evidence to authenticated;
grant all on public.claim_entities to service_role;
grant all on public.claim_relations to service_role;
grant all on public.claim_versions to service_role;
grant all on public.claim_evidence to service_role;

create or replace function public.claim_graph_node_belongs_to_user(
  p_node_type public.claim_graph_node_type,
  p_node_id uuid,
  p_user_id uuid
)
returns boolean
language sql
stable
set search_path = public
as $$
  select case p_node_type
    when 'CLAIM' then exists (
      select 1 from public.claims where id = p_node_id and user_id = p_user_id
    )
    when 'ENTITY' then exists (
      select 1 from public.claim_entities where id = p_node_id and user_id = p_user_id
    )
    else false
  end;
$$;

create or replace function public.validate_claim_relation_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not public.claim_graph_node_belongs_to_user(
    new.source_entity_type, new.source_entity_id, new.user_id
  ) or not public.claim_graph_node_belongs_to_user(
    new.target_entity_type, new.target_entity_id, new.user_id
  ) then
    raise exception 'claim relation nodes must belong to the same user';
  end if;
  return new;
end;
$$;

create trigger claim_relations_validate_ownership
  before insert or update on public.claim_relations
  for each row execute procedure public.validate_claim_relation_ownership();

create or replace function public.validate_claim_child_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.claims where id = new.claim_id and user_id = new.user_id
  ) then
    raise exception 'claim child row must belong to the claim owner';
  end if;

  if tg_table_name = 'claim_evidence' and new.document_id is not null and not exists (
    select 1 from public.documents where id = new.document_id and user_id = new.user_id
  ) then
    raise exception 'claim evidence document must belong to the claim owner';
  end if;

  if tg_table_name = 'claim_evidence' and new.turn_id is not null and not exists (
    select 1
    from public.turns t
    join public.sessions s on s.id = t.session_id
    where t.id = new.turn_id and s.user_id = new.user_id
  ) then
    raise exception 'claim evidence turn must belong to the claim owner';
  end if;
  return new;
end;
$$;

create trigger claim_versions_validate_ownership
  before insert or update on public.claim_versions
  for each row execute procedure public.validate_claim_child_ownership();
create trigger claim_evidence_validate_ownership
  before insert or update on public.claim_evidence
  for each row execute procedure public.validate_claim_child_ownership();

create or replace function public.build_claim_graph_for_resume_analysis(
  p_analysis_id uuid,
  p_user_id uuid
)
returns void
language plpgsql
set search_path = public
as $$
begin
  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'SKILL', trim(skill), '{}'::jsonb
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and nullif(trim(skill), '') is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'PROJECT', trim(project_name), '{}'::jsonb
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and nullif(trim(project_name), '') is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'TOOL', trim(tool), '{}'::jsonb
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and nullif(trim(tool), '') is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'OUTCOME', trim(outcome), '{}'::jsonb
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and nullif(trim(outcome), '') is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct
    user_id,
    'METRIC',
    trim(metric_value::text || coalesce(' ' || nullif(trim(metric_unit), ''), '')),
    jsonb_strip_nulls(jsonb_build_object('value', metric_value, 'unit', metric_unit))
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and metric_value is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'RESPONSIBILITY', trim(claim_text),
    jsonb_strip_nulls(jsonb_build_object('ownership_language', ownership_language))
  from public.claims
  where resume_analysis_id = p_analysis_id
    and user_id = p_user_id
    and claim_type in ('ownership', 'responsibility')
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_relations (
    user_id, source_entity_type, source_entity_id, relation_type,
    target_entity_type, target_entity_id, confidence, source
  )
  select c.user_id, 'CLAIM', c.id, mapping.relation_type,
    'ENTITY', e.id, c.confidence, 'RESUME_ANALYSIS'
  from public.claims c
  cross join lateral (
    values
      ('SKILL'::public.claim_entity_type, c.skill, 'ABOUT_SKILL'::public.claim_relation_type),
      ('PROJECT'::public.claim_entity_type, c.project_name, 'ABOUT_PROJECT'::public.claim_relation_type),
      ('TOOL'::public.claim_entity_type, c.tool, 'USES_TOOL'::public.claim_relation_type),
      ('OUTCOME'::public.claim_entity_type, c.outcome, 'CLAIMS_OUTCOME'::public.claim_relation_type),
      ('METRIC'::public.claim_entity_type,
        case when c.metric_value is null then null else
          trim(c.metric_value::text || coalesce(' ' || nullif(trim(c.metric_unit), ''), '')) end,
        'HAS_METRIC'::public.claim_relation_type),
      ('RESPONSIBILITY'::public.claim_entity_type,
        case when c.claim_type in ('ownership', 'responsibility') then c.claim_text else null end,
        case when c.claim_type = 'ownership'
          then 'CLAIMS_OWNERSHIP'::public.claim_relation_type
          else 'CLAIMS_RESPONSIBILITY'::public.claim_relation_type end)
  ) as mapping(entity_type, canonical_name, relation_type)
  join public.claim_entities e
    on e.user_id = c.user_id
    and e.entity_type = mapping.entity_type
    and e.canonical_key = lower(trim(mapping.canonical_name))
  where c.resume_analysis_id = p_analysis_id
    and c.user_id = p_user_id
    and nullif(trim(mapping.canonical_name), '') is not null
  on conflict do nothing;

  insert into public.claim_versions (
    user_id, claim_id, version, previous_state, new_state, changed_by, reason
  )
  select c.user_id, c.id, 1, null,
    jsonb_build_object(
      'claim_text', c.claim_text,
      'status', upper(c.status::text),
      'confidence', c.confidence,
      'verification_priority', c.verification_priority::text
    ),
    'AI',
    'Initial claim extracted from resume analysis'
  from public.claims c
  where c.resume_analysis_id = p_analysis_id and c.user_id = p_user_id
  on conflict (claim_id, version) do nothing;

  insert into public.claim_evidence (
    user_id, claim_id, evidence_type, document_id, quote_text,
    evidence_direction, strength
  )
  select c.user_id, c.id, 'DOCUMENT_EXCERPT', c.source_document_id,
    c.claim_text, 'CONTEXT_ONLY', c.confidence
  from public.claims c
  where c.resume_analysis_id = p_analysis_id
    and c.user_id = p_user_id
    and c.source_document_id is not null
  on conflict do nothing;
end;
$$;

create or replace function public.complete_resume_analysis(
  p_analysis_id uuid,
  p_user_id uuid,
  p_execution_id uuid,
  p_output jsonb
)
returns setof public.resume_analyses
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.resume_analyses
    where id = p_analysis_id and user_id = p_user_id and status = 'PROCESSING'
    for update
  ) then
    raise exception 'resume analysis is not available for completion';
  end if;

  insert into public.claims (
    session_id, user_id, claim_text, claim_type, source, source_ref, status,
    confidence, source_document_id, resume_analysis_id, source_reference,
    verification_priority, skill, project_name, metric_value, metric_unit,
    ownership_language, outcome, tool
  )
  select
    null, p_user_id, claim ->> 'claim_text',
    lower(claim ->> 'claim_type')::public.claim_type,
    'resume'::public.claim_source,
    claim ->> 'source_reference',
    'unverified'::public.claim_status,
    (claim ->> 'confidence')::numeric,
    analysis.document_id, analysis.id,
    claim ->> 'source_reference',
    (claim ->> 'verification_priority')::public.verification_priority,
    claim ->> 'skill', claim ->> 'project_name',
    nullif(claim ->> 'metric_value', '')::numeric,
    claim ->> 'metric_unit', claim ->> 'ownership_language',
    claim ->> 'outcome', claim ->> 'tool'
  from public.resume_analyses analysis
  cross join lateral jsonb_array_elements(coalesce(p_output -> 'claims', '[]'::jsonb)) claim
  where analysis.id = p_analysis_id and analysis.user_id = p_user_id;

  perform public.build_claim_graph_for_resume_analysis(p_analysis_id, p_user_id);

  return query
  update public.resume_analyses
  set status = 'COMPLETED', output = p_output, execution_id = p_execution_id,
      completed_at = now()
  where id = p_analysis_id and user_id = p_user_id
  returning *;
end;
$$;

create or replace function public.update_claim_status(
  p_claim_id uuid,
  p_user_id uuid,
  p_new_status public.claim_status,
  p_changed_by public.claim_changed_by,
  p_reason text
)
returns setof public.claims
language plpgsql
set search_path = public
as $$
declare
  old_claim public.claims%rowtype;
  next_version integer;
begin
  select * into old_claim from public.claims
  where id = p_claim_id and user_id = p_user_id
  for update;
  if old_claim.id is null then
    raise exception 'claim not found';
  end if;
  if old_claim.status = p_new_status then
    raise exception 'claim already has requested status';
  end if;
  if char_length(trim(p_reason)) < 3 then
    raise exception 'status change reason is required';
  end if;

  select coalesce(max(version), 0) + 1 into next_version
  from public.claim_versions where claim_id = p_claim_id;

  insert into public.claim_versions (
    user_id, claim_id, version, previous_state, new_state, changed_by, reason
  ) values (
    p_user_id, p_claim_id, next_version,
    jsonb_build_object('claim_text', old_claim.claim_text, 'status', upper(old_claim.status::text), 'confidence', old_claim.confidence),
    jsonb_build_object('claim_text', old_claim.claim_text, 'status', upper(p_new_status::text), 'confidence', old_claim.confidence),
    p_changed_by, trim(p_reason)
  );

  return query update public.claims
  set status = p_new_status
  where id = p_claim_id and user_id = p_user_id
  returning *;
end;
$$;

create or replace function public.create_claim_with_version(
  p_user_id uuid,
  p_claim jsonb,
  p_changed_by public.claim_changed_by,
  p_reason text
)
returns setof public.claims
language plpgsql
set search_path = public
as $$
declare
  created_claim public.claims%rowtype;
begin
  if char_length(trim(p_reason)) < 3 then
    raise exception 'claim creation reason is required';
  end if;
  if p_claim ->> 'session_id' is not null and not exists (
    select 1 from public.sessions
    where id = (p_claim ->> 'session_id')::uuid and user_id = p_user_id
  ) then
    raise exception 'claim session must belong to the claim owner';
  end if;
  if p_claim ->> 'source_document_id' is not null and not exists (
    select 1 from public.documents
    where id = (p_claim ->> 'source_document_id')::uuid and user_id = p_user_id
  ) then
    raise exception 'claim document must belong to the claim owner';
  end if;

  insert into public.claims (
    session_id, user_id, claim_text, claim_type, source, source_ref, status,
    confidence, source_document_id, source_reference, verification_priority, synthetic
  ) values (
    nullif(p_claim ->> 'session_id', '')::uuid,
    p_user_id,
    trim(p_claim ->> 'claim_text'),
    lower(p_claim ->> 'claim_type')::public.claim_type,
    lower(p_claim ->> 'source')::public.claim_source,
    p_claim ->> 'source_reference',
    'unverified',
    (p_claim ->> 'confidence')::numeric,
    nullif(p_claim ->> 'source_document_id', '')::uuid,
    p_claim ->> 'source_reference',
    (p_claim ->> 'verification_priority')::public.verification_priority,
    coalesce((p_claim ->> 'synthetic')::boolean, false)
  ) returning * into created_claim;

  insert into public.claim_versions (
    user_id, claim_id, version, previous_state, new_state, changed_by, reason
  ) values (
    p_user_id, created_claim.id, 1, null,
    jsonb_build_object(
      'claim_text', created_claim.claim_text,
      'status', upper(created_claim.status::text),
      'confidence', created_claim.confidence,
      'verification_priority', created_claim.verification_priority::text
    ),
    p_changed_by, trim(p_reason)
  );
  return next created_claim;
end;
$$;

create or replace function public.append_claim_version(
  p_claim_id uuid,
  p_user_id uuid,
  p_previous_state jsonb,
  p_new_state jsonb,
  p_changed_by public.claim_changed_by,
  p_reason text
)
returns setof public.claim_versions
language plpgsql
set search_path = public
as $$
declare
  next_version integer;
begin
  if not exists (
    select 1 from public.claims
    where id = p_claim_id and user_id = p_user_id for update
  ) then
    raise exception 'claim not found';
  end if;
  select coalesce(max(version), 0) + 1 into next_version
  from public.claim_versions where claim_id = p_claim_id;
  return query insert into public.claim_versions (
    user_id, claim_id, version, previous_state, new_state, changed_by, reason
  ) values (
    p_user_id, p_claim_id, next_version, p_previous_state, p_new_state,
    p_changed_by, trim(p_reason)
  ) returning *;
end;
$$;

create or replace function public.find_related_claims(
  p_claim_id uuid,
  p_user_id uuid
)
returns setof public.claims
language sql
stable
set search_path = public
as $$
  with anchors as (
    select target_entity_type, target_entity_id
    from public.claim_relations
    where user_id = p_user_id
      and source_entity_type = 'CLAIM'
      and source_entity_id = p_claim_id
    union
    select source_entity_type, source_entity_id
    from public.claim_relations
    where user_id = p_user_id
      and target_entity_type = 'CLAIM'
      and target_entity_id = p_claim_id
  ), related_ids as (
    select r.source_entity_id as claim_id
    from public.claim_relations r
    join anchors a
      on a.target_entity_type = r.target_entity_type
      and a.target_entity_id = r.target_entity_id
    where r.user_id = p_user_id and r.source_entity_type = 'CLAIM'
    union
    select r.target_entity_id
    from public.claim_relations r
    join anchors a
      on a.target_entity_type = r.source_entity_type
      and a.target_entity_id = r.source_entity_id
    where r.user_id = p_user_id and r.target_entity_type = 'CLAIM'
  )
  select c.* from public.claims c
  where c.user_id = p_user_id
    and c.id <> p_claim_id
    and c.id in (select claim_id from related_ids);
$$;

create or replace function public.create_resume_claim_correction(
  p_document_id uuid,
  p_user_id uuid,
  p_claim_id uuid,
  p_review_status public.claim_review_status,
  p_corrected_claim_text text
)
returns setof public.resume_claim_corrections
language plpgsql
set search_path = public
as $$
declare
  target_analysis_id uuid;
  next_correction_version integer;
  next_claim_version integer;
  original_claim public.claims%rowtype;
begin
  select c.* into original_claim
  from public.claims c
  join public.resume_analyses a on a.id = c.resume_analysis_id
  where c.id = p_claim_id
    and c.user_id = p_user_id
    and c.source_document_id = p_document_id
    and a.user_id = p_user_id
  for update of c;

  target_analysis_id := original_claim.resume_analysis_id;
  if target_analysis_id is null then
    raise exception 'resume claim not found';
  end if;

  select coalesce(max(version), 0) + 1 into next_correction_version
  from public.resume_claim_corrections where claim_id = p_claim_id;
  select coalesce(max(version), 0) + 1 into next_claim_version
  from public.claim_versions where claim_id = p_claim_id;

  insert into public.claim_versions (
    user_id, claim_id, version, previous_state, new_state, changed_by, reason
  ) values (
    p_user_id, p_claim_id, next_claim_version,
    jsonb_build_object('claim_text', original_claim.claim_text, 'status', upper(original_claim.status::text)),
    jsonb_strip_nulls(jsonb_build_object(
      'claim_text', original_claim.claim_text,
      'status', upper(original_claim.status::text),
      'review_status', p_review_status::text,
      'corrected_claim_text', p_corrected_claim_text
    )),
    'USER',
    case when p_review_status = 'CORRECT'
      then 'Candidate confirmed resume claim'
      else 'Candidate submitted a correction without overwriting the original claim' end
  );

  return query insert into public.resume_claim_corrections (
    user_id, resume_analysis_id, claim_id, version, review_status, corrected_claim_text
  ) values (
    p_user_id, target_analysis_id, p_claim_id, next_correction_version,
    p_review_status, p_corrected_claim_text
  ) returning *;
end;
$$;

revoke all on function public.build_claim_graph_for_resume_analysis(uuid, uuid)
  from public, anon, authenticated;
revoke all on function public.update_claim_status(
  uuid, uuid, public.claim_status, public.claim_changed_by, text
) from public, anon, authenticated;
revoke all on function public.create_claim_with_version(
  uuid, jsonb, public.claim_changed_by, text
) from public, anon, authenticated;
revoke all on function public.append_claim_version(
  uuid, uuid, jsonb, jsonb, public.claim_changed_by, text
) from public, anon, authenticated;
revoke all on function public.find_related_claims(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.build_claim_graph_for_resume_analysis(uuid, uuid)
  to service_role;
grant execute on function public.update_claim_status(
  uuid, uuid, public.claim_status, public.claim_changed_by, text
) to service_role;
grant execute on function public.create_claim_with_version(
  uuid, jsonb, public.claim_changed_by, text
) to service_role;
grant execute on function public.append_claim_version(
  uuid, uuid, jsonb, jsonb, public.claim_changed_by, text
) to service_role;
grant execute on function public.find_related_claims(uuid, uuid)
  to service_role;

commit;

