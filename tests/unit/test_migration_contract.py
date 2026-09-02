from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608290001_initial_schema.sql"
).read_text(encoding="utf-8")


def test_user_owned_tables_enable_rls() -> None:
    for table in (
        "sessions",
        "turns",
        "claims",
        "flags",
        "scores",
        "session_results",
        "assessment_disputes",
    ):
        assert f"alter table public.{table} enable row level security" in MIGRATION


def test_candidate_access_is_owner_scoped() -> None:
    assert "sessions_owner_all" in MIGRATION
    assert "s.user_id = auth.uid()" in MIGRATION
    assert "disputes_owner_all" in MIGRATION


def test_tpo_has_no_individual_evidence_policy() -> None:
    policy_lines = [
        line for line in MIGRATION.splitlines() if line.startswith("create policy")
    ]
    assert all("tpo" not in line.lower() for line in policy_lines)


def test_database_enforces_scored_evidence() -> None:
    assert "constraint scored_requires_evidence" in MIGRATION
    assert "cardinality(evidence_quotes) >= 1" in MIGRATION

