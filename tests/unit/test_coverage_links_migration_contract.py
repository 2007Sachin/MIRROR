"""Coverage links: additive, private, backend-written, owner-checked, one choice per need and target."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
MIGRATION = (MIGRATIONS / "202610010003_coverage_links.sql").read_text(encoding="utf-8")
SQL = re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", MIGRATION).lower())
TABLE = SQL[SQL.index("create table public.coverage_links"):SQL.index("create index")]


def test_it_is_additive() -> None:
    for destructive in ("drop table", "drop column", "truncate", "delete from", "update public.", "alter column"):
        assert destructive not in SQL


def test_columns_and_owner_references() -> None:
    assert "user_id uuid not null references public.profiles(id) on delete cascade" in TABLE
    assert "role_profile_id uuid not null references public.role_profiles(id) on delete cascade" in TABLE
    assert "requirement_key text not null" in TABLE
    assert "evidence_item_id uuid null references public.evidence_items(id) on delete cascade" in TABLE
    assert "story_id uuid null references public.stories(id) on delete cascade" in TABLE
    assert "confirmed boolean not null default false" in TABLE
    assert "dismissed boolean not null default false" in TABLE


def test_a_link_has_one_target_cites_a_reason_and_is_never_both() -> None:
    assert "num_nonnulls(evidence_item_id, story_id) = 1" in TABLE
    assert "not (confirmed and dismissed)" in TABLE
    assert "not confirmed or reason is not null" in TABLE
    assert "reason in ('tool', 'outcome', 'decision', 'capability', 'confirmed')" in TABLE
    for text in ("score", "percent", "predict", "weight"):
        assert text not in SQL


def test_one_choice_per_need_and_target() -> None:
    assert "unique (user_id, role_profile_id, requirement_key, evidence_item_id)" in TABLE
    assert "unique (user_id, role_profile_id, requirement_key, story_id)" in TABLE


def test_role_item_and_story_must_be_the_owners() -> None:
    assert "select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id" in SQL
    assert "select 1 from public.evidence_items where id = new.evidence_item_id and user_id = new.user_id" in SQL
    assert "select 1 from public.stories where id = new.story_id and user_id = new.user_id" in SQL
    assert "before insert or update on public.coverage_links" in SQL


def test_rls_select_own_and_no_client_writes() -> None:
    assert "alter table public.coverage_links enable row level security" in SQL
    assert (
        "create policy coverage_links_select_own on public.coverage_links for select to authenticated "
        "using (user_id = (select auth.uid()))"
    ) in SQL
    assert "revoke all on public.coverage_links from anon" in SQL
    assert "revoke insert, update, delete on public.coverage_links from authenticated" in SQL
    assert "grant all on public.coverage_links to service_role" in SQL
    assert "to anon" not in SQL.replace("from anon", "")
    assert not re.search(r"grant (insert|update|delete|all)[^;]* to authenticated", SQL)


def test_it_sorts_after_career_evidence() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("202610010001_career_evidence.sql") < names.index("202610010003_coverage_links.sql")
