from pathlib import Path
import re

ROOT = Path(__file__).parents[2]
MIG = ROOT / "supabase/migrations/20261008230000_loop5a_candidate_stages.sql"
DOWN = ROOT / "supabase/rollbacks/20261008230000_loop5a_candidate_stages_down.sql"
SQL = re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", MIG.read_text(encoding="utf-8") if MIG.exists() else "").lower())


def test_additive_stage_contract_has_bounded_exact_shape_and_safe_legacy_defaults():
    for col in ("candidate_stage_state", "candidate_stage_order_known", "candidate_stages", "candidate_stage_mapping_version", "candidate_stage_notes_revision"):
        assert col in SQL
    assert "jsonb_object_keys" in SQL and "stage_id" in SQL
    assert "jsonb_array_length" in SQL and "between 1 and 12" in SQL
    assert "candidate_stage_mapping_version integer not null default 0" in SQL


def test_private_current_only_notes_and_owner_integrity():
    assert "create table public.candidate_stage_notes" in SQL
    assert "enable row level security" in SQL
    assert "candidate_stage_notes" in SQL and "foreign key (candidate_target_id,user_id)" in SQL
    assert "grant all on public.candidate_stage_notes to service_role" not in SQL
    assert re.search(r"revoke all on public\.candidate_stage_notes from public, anon, authenticated", SQL)


def test_service_rpcs_lock_targets_validate_compare_and_swap_and_preserve_pins():
    for f in ("append_target_blueprint_pin", "save_candidate_stage_plan", "read_candidate_stage_plan"):
        assert f"function public.{f}" in SQL
        assert f"revoke all on function public.{f}" in SQL
        assert f"grant execute on function public.{f}" in SQL and "to service_role" in SQL
    assert SQL.count("for update") >= 2
    assert "security definer" in SQL and "set search_path = pg_catalog, public" in SQL
    assert "candidate_stage_notes_revision" in SQL
    start = SQL.index("create or replace function public.save_candidate_stage_plan")
    end = SQL.index("create or replace function public.read_candidate_stage_plan", start)
    save_rpc = SQL[start:end]
    assert "auth.role() is distinct from 'service_role'" in save_rpc
    assert "current_user" not in save_rpc
    assert "p_expected_version is null or p_expected_version < 0" in save_rpc


def test_initial_mapping_pin_and_atomic_reader_preserve_full_blueprint():
    append_start = SQL.index("create or replace function public.append_target_blueprint_pin")
    save_start = SQL.index("create or replace function public.save_candidate_stage_plan", append_start)
    append_rpc = SQL[append_start:save_start]
    assert "case when b.id is null then 1 else b.candidate_stage_mapping_version end" in append_rpc
    read_start = SQL.index("create or replace function public.read_candidate_stage_plan")
    read_end = SQL.index("revoke all on function public.validate_candidate_stages", read_start)
    read_rpc = SQL[read_start:read_end]
    assert "to_jsonb(b)" in read_rpc
    assert "for share" in read_rpc and "from public.candidate_targets" in read_rpc


def test_append_rpc_validates_research_pin_at_the_database_boundary():
    start = SQL.index("create or replace function public.append_target_blueprint_pin")
    end = SQL.index("create or replace function public.save_candidate_stage_plan", start)
    append_rpc = SQL[start:end]
    assert "p_catalog_version is null or p_catalog_version < 1" in append_rpc
    assert "p_catalog_sha256 is null or p_catalog_sha256 !~ '^[0-9a-f]{64}$'" in append_rpc
    assert "p_match_state is null or p_match_state not in ('researched','general_only','not_researched')" in append_rpc
    assert "p_rules_version is null or char_length(btrim(p_rules_version)) not between 1 and 40" in append_rpc


def test_stage_validator_rejects_null_order_and_order_on_empty_states():
    start = SQL.index("create or replace function public.validate_candidate_stages")
    end = SQL.index("create table public.candidate_stage_notes", start)
    validator = SQL[start:end]
    assert "p_state is null or p_order_known is null" in validator
    assert "p_state <> 'known' and p_order_known" in validator
    assert "candidate_stage_state in ('not_asked','not_yet') and jsonb_array_length(candidate_stages) = 0 and not candidate_stage_order_known" in SQL
    assert "candidate_stage_notes_revision = 0" in SQL
    assert "char_length(x->>'sequence') > 2" in validator


def test_archive_clears_notes_and_no_blueprint_update_or_session_link_changes():
    assert "candidate_targets" in SQL and "archived" in SQL and "delete from public.candidate_stage_notes" in SQL
    start = SQL.index("create or replace function public.candidate_stage_notes_archive_cleanup")
    end = SQL.index("create trigger candidate_stage_notes_archive_cleanup", start)
    archive = SQL[start:end]
    assert "security definer" in archive
    assert "set search_path = pg_catalog, public" in archive
    assert "revoke all on function public.candidate_stage_notes_archive_cleanup() from public,anon,authenticated,service_role" in SQL
    assert "create or replace function public.interview_blueprints_guard" not in SQL
    assert "target_session_links" not in SQL


def test_rollback_is_guarded_restrictive_and_restores_base_blueprint_guard():
    down = DOWN.read_text(encoding="utf-8").lower()
    assert "rollback refused" in down and "candidate_stage_notes" in down
    assert "drop table public.candidate_stage_notes restrict" in down
    assert "cascade" not in down
    assert "create or replace function public.interview_blueprints_guard" not in down


def test_append_pin_uses_version_cas_monotonicity_and_full_pin_idempotency():
    start = SQL.index("create or replace function public.append_target_blueprint_pin")
    end = SQL.index("create or replace function public.save_candidate_stage_plan", start)
    rpc = SQL[start:end]
    assert "p_expected_version integer,p_catalog_version integer" in rpc
    assert "stale blueprint pin" in rpc
    assert "p_catalog_version < b.catalog_version" in rpc
    assert "p_catalog_version = b.catalog_version and b.catalog_sha256 is distinct from p_catalog_sha256" in rpc
    assert "b.catalog_version=p_catalog_version and b.catalog_sha256=p_catalog_sha256 and b.match_state=p_match_state and b.rules_version=p_rules_version" in rpc


def test_reader_returns_locked_latest_version_for_historical_and_current_reads():
    start = SQL.index("create or replace function public.read_candidate_stage_plan")
    end = SQL.index("revoke all on function public.validate_candidate_stages", start)
    rpc = SQL[start:end]
    assert "latest_version" in rpc
    assert "order by version desc limit 1" in rpc
    assert "for share" in rpc
