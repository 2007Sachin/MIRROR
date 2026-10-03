"""Career evidence items: additive, private, backend-written, owner-checked, idempotent per source."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
MIGRATION = (MIGRATIONS / "202610010001_career_evidence.sql").read_text(encoding="utf-8")
SQL = re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", MIGRATION).lower())
TABLE = SQL[SQL.index("create table public.evidence_items"):SQL.index("create index")]


def test_it_is_additive() -> None:
    for destructive in ("drop table", "drop column", "truncate", "delete from", "update public.", "alter column"):
        assert destructive not in SQL


def test_one_item_per_person_and_source() -> None:
    assert "user_id uuid not null references public.profiles(id) on delete cascade" in TABLE
    assert "source_key text not null" in TABLE
    assert "unique (user_id, source_key)" in TABLE
    assert "source_document_id uuid null references public.documents(id) on delete set null" in TABLE


def test_kinds_and_statuses_are_closed_sets() -> None:
    assert "kind in ('achievement', 'project', 'responsibility', 'skill')" in TABLE
    assert "status in ('pending', 'approved', 'removed')" in TABLE
    assert "default 'pending'" in TABLE
    assert "edited boolean not null default false" in TABLE
    assert "tools text[] not null default '{}'" in TABLE
    for text in ("score", "percent", "predict", "weight"):
        assert text not in SQL


def test_merges_stay_inside_one_persons_items() -> None:
    assert "merged_into uuid null references public.evidence_items(id) on delete set null" in TABLE
    assert "merged_into <> id" in TABLE
    assert "select 1 from public.evidence_items where id = new.merged_into and user_id = new.user_id" in SQL
    assert "select 1 from public.documents where id = new.source_document_id and user_id = new.user_id" in SQL
    assert "before insert or update on public.evidence_items" in SQL


def test_rls_select_own_and_no_client_writes() -> None:
    assert "alter table public.evidence_items enable row level security" in SQL
    assert (
        "create policy evidence_items_select_own on public.evidence_items for select to authenticated "
        "using (user_id = (select auth.uid()))"
    ) in SQL
    assert "revoke all on public.evidence_items from anon" in SQL
    assert "revoke insert, update, delete on public.evidence_items from authenticated" in SQL
    assert "grant all on public.evidence_items to service_role" in SQL
    assert "to anon" not in SQL.replace("from anon", "")
    assert not re.search(r"grant (insert|update|delete|all)[^;]* to authenticated", SQL)


def test_it_sorts_last() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("202609300001_interview_events.sql") < names.index("202610010001_career_evidence.sql")
