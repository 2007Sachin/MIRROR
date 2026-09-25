-- Repeat-use writes are safe to replay after a lost response.
alter table public.sessions
  add column if not exists idempotency_key uuid,
  add column if not exists idempotency_payload_hash text;

create unique index if not exists sessions_user_idempotency_key_idx
  on public.sessions (user_id, idempotency_key)
  where idempotency_key is not null;

alter table public.answer_attempts
  add column if not exists idempotency_key uuid,
  add column if not exists idempotency_payload_hash text;

create unique index if not exists answer_attempts_user_idempotency_key_idx
  on public.answer_attempts (user_id, idempotency_key)
  where idempotency_key is not null;
