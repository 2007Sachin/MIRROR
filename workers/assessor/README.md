# Assessor worker

Runs the durable `POST_SESSION_ASSESSMENT` queue after an interview is complete.

Start it from the repository root with `apps/api` on `PYTHONPATH` and the API environment configured:

```powershell
npm run dev:worker
```

The root `npm run dev` command starts this worker alongside the web and API processes. Use `node scripts/run-assessor.js --once` to claim at most one job during operational checks. The worker is backend-only: it requires the Supabase service-role key and configured model-provider key. It validates specialist evidence, performs conditional adjudication, applies deterministic aggregation, and writes `session_results` only after the complete pipeline succeeds. Failed work is retried with bounded exponential backoff.
