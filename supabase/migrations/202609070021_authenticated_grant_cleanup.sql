begin;

-- Supabase's standard authenticated role should never write Mirror's durable
-- workflow state directly. Candidate mutations go through the owner-scoped API;
-- service-owned configuration, queues, and agent output remain service-role only.
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
  public.assessment_adjudications from authenticated;

-- These are the only relations exposed for candidate-owned, read-only access.
-- RLS policies on each table enforce ownership; the API owns all writes except
-- the deliberately narrow display-name edit below.
grant select on public.profiles, public.sessions, public.turns, public.claims,
  public.scores, public.session_results, public.assessment_disputes, public.outcomes,
  public.documents, public.resume_analyses, public.resume_claim_corrections,
  public.role_profiles, public.role_analysis_versions, public.role_competencies,
  public.claim_entities, public.claim_relations, public.claim_versions,
  public.claim_evidence, public.session_events, public.interview_plans,
  public.claim_resolutions to authenticated;
grant update (full_name) on public.profiles to authenticated;

commit;
