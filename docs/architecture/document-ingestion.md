# Document ingestion

This milestone persists source documents without interpreting them. Resume intelligence, extraction, scoring, claims, embeddings, and AI-agent work remain out of scope.

## Persistence model

`public.documents` owns document metadata and optional raw text. Each row belongs to `profiles.id` and has one of `RESUME`, `JOB_DESCRIPTION`, or `PROJECT` document types. Lifecycle status is `UPLOADED`, `PROCESSING`, `PROCESSED`, or `FAILED`.

Resume rows store a private Supabase Storage path and validated MIME type. They remain `UPLOADED`; no text is extracted. Pasted job descriptions store `raw_text` directly and are marked `PROCESSED` because no additional ingestion work is required. `preferred_language` and onboarding data do not affect ingestion.

`session_document_links` is a generic reference table for future session setup. The deletion API checks it and refuses deletion when a document is attached to an `in_progress`, `processing`, or `complete` session. Links for inactive sessions may be removed with the document through the foreign-key cascade.

## Resume validation and storage

The API accepts only `application/pdf` and `application/vnd.openxmlformats-officedocument.wordprocessingml.document`. It requires an allowed multipart MIME declaration and independently inspects file content: PDFs must have the PDF signature; DOCX files must be valid ZIP containers containing the required Word package entries. Filename extensions are never used as proof of type.

`RESUME_MAX_FILE_SIZE_BYTES` is the authoritative API limit. `NEXT_PUBLIC_RESUME_MAX_FILE_SIZE_BYTES` provides matching early browser validation, while the API always rechecks size. The default is 8 MiB, matching the private bucket's initial limit.

Storage paths are generated from the verified user UUID and a server-generated document UUID. Original filenames are sanitized metadata only and are never used as object paths. The service-role key performs private Storage and database operations and is never exposed to the browser.

## API ownership boundary

The document routes derive the owner from `get_current_user()`:

- `POST /api/v1/documents/resume`
- `POST /api/v1/documents/job-description`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{id}`
- `DELETE /api/v1/documents/{id}`

Reads and deletes filter on both document ID and the verified subject UUID. Missing and other-user documents both return `404` to avoid disclosing document existence. RLS permits authenticated users to select only their own rows; all mutation grants remain backend-only.

## Setup page

`/app/setup` requires authentication and completed onboarding. It uploads a resume with real progress reporting, then lets the candidate paste a job description or explicitly continue without one. Successful selected document IDs are stored locally and reconciled against the authenticated document list on refresh. No analysis result is presented.

