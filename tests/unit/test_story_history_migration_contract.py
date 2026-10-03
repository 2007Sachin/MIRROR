"""Story history and archive migration: additive, owner-scoped, and history is append-only."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
MIGRATION = (MIGRATIONS / "202609240004_story_history_archive.sql").read_text(encoding="utf-8")
SQL = re.sub(r"\s+", " ", MIGRATION.lower())


def test_it_is_additive_and_never_drops_or_deletes() -> None:
    for destructive in ("drop table", "drop column", "truncate", "delete from", "alter column"):
        assert destructive not in SQL
    assert "add column archived_at timestamptz" in SQL
    assert "add column current_version integer not null default 1" in SQL


def test_versions_are_ordered_per_story_and_owned() -> None:
    assert "create table public.story_versions" in SQL
    assert "story_id uuid not null references public.stories(id)" in SQL
    assert "user_id uuid not null references public.profiles(id)" in SQL
    assert "unique (story_id, version)" in SQL
    assert "create type public.story_change_reason as enum ('created', 'manual_edit', 'restored')" in SQL
    assert "story_versions_verify_ownership" in SQL


def test_existing_stories_get_a_first_version_without_being_changed() -> None:
    backfill = SQL[SQL.index("insert into public.story_versions"):SQL.index("create or replace function public.stories_track_version")]
    assert "from public.stories s" in backfill and "'created'" in backfill and "s.updated_at" in backfill
    assert "where not exists" in backfill
    assert "update public.stories" not in backfill
    # The backfill runs before the story triggers exist.
    assert SQL.index("insert into public.story_versions") < SQL.index("create trigger stories_record_version")


def test_history_is_written_by_the_database_and_never_rewritten() -> None:
    assert "before update on public.story_versions" in SQL and "immutable history" in SQL
    assert "after insert or update on public.stories" in SQL
    assert "is distinct from" in SQL  # unchanged content never creates a version


def test_versions_are_private_and_restore_is_service_only() -> None:
    assert "alter table public.story_versions enable row level security" in SQL
    assert "using (user_id = (select auth.uid()))" in SQL
    assert "revoke insert, update, delete on public.story_versions from authenticated" in SQL
    assert "revoke all on function public.restore_story_version(uuid, uuid, uuid) from public, anon, authenticated" in SQL
    assert "grant execute on function public.restore_story_version(uuid, uuid, uuid) to service_role" in SQL
    restore = SQL[SQL.index("create or replace function public.restore_story_version"):]
    assert "user_id = p_user_id and archived_at is null" in restore
    assert "id = p_version_id and story_id = p_story_id and user_id = p_user_id" in restore


def test_the_new_migration_sorts_after_the_stories_table() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("202609220001_candidate_stories.sql") < names.index("202609240004_story_history_archive.sql")
