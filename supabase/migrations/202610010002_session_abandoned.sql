-- A practice can be discarded before it finishes: ABANDONED is terminal, is never reviewed,
-- and never counts as a practice. Additive: no table, row, or existing transition changes.

begin;

alter type public.session_status add value if not exists 'ABANDONED';

commit;

begin;

-- Same rules as 202609010008_interview_session_engine.sql, plus: any session that has not
-- reached review (CREATED, PREPARING, READY, ACTIVE) may become ABANDONED, and nothing leaves it.
create or replace function public.enforce_session_lifecycle()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if old.status <> new.status and not (
    (old.status = 'CREATED' and new.status in ('PREPARING', 'FAILED', 'ABANDONED')) or
    (old.status = 'PREPARING' and new.status in ('READY', 'FAILED', 'ABANDONED')) or
    (old.status = 'READY' and new.status in ('ACTIVE', 'FAILED', 'ABANDONED')) or
    (old.status = 'ACTIVE' and new.status in ('ASSESSING', 'FAILED', 'ABANDONED')) or
    (old.status = 'ASSESSING' and new.status in ('COMPLETED', 'FAILED'))
  ) then
    raise exception 'illegal session status transition: % to %', old.status, new.status;
  end if;
  if old.status in ('ACTIVE', 'ASSESSING', 'COMPLETED', 'FAILED', 'ABANDONED')
    and new.total_time_budget_seconds <> old.total_time_budget_seconds then
    raise exception 'session time budget cannot be extended after start';
  end if;
  return new;
end;
$$;

commit;
