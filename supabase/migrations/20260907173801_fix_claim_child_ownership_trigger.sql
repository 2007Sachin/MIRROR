begin;

create or replace function public.validate_claim_child_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.claims where id = new.claim_id and user_id = new.user_id
  ) then
    raise exception 'claim child row must belong to the claim owner';
  end if;

  if tg_table_name = 'claim_evidence' then
    if (to_jsonb(new) ->> 'document_id') is not null and not exists (
      select 1 from public.documents
      where id = (to_jsonb(new) ->> 'document_id')::uuid and user_id = new.user_id
    ) then
      raise exception 'claim evidence document must belong to the claim owner';
    end if;

    if (to_jsonb(new) ->> 'turn_id') is not null and not exists (
      select 1
      from public.turns t
      join public.sessions s on s.id = t.session_id
      where t.id = (to_jsonb(new) ->> 'turn_id')::uuid and s.user_id = new.user_id
    ) then
      raise exception 'claim evidence turn must belong to the claim owner';
    end if;
  end if;
  return new;
end;
$$;

commit;
