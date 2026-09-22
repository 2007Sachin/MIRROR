-- Practice modes: a session can be a full interview, a focused practice or a quick drill.
-- Additive. Existing rows become FULL_INTERVIEW, which is exactly what they were.
-- Deploy this before the API that selects these columns (repository.SESSION_READ_COLUMNS).
begin;

create type public.practice_mode as enum ('FULL_INTERVIEW', 'FOCUSED_PRACTICE', 'QUICK_DRILL');

alter table public.sessions
  add column practice_mode public.practice_mode not null default 'FULL_INTERVIEW',
  add column practice_focus text,
  add column practice_theme text;

alter table public.sessions
  add constraint sessions_practice_focus_known check (
    practice_focus is null
    or practice_focus in ('full', 'story', 'project', 'decisions', 'impact', 'disagreement', 'setback', 'analytics', 'role')
  ),
  -- A short practice always has one area to work on.
  add constraint sessions_short_practice_has_focus check (
    practice_mode = 'FULL_INTERVIEW' or (practice_focus is not null and practice_focus <> 'full')
  ),
  add constraint sessions_practice_theme_length check (
    practice_theme is null or char_length(trim(practice_theme)) between 2 and 300
  );

commit;
