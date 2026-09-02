from pathlib import Path


MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "202608310004_document_ingestion.sql"
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

