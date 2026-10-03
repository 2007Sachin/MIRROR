"""Story improvement suggestions: additive, no backfill, exact links, no rewritten content."""

import re
from pathlib import Path

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"
MIGRATION = (MIGRATIONS / "202609240007_story_improvement_suggestions.sql").read_text(encoding="utf-8")
SQL = re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", MIGRATION).lower())
TABLE = SQL[SQL.index("create table public.story_improvement_suggestions"):SQL.index("create index")]


def test_it_is_additive_and_guesses_no_history() -> None:
    for destructive in ("drop table", "drop column", "truncate", "delete from", "alter table public.stories", "update public.stories"):
        assert destructive not in SQL
    assert "insert into public.story_improvement_suggestions" not in SQL


def test_a_suggestion_references_its_sources_and_holds_no_story_text() -> None:
    for link in ("usage_id uuid not null references public.practice_story_usages(id)",
                 "story_version_id uuid not null references public.story_versions(id)",
                 "source_observation_id uuid not null references public.skeptic_observations(id)",
                 "source_turn_id uuid not null references public.turns(id)"):
        assert link in TABLE
    assert "unique (session_id, source_turn_id, issue_type)" in TABLE
    for text in ("situation", " actions", "outcome text", "summary", "explanation", "rewrite", "score"):
        assert text not in TABLE


def test_only_parts_the_review_can_name_are_allowed() -> None:
    assert "issue_type in ('ownership_unclear', 'result_unsupported')" in TABLE
    assert "story_part in ('ownership', 'measurable_result')" in TABLE
    assert "status in ('open', 'accepted', 'dismissed')" in TABLE


def test_every_link_and_transition_is_checked() -> None:
    assert "before insert on public.story_improvement_suggestions" in SQL
    assert "u.role_profile_id is not distinct from new.role_profile_id" in SQL
    assert "t.speaker = 'candidate'" in SQL
    assert "only an open suggestion can be accepted or dismissed" in SQL
    assert "later.version > practised.version" in SQL


def test_private_and_backend_written() -> None:
    assert "alter table public.story_improvement_suggestions enable row level security" in SQL
    assert "revoke insert, update, delete on public.story_improvement_suggestions from authenticated" in SQL


def test_it_sorts_after_practice_usage() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert names.index("202609240006_practice_story_usage.sql") < names.index("202609240007_story_improvement_suggestions.sql")
