begin;

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
  select distinct user_id, 'SKILL'::public.claim_entity_type, trim(skill), '{}'::jsonb
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and nullif(trim(skill), '') is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'PROJECT'::public.claim_entity_type, trim(project_name), '{}'::jsonb
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and nullif(trim(project_name), '') is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'TOOL'::public.claim_entity_type, trim(tool), '{}'::jsonb
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and nullif(trim(tool), '') is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'OUTCOME'::public.claim_entity_type, trim(outcome), '{}'::jsonb
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and nullif(trim(outcome), '') is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct
    user_id,
    'METRIC'::public.claim_entity_type,
    trim(metric_value::text || coalesce(' ' || nullif(trim(metric_unit), ''), '')),
    jsonb_strip_nulls(jsonb_build_object('value', metric_value, 'unit', metric_unit))
  from public.claims
  where resume_analysis_id = p_analysis_id and user_id = p_user_id and metric_value is not null
  on conflict (user_id, entity_type, canonical_key) do nothing;

  insert into public.claim_entities (user_id, entity_type, canonical_name, metadata)
  select distinct user_id, 'RESPONSIBILITY'::public.claim_entity_type, trim(claim_text),
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

commit;
