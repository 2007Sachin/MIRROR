from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608310002_authentication_profiles.sql"
).read_text(encoding="utf-8")


def test_profile_identity_is_auth_user_owned() -> None:
    assert "new.id" in MIGRATION
    assert "on conflict (id) do update" in MIGRATION
    assert "using (id = auth.uid())" in MIGRATION
    assert "with check (id = auth.uid())" in MIGRATION


def test_browser_can_only_update_full_name() -> None:
    assert "revoke update on public.profiles from authenticated" in MIGRATION
    assert "grant update (full_name) on public.profiles to authenticated" in MIGRATION


def test_profile_trigger_reconciles_auth_identity() -> None:
    assert (
        "after insert or update of email, raw_user_meta_data on auth.users" in MIGRATION
    )
    assert "set email = excluded.email" in MIGRATION

