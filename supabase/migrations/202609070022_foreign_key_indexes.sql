begin;

-- Cover the remaining foreign keys used by ownership joins, graph traversal,
-- cleanup cascades, and operational reporting. PostgreSQL does not create these
-- indexes automatically for referencing columns.
create index if not exists assessment_disputes_session_idx on public.assessment_disputes(session_id);
create index if not exists claim_evidence_user_idx on public.claim_evidence(user_id);
create index if not exists claim_resolutions_user_idx on public.claim_resolutions(user_id);
create index if not exists claim_versions_user_idx on public.claim_versions(user_id);
create index if not exists claims_contradicted_turn_idx on public.claims(contradicted_by_turn_id);
create index if not exists flags_interviewer_turn_idx on public.flags(interviewer_turn_id);
create index if not exists outcomes_linked_session_idx on public.outcomes(linked_session_id);
create index if not exists profiles_current_role_profile_idx on public.profiles(current_role_profile_id);
create index if not exists profiles_college_idx on public.profiles(college_id);
create index if not exists question_bank_role_idx on public.question_bank(role_id);
create index if not exists question_bank_skill_idx on public.question_bank(skill_id);
create index if not exists resume_claim_corrections_analysis_idx on public.resume_claim_corrections(resume_analysis_id);
create index if not exists resume_claim_corrections_user_idx on public.resume_claim_corrections(user_id);
create index if not exists role_analysis_versions_source_document_idx on public.role_analysis_versions(source_document_id);
create index if not exists role_analysis_versions_user_idx on public.role_analysis_versions(user_id);
create index if not exists role_competencies_role_profile_idx on public.role_competencies(role_profile_id);
create index if not exists role_competencies_user_idx on public.role_competencies(user_id);
create index if not exists role_profiles_current_analysis_idx on public.role_profiles(current_analysis_version_id);
create index if not exists role_profiles_source_document_idx on public.role_profiles(source_document_id);
create index if not exists rubrics_role_idx on public.rubrics(role_id);
create index if not exists scores_skill_idx on public.scores(skill_id);
create index if not exists session_events_user_idx on public.session_events(user_id);
create index if not exists skeptic_analyses_source_turn_idx on public.skeptic_analyses(source_turn_id);
create index if not exists skeptic_analyses_user_idx on public.skeptic_analyses(user_id);
create index if not exists skeptic_claim_proposals_claim_idx on public.skeptic_claim_update_proposals(claim_id);
create index if not exists skeptic_claim_proposals_reviewer_idx on public.skeptic_claim_update_proposals(reviewed_by);
create index if not exists skeptic_claim_proposals_source_turn_idx on public.skeptic_claim_update_proposals(source_turn_id);
create index if not exists skeptic_claim_proposals_user_idx on public.skeptic_claim_update_proposals(user_id);
create index if not exists skeptic_observations_source_turn_idx on public.skeptic_observations(source_turn_id);
create index if not exists skeptic_observations_user_idx on public.skeptic_observations(user_id);
create index if not exists tts_audio_cache_session_idx on public.tts_audio_cache(session_id);
create index if not exists turns_parent_question_idx on public.turns(parent_question_id);
create index if not exists voice_turn_metrics_candidate_turn_idx on public.voice_turn_metrics(candidate_turn_id);
create index if not exists voice_turn_metrics_interviewer_turn_idx on public.voice_turn_metrics(interviewer_turn_id);
create index if not exists voice_turn_requests_candidate_turn_idx on public.voice_turn_requests(candidate_turn_id);
create index if not exists voice_turn_requests_interviewer_turn_idx on public.voice_turn_requests(interviewer_turn_id);

commit;
