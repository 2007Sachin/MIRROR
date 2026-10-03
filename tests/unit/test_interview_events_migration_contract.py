"""Interview events + debriefs: additive, private, backend-written, owner-checked."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
MIGRATION = (MIGRATIONS / "202609300001_interview_events.sql").read_text(encoding="utf-8")
SQL = re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", MIGRATION).lower())
TABLES = ("interview_events", "interview_debriefs")


def test_it_is_additive() -> None:
    for destructive in ("drop table", "drop column", "truncate", "delete from", "update public."):
        assert destructive not in SQL


def test_rls_select_own_and_no_client_writes() -> None:
    for table in TABLES:
        assert f"alter table public.{table} enable row level security" in SQL
        assert f"create policy {table}_select_own on public.{table} for select to authenticated using (user_id = (select auth.uid()))" in SQL
    assert "revoke all on public.interview_events, public.interview_debriefs from anon" in SQL
    assert "revoke insert, update, delete on public.interview_events, public.interview_debriefs from authenticated" in SQL
    assert "grant all on public.interview_events, public.interview_debriefs to service_role" in SQL
    assert "to anon" not in SQL.replace("from anon", "")
    assert not re.search(r"grant (insert|update|delete|all)[^;]* to authenticated", SQL)


def test_ownership_triggers() -> None:
    assert "select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id" in SQL
    assert "select 1 from public.interview_events where id = new.interview_event_id and user_id = new.user_id" in SQL
    for table in TABLES:
        assert f"before insert or update on public.{table}" in SQL


def test_one_debrief_per_event_and_bounded_text() -> None:
    assert "unique (interview_event_id)" in SQL
    assert "references public.interview_events(id) on delete cascade" in SQL
    assert "cardinality(questions_asked) <= 15" in SQL
    assert "char_length(q) between 1 and 500" in SQL
    assert "char_length(notes) <= 2000" in SQL
    assert "char_length(company_label) <= 120" in SQL
    for text in ("score", "percent", "predict"):
        assert text not in SQL


def test_it_sorts_last() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("202609250001_revoke_anon_new_tables.sql") < names.index("202609300001_interview_events.sql")
