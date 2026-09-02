from pathlib import Path


ROOT = Path(__file__).parents[2]
MIGRATION = (
    ROOT / "supabase" / "migrations" / "202608310003_candidate_onboarding.sql"
).read_text(encoding="utf-8")


def test_onboarding_columns_and_default_are_migrated() -> None:
    for column in (
        "career_stage",
        "career_intent",
        "target_role",
        "interview_timeline",
        "preferred_language",
        "college_id",
        "onboarding_completed",
    ):
        assert f"add column if not exists {column}" in MIGRATION
    assert "onboarding_completed boolean not null default false" in MIGRATION


def test_completion_requires_required_profile_fields() -> None:
    assert "profiles_onboarding_completion_required_fields" in MIGRATION
    assert "career_stage is not null" in MIGRATION
    assert "preferred_language is not null" in MIGRATION


def test_language_is_preference_metadata_only() -> None:
    assert "public.preferred_language" in MIGRATION
    assert all(
        term not in MIGRATION.lower() for term in ("translation", "prompt", "agent")
    )

