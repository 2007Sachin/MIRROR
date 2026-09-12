begin;

create type public.evidence_category as enum (
  'RESUME',
  'PROJECT',
  'CASE_STUDY',
  'CERTIFICATE',
  'PORTFOLIO',
  'COVER_LETTER',
  'ACHIEVEMENT',
  'WORK_SAMPLE',
  'ROLE_BRIEF',
  'OTHER'
);

alter table public.documents
  add column title text,
  add column evidence_category public.evidence_category,
  add column context_note text,
  add column archived_at timestamptz,
  add column version_number integer not null default 1,
  add column supersedes_document_id uuid references public.documents(id) on delete set null;

update public.documents
set title = case
      when nullif(trim(original_filename), '') is not null then original_filename
      when document_type = 'RESUME' then 'Resume'
      when document_type = 'JOB_DESCRIPTION' then 'Role brief'
      else 'Professional evidence'
    end,
    evidence_category = case
      when document_type = 'RESUME' then 'RESUME'::public.evidence_category
      when document_type = 'JOB_DESCRIPTION' then 'ROLE_BRIEF'::public.evidence_category
      else 'PROJECT'::public.evidence_category
    end,
    updated_at = coalesce(processed_at, created_at, now())
where title is null or evidence_category is null;

alter table public.documents
  alter column title set not null,
  alter column evidence_category set not null,
  add constraint documents_title_length check (char_length(title) between 1 and 160),
  add constraint documents_context_length check (context_note is null or char_length(context_note) <= 4000),
  add constraint documents_version_positive check (version_number > 0),
  add constraint documents_not_self_superseding check (supersedes_document_id is null or supersedes_document_id <> id);

create unique index documents_single_replacement_idx
  on public.documents(supersedes_document_id)
  where supersedes_document_id is not null;

create index documents_active_user_updated_idx
  on public.documents(user_id, updated_at desc)
  where archived_at is null;

create index documents_archived_user_idx
  on public.documents(user_id, archived_at desc)
  where archived_at is not null;

create or replace function public.replace_evidence_document(
  p_original_document_id uuid,
  p_user_id uuid,
  p_new_document_id uuid,
  p_document_type public.document_type,
  p_storage_path text,
  p_original_filename text,
  p_mime_type text,
  p_raw_text text,
  p_status public.document_status,
  p_processed_at timestamptz,
  p_title text,
  p_evidence_category public.evidence_category,
  p_context_note text
)
returns setof public.documents
language plpgsql
security definer
set search_path = public
as $$
declare
  original public.documents;
begin
  select * into original
  from public.documents
  where id = p_original_document_id
    and user_id = p_user_id
    and archived_at is null
  for update;

  if original.id is null then
    raise exception 'active owned evidence not found';
  end if;

  insert into public.documents (
    id, user_id, document_type, storage_path, original_filename, mime_type,
    raw_text, status, processed_at, title, evidence_category, context_note,
    version_number, supersedes_document_id
  ) values (
    p_new_document_id, p_user_id, p_document_type, p_storage_path,
    p_original_filename, p_mime_type, p_raw_text, p_status, p_processed_at,
    p_title, p_evidence_category, p_context_note,
    original.version_number + 1, original.id
  );

  update public.documents
  set archived_at = now()
  where id = original.id and user_id = p_user_id;

  return query
  select * from public.documents where id = p_new_document_id;
end;
$$;

revoke all on function public.replace_evidence_document(
  uuid, uuid, uuid, public.document_type, text, text, text, text,
  public.document_status, timestamptz, text, public.evidence_category, text
) from public, anon, authenticated;

grant execute on function public.replace_evidence_document(
  uuid, uuid, uuid, public.document_type, text, text, text, text,
  public.document_status, timestamptz, text, public.evidence_category, text
) to service_role;

commit;
