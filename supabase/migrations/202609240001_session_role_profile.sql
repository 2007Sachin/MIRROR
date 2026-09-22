-- Explicit role binding for a session, alongside the free-text target_role.
-- Additive and nullable: existing sessions keep working via profiles.current_role_profile_id.
-- When set, planning must use this role instead of the account's mutable "current role".
begin;

alter table public.sessions
  add column role_profile_id uuid references public.role_profiles(id) on delete set null;

create index sessions_role_profile_idx on public.sessions(role_profile_id);

-- A session's explicit role must belong to the session's own owner.
create or replace function public.sessions_verify_role_profile_ownership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.role_profile_id is not null and not exists (
    select 1 from public.role_profiles where id = new.role_profile_id and user_id = new.user_id
  ) then
    raise exception 'role profile does not belong to the session owner';
  end if;
  return new;
end;
$$;

create trigger sessions_verify_role_profile_ownership
  before insert or update on public.sessions
  for each row execute function public.sessions_verify_role_profile_ownership();

commit;
