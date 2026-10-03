"""ABANDONED session status: additive enum value, terminal, reachable only before review."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
NAME = "202610010002_session_abandoned.sql"
SQL = re.sub(r"\s+", " ", (MIGRATIONS / NAME).read_text(encoding="utf-8").lower())


def test_it_is_additive() -> None:
    for destructive in ("drop table", "drop column", "drop type", "truncate", "delete from", "update public.sessions"):
        assert destructive not in SQL
    assert "alter type public.session_status add value if not exists 'abandoned'" in SQL


def test_the_new_value_is_committed_before_the_trigger_uses_it() -> None:
    # Postgres cannot use an enum value in the transaction that added it.
    assert SQL.index("add value if not exists 'abandoned'") < SQL.index("commit;") < SQL.index(
        "create or replace function public.enforce_session_lifecycle"
    )


def test_only_unfinished_sessions_can_be_abandoned_and_it_is_terminal() -> None:
    for source in ("created", "preparing", "ready", "active"):
        assert re.search(rf"old.status = '{source}' and new.status in \([^)]*'abandoned'", SQL), source
    for source in ("assessing",):
        clause = re.search(rf"old.status = '{source}' and new.status in \(([^)]*)\)", SQL)
        assert clause and "abandoned" not in clause.group(1)
    assert "old.status = 'abandoned' and" not in SQL  # nothing leaves ABANDONED
    assert "'failed', 'abandoned') and new.total_time_budget_seconds" in SQL


def test_the_matching_enum_case_is_used() -> None:
    engine = (MIGRATIONS / "202609010008_interview_session_engine.sql").read_text(encoding="utf-8")
    assert "add value if not exists 'COMPLETED'" in engine  # existing values are upper case
    assert "'ABANDONED'" in (MIGRATIONS / NAME).read_text(encoding="utf-8")


def test_the_new_migration_sorts_after_the_session_engine() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("202609010008_interview_session_engine.sql") < names.index(NAME)
