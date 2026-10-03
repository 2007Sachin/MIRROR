"""Story role framings: additive, exact-id, owner-checked, and never a copy of the story."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
MIGRATION = (MIGRATIONS / "202609240005_story_role_framings.sql").read_text(encoding="utf-8")
SQL = re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", MIGRATION).lower())  # code only, not comments
TABLE = SQL[SQL.index("create table public.story_role_framings"):SQL.index("create index")]


def test_it_is_additive() -> None:
    for destructive in ("drop table", "drop column", "truncate", "delete from", "alter column", "alter table public.stories"):
        assert destructive not in SQL


def test_one_framing_per_story_and_exact_role() -> None:
    assert "story_id uuid not null references public.stories(id) on delete cascade" in TABLE
    assert "role_profile_id uuid not null references public.role_profiles(id) on delete cascade" in TABLE
    assert "unique (story_id, role_profile_id)" in TABLE
    assert "target_role" not in SQL  # roles are never matched by name


def test_a_framing_holds_no_story_content() -> None:
    for part in ("situation", "ownership", "actions", "reasoning", "trade_offs", "outcome", "measurable_result", "learning", "do_differently", "title"):
        assert f" {part} " not in TABLE
    assert "themes text[]" in TABLE and "emphasis text" in TABLE


def test_story_and_role_must_share_the_owner() -> None:
    trigger = SQL[SQL.index("create or replace function public.story_role_framings_verify_ownership"):]
    assert "from public.stories where id = new.story_id and user_id = new.user_id" in trigger
    assert "from public.role_profiles where id = new.role_profile_id and user_id = new.user_id" in trigger
    assert "cannot move to another story or role" in trigger


def test_existing_roles_are_backfilled_including_archived_stories() -> None:
    backfill = SQL[SQL.index("insert into public.story_role_framings"):SQL.index("create or replace function public.stories_frame_originating_role")]
    assert "where s.role_profile_id is not null" in backfill
    assert "archived_at" not in backfill  # archived stories keep their role too
    assert "r.user_id = s.user_id" in backfill
    assert "on conflict (story_id, role_profile_id) do nothing" in backfill


def test_new_stories_keep_the_role_they_were_written_for() -> None:
    assert "after insert on public.stories" in SQL
    assert "story_versions" not in SQL  # framing never touches story history


def test_framings_are_private_and_written_only_by_the_backend() -> None:
    assert "alter table public.story_role_framings enable row level security" in SQL
    assert "using (user_id = (select auth.uid()))" in SQL
    assert "revoke insert, update, delete on public.story_role_framings from authenticated" in SQL


def test_it_sorts_after_story_history() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("202609240004_story_history_archive.sql") < names.index("202609240005_story_role_framings.sql")
