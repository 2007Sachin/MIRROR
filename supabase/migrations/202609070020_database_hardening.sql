begin;

-- Auth trigger functions run only as triggers. They must not be callable via RPC.
revoke all on function public.handle_new_user() from public, anon, authenticated;

alter function public.evidence_normalize(text) set search_path = pg_catalog;

-- Repair the fresh-install enum comparison from the evidence migration.
create or replace function public.insert_validated_claim_evidence(
  p_claim_id uuid, p_user_id uuid, p_source_type text, p_source_id uuid,
  p_turn_id uuid, p_document_id uuid, p_quote_text text,
  p_direction text, p_strength text, p_reason_code text,
  p_execution_id uuid, p_model text, p_prompt_version text
)
returns boolean
language plpgsql security definer set search_path = public
as $$
declare source_text text; key_value text; inserted_count integer;
begin
  if not exists (select 1 from public.claims where id = p_claim_id and user_id = p_user_id) then
    return false;
  end if;
  if p_source_type in ('CANDIDATE_TURN','INTERVIEWER_TURN') then
    select t.text into source_text from public.turns t join public.sessions s on s.id=t.session_id
    where t.id=p_source_id and t.id=p_turn_id and s.user_id=p_user_id
      and ((p_source_type='CANDIDATE_TURN' and t.speaker='candidate')
        or (p_source_type='INTERVIEWER_TURN' and t.speaker='interviewer'));
  elsif p_source_type in ('RESUME','OTHER_DOCUMENT') then
    select d.raw_text into source_text from public.documents d
    where d.id=p_source_id and d.id=p_document_id and d.user_id=p_user_id
      and (p_source_type<>'RESUME' or d.document_type='RESUME');
  else
    return false;
  end if;
  if source_text is null or position(public.evidence_normalize(p_quote_text) in public.evidence_normalize(source_text)) = 0 then
    return false;
  end if;
  key_value := encode(digest(
    p_source_type || ':' || p_source_id::text || ':' || public.evidence_normalize(p_quote_text) || ':' || p_direction,
    'sha256'), 'hex');
  insert into public.claim_evidence (
    user_id, claim_id, evidence_type, source_type, source_id, turn_id, document_id,
    quote_text, evidence_direction, strength, evidence_strength, reason_code, agent_model,
    prompt_version, evidence_execution_id, validated, evidence_key
  ) values (
    p_user_id, p_claim_id,
    case when p_turn_id is not null then 'INTERVIEW_TURN'::public.claim_evidence_type else 'DOCUMENT_EXCERPT'::public.claim_evidence_type end,
    p_source_type, p_source_id, p_turn_id, p_document_id, p_quote_text,
    p_direction::public.evidence_direction,
    case p_strength when 'NONE' then 0 when 'WEAK' then 0.25 when 'MODERATE' then 0.65 else 1 end,
    p_strength, p_reason_code, p_model, p_prompt_version, p_execution_id, true, key_value
  ) on conflict (claim_id, evidence_key) where evidence_key is not null and validated = true do nothing;
  get diagnostics inserted_count = row_count;
  return inserted_count = 1;
end;
$$;

revoke all on function public.insert_validated_claim_evidence(uuid,uuid,text,uuid,uuid,uuid,text,text,text,text,uuid,text,text)
  from public, anon, authenticated;
grant execute on function public.insert_validated_claim_evidence(uuid,uuid,text,uuid,uuid,uuid,text,text,text,text,uuid,text,text)
  to service_role;

alter table public.jobs add column if not exists updated_at timestamptz not null default now();
drop trigger if exists jobs_set_updated_at on public.jobs;
create trigger jobs_set_updated_at before update on public.jobs
  for each row execute procedure public.set_updated_at();

alter table public.documents add column if not exists updated_at timestamptz not null default now();
drop trigger if exists documents_set_updated_at on public.documents;
create trigger documents_set_updated_at before update on public.documents
  for each row execute procedure public.set_updated_at();

-- Foreign keys used for joins, ownership checks, or cascading deletes.
create index if not exists assessment_disputes_user_session_idx on public.assessment_disputes(user_id, session_id);
create index if not exists claim_evidence_document_idx on public.claim_evidence(document_id) where document_id is not null;
create index if not exists claim_evidence_turn_idx on public.claim_evidence(turn_id) where turn_id is not null;
create index if not exists flags_claim_idx on public.flags(claim_id) where claim_id is not null;
create index if not exists flags_source_turn_idx on public.flags(source_turn_id) where source_turn_id is not null;
create index if not exists model_events_turn_idx on public.model_events(turn_id) where turn_id is not null;
create index if not exists outcomes_user_created_idx on public.outcomes(user_id, created_at desc);
create index if not exists scores_session_created_idx on public.scores(session_id, created_at desc);
create index if not exists voice_turn_metrics_user_idx on public.voice_turn_metrics(user_id, created_at desc);

-- Prevent pre-authenticated discovery of every Mirror table through Data/GraphQL APIs.
revoke all on public.colleges, public.profiles, public.roles, public.skills,
  public.sessions, public.turns, public.claims, public.flags, public.rubrics,
  public.scores, public.session_results, public.assessment_disputes, public.jobs,
  public.model_events, public.golden_cases, public.calibration_runs, public.outcomes,
  public.question_bank, public.question_reports, public.documents,
  public.session_document_links, public.resume_analyses,
  public.resume_claim_corrections, public.role_profiles,
  public.role_analysis_versions, public.role_competencies, public.claim_entities,
  public.claim_relations, public.claim_versions, public.claim_evidence,
  public.session_events, public.interview_plans, public.voice_turn_requests,
  public.tts_audio_cache, public.voice_turn_metrics, public.skeptic_observations,
  public.skeptic_claim_update_proposals, public.skeptic_analyses,
  public.claim_resolutions, public.specialist_assessments,
  public.assessment_adjudications from anon;

-- Candidate-facing reads remain ownership-scoped by RLS. Writes are API-owned,
-- except the deliberately narrow profile display-name update.
revoke all on public.profiles, public.sessions, public.turns, public.claims,
  public.scores, public.session_results, public.assessment_disputes, public.outcomes,
  public.documents, public.resume_analyses, public.resume_claim_corrections,
  public.role_profiles, public.role_analysis_versions, public.role_competencies,
  public.claim_entities, public.claim_relations, public.claim_versions,
  public.claim_evidence, public.session_events, public.interview_plans,
  public.claim_resolutions from authenticated;
grant select on public.profiles, public.sessions, public.turns, public.claims,
  public.scores, public.session_results, public.assessment_disputes, public.outcomes,
  public.documents, public.resume_analyses, public.resume_claim_corrections,
  public.role_profiles, public.role_analysis_versions, public.role_competencies,
  public.claim_entities, public.claim_relations, public.claim_versions,
  public.claim_evidence, public.session_events, public.interview_plans,
  public.claim_resolutions to authenticated;
grant update (full_name) on public.profiles to authenticated;

alter policy profiles_select_own on public.profiles to authenticated using (id = (select auth.uid()));
alter policy profiles_update_own on public.profiles to authenticated
  using (id = (select auth.uid())) with check (id = (select auth.uid()));
alter policy sessions_owner_all on public.sessions to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
alter policy turns_owner_read on public.turns to authenticated using (
  exists (select 1 from public.sessions s where s.id = turns.session_id and s.user_id = (select auth.uid()))
);
alter policy claims_owner_read on public.claims to authenticated using (user_id = (select auth.uid()));
alter policy scores_owner_read on public.scores to authenticated using (
  exists (select 1 from public.sessions s where s.id = scores.session_id and s.user_id = (select auth.uid()))
);
alter policy results_owner_read on public.session_results to authenticated using (
  exists (select 1 from public.sessions s where s.id = session_results.session_id and s.user_id = (select auth.uid()))
);
alter policy disputes_owner_all on public.assessment_disputes to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
alter policy outcomes_owner_read on public.outcomes to authenticated using (user_id = (select auth.uid()));
alter policy documents_select_own on public.documents to authenticated using (user_id = (select auth.uid()));
alter policy resume_analyses_select_own on public.resume_analyses to authenticated using (user_id = (select auth.uid()));
alter policy resume_claim_corrections_select_own on public.resume_claim_corrections to authenticated using (user_id = (select auth.uid()));
alter policy role_profiles_select_own on public.role_profiles to authenticated using (user_id = (select auth.uid()));
alter policy role_analysis_versions_select_own on public.role_analysis_versions to authenticated using (user_id = (select auth.uid()));
alter policy role_competencies_select_own on public.role_competencies to authenticated using (user_id = (select auth.uid()));
alter policy claim_entities_select_own on public.claim_entities to authenticated using (user_id = (select auth.uid()));
alter policy claim_relations_select_own on public.claim_relations to authenticated using (user_id = (select auth.uid()));
alter policy claim_versions_select_own on public.claim_versions to authenticated using (user_id = (select auth.uid()));
alter policy claim_evidence_select_own on public.claim_evidence to authenticated using (user_id = (select auth.uid()));
alter policy session_events_select_own on public.session_events to authenticated using (user_id = (select auth.uid()));
alter policy interview_plans_select_own on public.interview_plans to authenticated using (user_id = (select auth.uid()));
alter policy claim_resolutions_select_own on public.claim_resolutions to authenticated using (user_id = (select auth.uid()));

-- Storage remains private. Direct candidate reads are restricted to their own
-- first path segment; all writes continue through the owner-scoped API.
drop policy if exists mirror_candidate_storage_read on storage.objects;
create policy mirror_candidate_storage_read on storage.objects
  for select to authenticated
  using (
    bucket_id in ('private-resumes', 'private-interview-audio')
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

commit;
