-- Owner-authorized retirement of obsolete nutrition data, 2026-10-04.
-- Exact two-table scope approved by Architecture, Data and Security;
-- hosted identity/dependency closure refreshed before the performed cleanup.
-- Hosted ledger: 20261004121203 / retire_verified_nutrition_tables.
-- Deployed statements omitted IF EXISTS because both tables were verified present.
-- IF EXISTS is equivalent under that precondition and permits clean checkouts
-- where these unrelated nutrition tables never existed. RESTRICT is retained;
-- no CASCADE, Mirror row mutation, or blanket migration replay is authorized.
-- Destructive data retirement is irreversible; no backup is asserted.
BEGIN;
DROP TABLE IF EXISTS public.detailed_food_logs RESTRICT;
DROP TABLE IF EXISTS public.nutrition_goals RESTRICT;
COMMIT;
