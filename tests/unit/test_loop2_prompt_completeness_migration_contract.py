from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UP = ROOT / "supabase/migrations/20261005210000_target_prompt_completeness.sql"
DOWN = ROOT / "supabase/rollbacks/20261005210000_target_prompt_completeness_down.sql"


def test_prompt_state_constraints_are_null_safe_and_trigger_is_installed_for_insert_update():
    sql = UP.read_text(encoding="utf-8").lower()
    assert "prompt_set_id is not null" in sql
    assert "expected_prompt_count is not null" in sql
    assert "drop trigger target_session_links_verify" in sql
    assert "before insert or update on public.target_session_links" in sql
    assert "old.prompt_set_state is distinct from 'pending'" in sql
    assert "new.prompt_set_state is distinct from 'complete'" in sql
    assert "expected_prompt_count is distinct from old.expected_prompt_count" in sql


def test_rollback_is_local_guarded_non_cascading_and_restores_base_functions():
    sql = DOWN.read_text(encoding="utf-8").lower()
    assert "lock table public.target_session_links" in sql
    assert "lock table public.generated_questions" in sql
    assert "raise exception" in sql
    assert "prompt_set_id is not null" in sql
    assert "create or replace function public.target_session_links_verify()" in sql
    assert "create or replace function public.target_session_links_write_once()" in sql
    assert "drop column prompt_set_state" in sql
    assert "drop column expected_prompt_count" in sql
    assert "cascade" not in sql


def test_prompt_sets_are_unique_and_questions_cannot_be_orphaned():
    sql = UP.read_text(encoding="utf-8").lower()
    assert "target_session_links_prompt_set_id_key unique (prompt_set_id)" in sql
    assert "generated_questions_prompt_set_id_fkey" in sql
    assert "references public.target_session_links (prompt_set_id) on delete cascade" in sql
    assert "duplicate prompt_set_id" in sql
    assert "orphan generated_questions" in sql


def test_completed_sets_are_immutable_and_question_writes_lock_link():
    sql = UP.read_text(encoding="utf-8").lower()
    assert "generated_questions_guard_link" in sql
    assert "for update" in sql
    assert "complete prompt set is immutable" in sql
    assert "before insert or delete on public.generated_questions" in sql
    assert "new.prompt_set_state is distinct from 'pending'" in sql
    assert "before insert or update on public.target_session_links" in sql


def test_rollback_drops_only_new_question_guard_and_set_constraints():
    sql = DOWN.read_text(encoding="utf-8").lower()
    assert "drop trigger generated_questions_guard_link" in sql
    assert "drop function public.generated_questions_guard_link()" in sql
    assert "drop constraint generated_questions_prompt_set_id_fkey" in sql
    assert "drop constraint target_session_links_prompt_set_id_key" in sql


def test_complete_prompt_guard_allows_parent_cascade_cleanup_but_blocks_direct_delete():
    sql = UP.read_text(encoding="utf-8").lower()
    assert "link_row.prompt_set_state = 'complete'" in sql
    assert "candidate_targets where id = link_row.candidate_target_id" in sql
    assert "sessions where id = link_row.session_id" in sql
    assert "interview_blueprints where id = link_row.blueprint_id" in sql
    assert "complete prompt set is immutable" in sql


def test_question_guard_uses_event_rows_and_rejects_unlinked_inserts():
    sql = UP.read_text(encoding="utf-8").lower()
    assert "if tg_op = 'delete' then set_id := old.prompt_set_id" in sql
    assert "else set_id := new.prompt_set_id" in sql
    assert "if not found and tg_op = 'delete' then return old" in sql
    assert "question insert requires a matching pending link" in sql


def test_prompt_manifest_is_private_and_controls_insert_completion_and_question_rows():
    sql = UP.read_text(encoding="utf-8").lower()
    assert "add column prompt_manifest jsonb" in sql
    assert "jsonb_typeof(prompt_manifest) = 'array'" in sql
    assert "and prompt_manifest is not null" in sql
    assert "prompt_manifest -> (new.position - 1)" in sql
    assert "to_jsonb(new) - array['id', 'user_id', 'created_at', 'provenance_class']::text[]" in sql
    assert "new.prompt_manifest is distinct from old.prompt_manifest" in sql
    assert "prompt-backed links must be created pending" in sql
    assert "prompt_manifest" in sql and "expected_prompt_count" in sql
    assert "revoke select on public.target_session_links from authenticated" in sql
    assert "grant select (session_id, user_id, candidate_target_id, blueprint_id, round_key, competency_key, prompt_set_id, created_at)" in sql
    assert "on public.target_session_links to authenticated" in sql
    assert "grant select (prompt_manifest)" not in sql


def test_generic_links_cannot_store_prompt_manifests_and_backfill_skips_them():
    sql = UP.read_text(encoding="utf-8").lower()
    assert "prompt_set_id is null and prompt_set_state = 'not_applicable' and expected_prompt_count is null" in sql
    assert "prompt_manifest is null" in sql
    assert "new.prompt_manifest is not null" in sql
    assert "where l.prompt_set_id is not null;" in sql
    assert "q.blueprint_id is distinct from l.blueprint_id" in sql
    assert "q.round_key is distinct from l.round_key" in sql


def test_rollback_removes_manifest_and_restores_table_select():
    sql = DOWN.read_text(encoding="utf-8").lower()
    assert "drop column prompt_manifest" in sql
    assert "revoke select (session_id" in sql
    assert "grant select on public.target_session_links to authenticated" in sql
