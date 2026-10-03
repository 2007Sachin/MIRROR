-- Career Evidence spine: the experience a person has reviewed, edited and approved.
-- Additive. Pending items are created by the backend from the newest resume reading
-- (idempotent per source_key); only APPROVED items feed the role plan, Home, stories,
-- Dig Deeper and practice. Written only by the backend (service_role); people read their own rows.
begin;

create table public.evidence_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  source_document_id uuid null references public.documents(id) on delete set null,
  source_key text not null check (char_length(source_key) between 1 and 200),
  kind text not null check (kind in ('ACHIEVEMENT', 'PROJECT', 'RESPONSIBILITY', 'SKILL')),
  title text not null check (char_length(title) between 1 and 500),
  detail text null check (detail is null or char_length(detail) <= 3000),
  outcome text null check (outcome is null or char_length(outcome) <= 2000),
  metric text null check (metric is null or char_length(metric) <= 200),
  tools text[] not null default '{}' check (cardinality(tools) <= 30),
  source_label text null check (source_label is null or char_length(source_label) <= 300),
  status text not null default 'PENDING' check (status in ('PENDING', 'APPROVED', 'REMOVED')),
  merged_into uuid null references public.evidence_items(id) on delete set null,
  edited boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, source_key),
  constraint evidence_items_not_merged_into_itself check (merged_into is null or merged_into <> id)
);

create index evidence_items_user_status_idx on public.evidence_items(user_id, status);
create index evidence_items_source_document_idx on public.evidence_items(source_document_id);
create index evidence_items_merged_into_idx on public.evidence_items(merged_into);

-- The source resume and the merge target must belong to the same person. Exact ids only.
create or replace function public.evidence_items_verify_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.source_document_id is not null
    and not exists (select 1 from public.documents where id = new.source_document_id and user_id = new.user_id) then
    raise exception 'document does not belong to the item owner';
  end if;
  if new.merged_into is not null
    and not exists (select 1 from public.evidence_items where id = new.merged_into and user_id = new.user_id) then
    raise exception 'merge target does not belong to the item owner';
  end if;
  if tg_op = 'UPDATE' and (new.user_id is distinct from old.user_id or new.source_key is distinct from old.source_key) then
    raise exception 'an item cannot move to another owner or source';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger evidence_items_verify_ownership
  before insert or update on public.evidence_items
  for each row execute function public.evidence_items_verify_ownership();

alter table public.evidence_items enable row level security;

create policy evidence_items_select_own
  on public.evidence_items for select to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.evidence_items from anon;
revoke insert, update, delete on public.evidence_items from authenticated;
grant select on public.evidence_items to authenticated;
grant all on public.evidence_items to service_role;

commit;
