from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608310004_document_ingestion.sql"
).read_text(encoding="utf-8")
LIFECYCLE = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202609100001_evidence_library_lifecycle.sql"
).read_text(encoding="utf-8")


def test_documents_table_has_required_contract() -> None:
    assert "create table public.documents" in MIGRATION
    for column in (
        "user_id",
        "document_type",
        "storage_path",
        "original_filename",
        "mime_type",
        "raw_text",
        "status",
        "error_message",
        "created_at",
        "processed_at",
    ):
        assert column in MIGRATION


def test_document_rls_is_owner_scoped() -> None:
    assert "alter table public.documents enable row level security" in MIGRATION
    assert "documents_select_own" in MIGRATION
    assert "user_id = auth.uid()" in MIGRATION
    assert (
        "revoke insert, update, delete on public.documents from authenticated"
        in MIGRATION
    )


def test_session_links_protect_referenced_documents() -> None:
    assert "create table public.session_document_links" in MIGRATION
    assert "references public.documents(id) on delete cascade" in MIGRATION


def test_evidence_lifecycle_adds_one_taxonomy_and_recoverable_archive() -> None:
    assert "create type public.evidence_category" in LIFECYCLE
    for category in (
        "RESUME",
        "PROJECT",
        "CASE_STUDY",
        "CERTIFICATE",
        "PORTFOLIO",
        "COVER_LETTER",
        "ACHIEVEMENT",
        "WORK_SAMPLE",
        "ROLE_BRIEF",
        "OTHER",
    ):
        assert f"'{category}'" in LIFECYCLE
    for column in (
        "title",
        "evidence_category",
        "context_note",
        "archived_at",
        "version_number",
        "supersedes_document_id",
    ):
        assert f"add column {column}" in LIFECYCLE


def test_replacement_is_transactional_and_historical_rows_are_archived() -> None:
    assert "create or replace function public.replace_evidence_document" in LIFECYCLE
    assert "for update" in LIFECYCLE
    assert "original.version_number + 1" in LIFECYCLE
    assert "set archived_at = now()" in LIFECYCLE
    assert "delete from public.documents" not in LIFECYCLE
    assert "revoke all on function public.replace_evidence_document" in LIFECYCLE
    assert "grant execute on function public.replace_evidence_document" in LIFECYCLE

