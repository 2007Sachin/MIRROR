begin;

create type public.document_type as enum ('RESUME', 'JOB_DESCRIPTION', 'PROJECT');
create type public.document_status as enum ('UPLOADED', 'PROCESSING', 'PROCESSED', 'FAILED');

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  document_type public.document_type not null,
  storage_path text,
  original_filename text,
  mime_type text,
  raw_text text,
  status public.document_status not null,
  error_message text,
  created_at timestamptz not null default now(),
  processed_at timestamptz,
  constraint documents_resume_source check (
    document_type <> 'RESUME'
    or (
      storage_path is not null
      and mime_type in (
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      )
    )
  ),
  constraint documents_job_description_source check (
    document_type <> 'JOB_DESCRIPTION' or raw_text is not null
  )
);

-- This link is intentionally generic so later session creation can attach the
-- selected resume/JD without adding document-specific columns to sessions.
create table public.session_document_links (
  session_id uuid not null references public.sessions(id) on delete cascade,
  document_id uuid not null references public.documents(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (session_id, document_id)
);

create index documents_user_created_idx
  on public.documents(user_id, created_at desc);
create index session_document_links_document_idx
  on public.session_document_links(document_id);

alter table public.documents enable row level security;
alter table public.session_document_links enable row level security;

create policy documents_select_own
  on public.documents for select
  to authenticated
  using (user_id = auth.uid());

revoke insert, update, delete on public.documents from authenticated;
grant select on public.documents to authenticated;
grant all on public.documents to service_role;
grant all on public.session_document_links to service_role;
revoke all on public.session_document_links from authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'private-resumes',
  'private-resumes',
  false,
  8388608,
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
)
on conflict (id) do nothing;

commit;

