-- Durable completion state for prompt-backed target-session links.
-- Apply locally only; hosted apply requires separate approval.
begin;

lock table public.target_session_links in access exclusive mode;
lock table public.generated_questions in access exclusive mode;

-- Existing prompt-backed links can be upgraded only when completeness and ownership are provable.
do $$
begin
  if exists (select 1 from public.target_session_links where prompt_set_id is not null group by prompt_set_id having count(*) > 1) then
    raise exception 'cannot add prompt completeness state: duplicate prompt_set_id links';
  end if;
  if exists (select 1 from public.generated_questions q where not exists (
    select 1 from public.target_session_links l where l.prompt_set_id = q.prompt_set_id
  )) then raise exception 'cannot add prompt completeness state: orphan generated_questions'; end if;
  if exists (
    select 1 from public.target_session_links l
    where l.prompt_set_id is not null and (
      (select count(*) from public.generated_questions q where q.prompt_set_id = l.prompt_set_id
        and q.user_id = l.user_id and q.candidate_target_id = l.candidate_target_id) not in (3, 4)
      or exists (select 1 from public.generated_questions q where q.prompt_set_id = l.prompt_set_id
        and (q.user_id <> l.user_id or q.candidate_target_id <> l.candidate_target_id))
      or (select array_agg(q.position order by q.position) from public.generated_questions q
          where q.prompt_set_id = l.prompt_set_id and q.user_id = l.user_id
            and q.candidate_target_id = l.candidate_target_id)
        is distinct from case
          when (select count(*) from public.generated_questions q where q.prompt_set_id = l.prompt_set_id
                and q.user_id = l.user_id and q.candidate_target_id = l.candidate_target_id) = 3 then array[1,2,3]::smallint[]
          else array[1,2,3,4]::smallint[] end
      or exists (
        select 1 from public.generated_questions q where q.prompt_set_id = l.prompt_set_id
          and q.user_id = l.user_id and q.candidate_target_id = l.candidate_target_id
          and (q.blueprint_id is distinct from l.blueprint_id or q.round_key is distinct from l.round_key)
      )
    )
  ) then raise exception 'cannot add prompt completeness state: existing prompt link has an incomplete or misowned set'; end if;
end;
$$;

-- The base write-once trigger rejects all updates; remove it only for this locked backfill.
drop trigger target_session_links_write_once on public.target_session_links;
alter table public.target_session_links
  add column prompt_set_state text not null default 'NOT_APPLICABLE',
  add column expected_prompt_count smallint null,
  add column prompt_manifest jsonb null;
update public.target_session_links l
set prompt_set_state = 'COMPLETE',
    expected_prompt_count = (select count(*)::smallint from public.generated_questions q
      where q.prompt_set_id = l.prompt_set_id and q.user_id = l.user_id
        and q.candidate_target_id = l.candidate_target_id),
    prompt_manifest = (select jsonb_agg(to_jsonb(q) - array['id', 'user_id', 'created_at', 'provenance_class']::text[] order by q.position)
      from public.generated_questions q where q.prompt_set_id = l.prompt_set_id and q.user_id = l.user_id
        and q.candidate_target_id = l.candidate_target_id)
where l.prompt_set_id is not null;

alter table public.target_session_links
  add constraint target_session_links_prompt_state_values
    check (prompt_set_state in ('NOT_APPLICABLE', 'PENDING', 'COMPLETE')),
  add constraint target_session_links_expected_count_values
    check (expected_prompt_count is null or expected_prompt_count in (3, 4)),
  add constraint target_session_links_prompt_state_shape check (
    (prompt_set_id is null and prompt_set_state = 'NOT_APPLICABLE' and expected_prompt_count is null and prompt_manifest is null)
    or (prompt_set_id is not null and prompt_set_state in ('PENDING', 'COMPLETE')
      and expected_prompt_count is not null and expected_prompt_count in (3, 4)
      and prompt_manifest is not null
      and jsonb_typeof(prompt_manifest) = 'array'
      and jsonb_array_length(prompt_manifest) = expected_prompt_count)
  );

alter table public.target_session_links add constraint target_session_links_prompt_set_id_key unique (prompt_set_id);
alter table public.generated_questions add constraint generated_questions_prompt_set_id_fkey
  foreign key (prompt_set_id) references public.target_session_links (prompt_set_id) on delete cascade;

create or replace function public.target_session_links_verify()
returns trigger language plpgsql set search_path = public as $$
begin
  if not exists (select 1 from public.sessions where id = new.session_id and user_id = new.user_id) then
    raise exception 'session does not belong to the link owner';
  end if;
  if not exists (select 1 from public.candidate_targets where id = new.candidate_target_id and user_id = new.user_id) then
    raise exception 'target does not belong to the link owner';
  end if;
  if new.blueprint_id is not null and not exists (
    select 1 from public.interview_blueprints where id = new.blueprint_id and user_id = new.user_id and candidate_target_id = new.candidate_target_id
  ) then raise exception 'blueprint does not belong to the link target'; end if;
  if new.prompt_set_id is null then
    if new.prompt_set_state is distinct from 'NOT_APPLICABLE' or new.expected_prompt_count is not null
      or new.prompt_manifest is not null then
      raise exception 'invalid generic link prompt state';
    end if;
  else
    if tg_op = 'INSERT' and new.prompt_set_state is distinct from 'PENDING' then
      raise exception 'prompt-backed links must be created PENDING';
    end if;
    if new.prompt_set_state not in ('PENDING', 'COMPLETE') or new.expected_prompt_count is null
      or new.expected_prompt_count not in (3, 4) then raise exception 'invalid prompt-backed link state'; end if;
    if jsonb_typeof(new.prompt_manifest) is distinct from 'array'
      or jsonb_array_length(new.prompt_manifest) <> new.expected_prompt_count then raise exception 'invalid prompt manifest'; end if;
    if exists (select 1 from jsonb_array_elements(new.prompt_manifest) with ordinality e(value, ordinality)
      where e.value ->> 'position' is distinct from e.ordinality::text) then
      raise exception 'prompt manifest positions must be sequential';
    end if;
    if exists (select 1 from jsonb_array_elements(new.prompt_manifest) e(value)
      where e.value ->> 'candidate_target_id' is distinct from new.candidate_target_id::text
        or e.value ->> 'blueprint_id' is distinct from new.blueprint_id::text
        or e.value ->> 'prompt_set_id' is distinct from new.prompt_set_id::text
        or e.value ->> 'round_key' is distinct from new.round_key) then
      raise exception 'prompt manifest identity does not match link';
    end if;
    if exists (select 1 from public.generated_questions q where q.prompt_set_id = new.prompt_set_id
      and (q.user_id <> new.user_id or q.candidate_target_id <> new.candidate_target_id)) then
      raise exception 'prompt set does not belong to the link target';
    end if;
    if new.prompt_set_state = 'COMPLETE' and (
      (select count(*) from public.generated_questions q where q.prompt_set_id = new.prompt_set_id and q.user_id = new.user_id and q.candidate_target_id = new.candidate_target_id) <> new.expected_prompt_count
      or exists (select 1 from generate_series(1, new.expected_prompt_count) p where not exists (
        select 1 from public.generated_questions q where q.prompt_set_id = new.prompt_set_id and q.user_id = new.user_id and q.candidate_target_id = new.candidate_target_id and q.position = p
      ))
      or exists (select 1 from public.generated_questions q where q.prompt_set_id = new.prompt_set_id
        and (to_jsonb(q) - array['id', 'user_id', 'created_at', 'provenance_class']::text[]) is distinct from new.prompt_manifest -> (q.position - 1))
    ) then raise exception 'prompt set is incomplete or differs from manifest'; end if;
  end if;
  return new;
end;
$$;

create or replace function public.target_session_links_write_once()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.session_id is distinct from old.session_id or new.user_id is distinct from old.user_id
    or new.candidate_target_id is distinct from old.candidate_target_id or new.blueprint_id is distinct from old.blueprint_id
    or new.round_key is distinct from old.round_key or new.competency_key is distinct from old.competency_key
    or new.prompt_set_id is distinct from old.prompt_set_id or new.expected_prompt_count is distinct from old.expected_prompt_count
    or new.prompt_manifest is distinct from old.prompt_manifest
    or new.created_at is distinct from old.created_at or old.prompt_set_state is distinct from 'PENDING'
    or new.prompt_set_state is distinct from 'COMPLETE' then
    raise exception 'a session link is write-once except pending completion';
  end if;
  return new;
end;
$$;

-- Replace/attach trigger for BOTH insert and update: verify owns exact COMPLETE sets.
drop trigger target_session_links_verify on public.target_session_links;
create trigger target_session_links_verify before insert or update on public.target_session_links
  for each row execute function public.target_session_links_verify();
create trigger target_session_links_write_once before update on public.target_session_links
  for each row execute function public.target_session_links_write_once();
revoke all on function public.target_session_links_verify() from public, anon, authenticated;
revoke all on function public.target_session_links_write_once() from public, anon, authenticated;

create or replace function public.generated_questions_guard_link()
returns trigger language plpgsql set search_path = public as $$
declare
  link_row public.target_session_links%rowtype;
  set_id uuid;
begin
  if tg_op = 'DELETE' then set_id := old.prompt_set_id; else set_id := new.prompt_set_id; end if;
  select * into link_row from public.target_session_links where prompt_set_id = set_id for update;
  if not found and tg_op = 'DELETE' then return old; end if;
  if not found then raise exception 'question insert requires a matching pending link'; end if;
  if tg_op = 'DELETE' then
    if link_row.prompt_set_state = 'COMPLETE'
      and exists (select 1 from public.candidate_targets where id = link_row.candidate_target_id and user_id = link_row.user_id)
      and exists (select 1 from public.sessions where id = link_row.session_id and user_id = link_row.user_id)
      and (link_row.blueprint_id is null or exists (
        select 1 from public.interview_blueprints where id = link_row.blueprint_id and user_id = link_row.user_id
      )) then
      raise exception 'complete prompt set is immutable';
    end if;
    return old;
  end if;
  if link_row.prompt_set_state is distinct from 'PENDING'
    or new.user_id is distinct from link_row.user_id
    or new.candidate_target_id is distinct from link_row.candidate_target_id
    or new.position > link_row.expected_prompt_count then
    raise exception 'question insert requires a matching pending link';
  end if;
  if (to_jsonb(new) - array['id', 'user_id', 'created_at', 'provenance_class']::text[])
      is distinct from link_row.prompt_manifest -> (new.position - 1) then
    raise exception 'question does not match prompt manifest';
  end if;
  return new;
end;
$$;
create trigger generated_questions_guard_link before insert or delete on public.generated_questions
  for each row execute function public.generated_questions_guard_link();
revoke all on function public.generated_questions_guard_link() from public, anon, authenticated;

-- Prompt/story content is backend-private; clients receive only link metadata.
revoke select on public.target_session_links from authenticated;
grant select (session_id, user_id, candidate_target_id, blueprint_id, round_key, competency_key, prompt_set_id, created_at)
  on public.target_session_links to authenticated;
commit;
