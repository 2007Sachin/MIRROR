"""Loop 2 owner-scoped target tables: additive, private, backend-written, owner-checked.

Static contract for supabase/migrations/20261004200000_loop2_candidate_targets.sql.
Runtime RLS/grant behaviour is exercised separately against a disposable local PostgreSQL 16.
"""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
NAME = "20261004200000_loop2_candidate_targets.sql"
MIGRATION = (MIGRATIONS / NAME).read_text(encoding="utf-8")
SQL = re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", MIGRATION).lower())

TABLES = ("candidate_targets", "interview_blueprints", "target_session_links", "generated_questions")
OWNER_TABLES = {"profiles", "role_profiles", "sessions", *TABLES}
EXISTING_TABLES = (
    "profiles", "role_profiles", "sessions", "turns", "interview_plans", "session_results",
    "stories", "evidence_items", "coverage_links", "answer_attempts", "practice_story_usage",
)


def _table(name: str) -> str:
    start = SQL.index(f"create table public.{name} (")
    return SQL[start:SQL.index(");", start)]


def test_it_sorts_after_every_existing_migration() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("20261004121203_retire_verified_nutrition_tables.sql") < names.index(NAME)


def test_it_is_additive_and_leaves_existing_tables_alone() -> None:
    assert SQL.strip().startswith("begin;") and SQL.strip().endswith("commit;")
    for destructive in ("drop ", "truncate", "delete from", "update public.", "alter column", "rename"):
        assert destructive not in SQL, destructive
    for existing in EXISTING_TABLES:
        assert f"alter table public.{existing} " not in SQL
        assert f"create table public.{existing} " not in SQL
    altered = set(re.findall(r"alter table public\.(\w+)", SQL))
    assert altered == set(TABLES)
    assert set(re.findall(r"create table public\.(\w+)", SQL)) == set(TABLES)


def test_every_table_is_owned_and_cascades_with_the_owner() -> None:
    for table in TABLES:
        assert "user_id uuid not null references public.profiles(id) on delete cascade" in _table(table), table


def test_foreign_keys_restrict_into_anything_not_owner_scoped() -> None:
    references = re.findall(r"references public\.(\w+)\(id\)(?: on delete (\w+(?: \w+)?))?", SQL)
    assert references
    for target, action in references:
        if target not in OWNER_TABLES:
            assert action == "restrict", (target, action)
    assert "intel_" not in SQL  # curated research stays in the repo catalog, not the database


def test_rls_select_own_and_no_client_writes() -> None:
    for table in TABLES:
        assert f"alter table public.{table} enable row level security" in SQL
        assert (
            f"create policy {table}_select_own on public.{table} for select to authenticated "
            "using (user_id = (select auth.uid()))"
        ) in SQL
        assert f"revoke all on public.{table} from public, anon, authenticated" in SQL
        assert f"grant select on public.{table} to authenticated" in SQL
        assert f"grant all on public.{table} to service_role" in SQL
    assert not re.search(r"grant [^;]* to [^;]*\banon\b", SQL)
    assert not re.search(r"grant (?:insert|update|delete|truncate|references|trigger|all)[^;]* to authenticated", SQL)
    assert not re.search(r"create policy \w+ on public\.\w+ for (?:insert|update|delete|all)", SQL)
    assert SQL.count("create policy") == len(TABLES)


def test_trigger_functions_are_private_and_pinned() -> None:
    functions = re.findall(r"create or replace function public\.(\w+)\(\)", SQL)
    assert functions
    assert "security definer" not in SQL
    for function in functions:
        assert f"revoke all on function public.{function}() from public, anon, authenticated" in SQL
    assert SQL.count("set search_path = public") == len(functions)


def test_targets_check_role_ownership_and_keep_scope_immutable() -> None:
    table = _table("candidate_targets")
    assert "role_profile_id uuid not null references public.role_profiles(id) on delete cascade" in table
    for column in ("company_label text not null", "role_family_key text not null", "level_key text null",
                   "geography_key text null", "interview_date date null"):
        assert column in table, column
    assert "status in ('active', 'archived')" in table
    assert "select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id" in SQL
    assert "target scope is immutable" in SQL
    assert "an archived target cannot be reactivated" in SQL
    assert "create unique index candidate_targets_one_active_scope_idx" in SQL


def test_blueprints_pin_a_catalog_version_and_hash() -> None:
    table = _table("interview_blueprints")
    assert "candidate_target_id uuid not null references public.candidate_targets(id) on delete cascade" in table
    assert "catalog_version integer not null check (catalog_version >= 1)" in table
    assert "catalog_sha256 text not null check (catalog_sha256 ~ '^[0-9a-f]{64}$')" in table
    assert "match_state in ('researched', 'general_only', 'not_researched')" in table
    assert "select 1 from public.candidate_targets where id = new.candidate_target_id and user_id = new.user_id" in SQL
    assert "a blueprint pin is immutable" in SQL


def test_session_links_are_write_once_and_owner_checked() -> None:
    table = _table("target_session_links")
    assert "session_id uuid primary key references public.sessions(id) on delete cascade" in table
    assert "select 1 from public.sessions where id = new.session_id and user_id = new.user_id" in SQL
    assert "a session link is write-once" in SQL
    assert "before update on public.target_session_links" in SQL


def test_generated_questions_are_mirror_generated_unique_and_immutable() -> None:
    table = _table("generated_questions")
    assert "provenance_class text not null default 'mirror_generated' check (provenance_class = 'mirror_generated')" in table
    assert "novelty_sha256 text not null check (novelty_sha256 ~ '^[0-9a-f]{64}$')" in table
    assert "char_length(trim(question_text)) between 20 and 400" in table
    assert "unique (user_id, candidate_target_id, novelty_sha256)" in table
    assert "generated questions are immutable" in SQL


def test_no_scoring_columns() -> None:
    for word in ("score", "percent", "predict", "weight", "grade", "points"):
        assert word not in SQL, word
