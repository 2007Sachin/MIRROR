-- READ-ONLY catalog inspection for the hosted Mirror Supabase project.
-- Run in the Supabase SQL editor (or any read-only connection). SELECT statements only; nothing here
-- writes. It returns ONE json document: save it as .runtime/hosted_catalog.json and compare it with the
-- repository's expected schema. Contains no row data from application tables.

select jsonb_pretty(jsonb_build_object(
  'applied_migrations', (select coalesce(jsonb_agg(version order by version), '[]'::jsonb)
                           from supabase_migrations.schema_migrations),
  'tables', (select coalesce(jsonb_agg(jsonb_build_object(
                'table', c.relname, 'rls_enabled', c.relrowsecurity, 'rls_forced', c.relforcerowsecurity)
                order by c.relname), '[]'::jsonb)
               from pg_class c join pg_namespace n on n.oid = c.relnamespace
              where n.nspname = 'public' and c.relkind = 'r'),
  'columns', (select coalesce(jsonb_agg(jsonb_build_object(
                'table', table_name, 'column', column_name, 'type', data_type, 'udt', udt_name,
                'nullable', is_nullable, 'default', column_default)
                order by table_name, ordinal_position), '[]'::jsonb)
               from information_schema.columns where table_schema = 'public'),
  'policies', (select coalesce(jsonb_agg(jsonb_build_object(
                'table', tablename, 'policy', policyname, 'cmd', cmd, 'roles', roles,
                'permissive', permissive, 'qual', qual, 'with_check', with_check)
                order by tablename, policyname), '[]'::jsonb)
               from pg_policies where schemaname in ('public', 'storage')),
  'table_grants', (select coalesce(jsonb_agg(jsonb_build_object(
                'table', table_name, 'grantee', grantee, 'privilege', privilege_type)
                order by table_name, grantee, privilege_type), '[]'::jsonb)
               from information_schema.role_table_grants
              where table_schema = 'public' and grantee in ('anon', 'authenticated', 'service_role')),
  'triggers', (select coalesce(jsonb_agg(jsonb_build_object(
                'table', event_object_table, 'trigger', trigger_name, 'timing', action_timing,
                'event', event_manipulation) order by event_object_table, trigger_name), '[]'::jsonb)
               from information_schema.triggers where trigger_schema = 'public'),
  'functions', (select coalesce(jsonb_agg(jsonb_build_object(
                'function', p.proname, 'security_definer', p.prosecdef,
                'config', p.proconfig) order by p.proname), '[]'::jsonb)
               from pg_proc p join pg_namespace n on n.oid = p.pronamespace
              where n.nspname = 'public'),
  'indexes', (select coalesce(jsonb_agg(jsonb_build_object(
                'table', tablename, 'index', indexname) order by tablename, indexname), '[]'::jsonb)
               from pg_indexes where schemaname = 'public'),
  'constraints', (select coalesce(jsonb_agg(jsonb_build_object(
                'table', conrelid::regclass::text, 'constraint', conname, 'type', contype)
                order by conrelid::regclass::text, conname), '[]'::jsonb)
               from pg_constraint where connamespace = 'public'::regnamespace),
  'enums', (select coalesce(jsonb_agg(jsonb_build_object(
                'enum', t.typname, 'labels', (select jsonb_agg(e.enumlabel order by e.enumsortorder)
                                                from pg_enum e where e.enumtypid = t.oid))
                order by t.typname), '[]'::jsonb)
               from pg_type t join pg_namespace n on n.oid = t.typnamespace
              where n.nspname = 'public' and t.typtype = 'e'),
  'storage_buckets', (select coalesce(jsonb_agg(jsonb_build_object(
                'id', id, 'public', public, 'file_size_limit', file_size_limit,
                'allowed_mime_types', allowed_mime_types) order by id), '[]'::jsonb)
               from storage.buckets)
)) as hosted_catalog;
