-- 202609070020 revoked anon from Mirror's tables by explicit list. Tables created after it
-- inherited Supabase's default grant to anon. RLS still returned no rows, but anon could see
-- and query them; Mirror's tables are candidate-owned and never anonymous.
-- Idempotent and non-destructive: only removes a privilege nothing uses.
begin;

revoke all on public.stories, public.story_versions, public.story_role_framings,
  public.practice_story_usages, public.story_improvement_suggestions,
  public.pressure_test_responses, public.answer_attempts,
  public.dig_deeper_responses from anon;

commit;
