"""Practice story usage: additive, not backfilled, exact version and role, immutable history."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
MIGRATION = (MIGRATIONS / "202609240006_practice_story_usage.sql").read_text(encoding="utf-8")
SQL = re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", MIGRATION).lower())  # code only, not comments
TABLE = SQL[SQL.index("create table public.practice_story_usages"):SQL.index("create index")]


def test_it_is_additive_and_guesses_no_history() -> None:
    for destructive in ("drop table", "drop column", "truncate", "delete from", "alter column", "alter table public.sessions", "alter table public.stories"):
        assert destructive not in SQL
    assert "insert into public.practice_story_usages" not in SQL  # nothing is backfilled


def test_usage_points_at_the_exact_version_and_role() -> None:
    assert "story_version_id uuid not null references public.story_versions(id)" in TABLE
    assert "role_profile_id uuid references public.role_profiles(id) on delete set null" in TABLE
    assert "session_id uuid not null references public.sessions(id) on delete cascade" in TABLE
    assert "unique (session_id, story_id)" in TABLE and "unique (session_id, position)" in TABLE
    for copied in ("title", "situation", "actions", "outcome", "themes", "score"):
        assert f" {copied} " not in TABLE  # a reference, never a copy, never a grade


def test_every_link_is_checked_in_the_database() -> None:
    trigger = SQL[SQL.index("create or replace function public.practice_story_usages_verify"):]
    assert "from public.sessions where id = new.session_id and user_id = new.user_id" in trigger
    assert "user_id = new.user_id and archived_at is null" in trigger
    assert "where id = new.story_version_id and story_id = new.story_id and user_id = new.user_id" in trigger
    assert "new.role_profile_id is distinct from session_role" in trigger
    assert "before insert on public.practice_story_usages" in SQL


def test_usage_is_history() -> None:
    assert "before update on public.practice_story_usages" in SQL
    assert "practice story usage is immutable history" in SQL


def test_usage_is_private_and_written_only_by_the_backend() -> None:
    assert "alter table public.practice_story_usages enable row level security" in SQL
    assert "using (user_id = (select auth.uid()))" in SQL
    assert "revoke insert, update, delete on public.practice_story_usages from authenticated" in SQL


def test_it_sorts_after_role_framings() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("202609240005_story_role_framings.sql") < names.index("202609240006_practice_story_usage.sql")
