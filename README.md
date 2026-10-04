# Mirror by Pathwisse

Mirror is a calm space to practice talking about your experience, with a friendly voice conversation and a kind, clear reflection afterward. This repository contains the Stage 1 production foundation: the web app, typed FastAPI service, deterministic interview state machine, Supabase schema/RLS, versioned prompt contracts, and synthetic evaluation fixtures.

## Quick start

1. Copy `.env.example` to `.env` and add Supabase credentials when available.
2. Run `npm install`.
3. Run `python -m venv .venv`, then `.\.venv\Scripts\Activate.ps1` on Windows.
4. Run `python -m pip install -r apps/api/requirements.txt`.
5. Run `npm run dev`.

Authentication fails closed without Supabase credentials. Configure the public URL and anonymous/publishable key for the web and API, and keep the service-role key available only to the API. See `docs/architecture/authentication.md` for the complete identity boundary.

## Secrets and local environment files

- `.env` is git-ignored; only `.env.example` (placeholders, one entry per key) is tracked. Every commit in the repository was scanned for env files and key-shaped strings: none were ever committed.
- The service-role key and provider keys (`SUPABASE_SERVICE_ROLE_KEY`, `DEEPGRAM_API_KEY`, `SARVAM_API_KEY`) are server-only. Never give a secret a `NEXT_PUBLIC_` prefix; those values are compiled into the browser bundle.
- Tests and CI need **no** secrets and make no model-provider or hosted-Supabase calls. If a test seems to need a real key, that is a bug in the test.
- Do not keep `.env.bak*` copies. They are ignored by git but are ordinary files: if the project folder is synced (OneDrive, Dropbox, iCloud) they are uploaded to the cloud. Preferred practice: keep the repository **outside** any synced folder (for example `C:\dev\MIRROR`), keep a single `.env`, and delete stale backups once `.env` is confirmed current. If the working copy must stay in a synced folder, set the secrets as user-level environment variables instead of a file (the API and `next` both read the process environment first and do not let `.env` override it), or use a secrets manager.
- If a key may have been exposed (shared folder, screen share, backup copy), rotate it in the provider's dashboard rather than only deleting the file.

## Important boundaries

- The Interviewer, Skeptic, and Assessor have separate contracts and versioned prompts.
- The interview phase controller is deterministic code.
- A flag detected on turn N is eligible only when `detected_at_turn < current_turn`.
- The Skeptic defaults to `shadow` mode.
- Numeric assessments cannot be published without candidate evidence.
- All supplied personas are marked synthetic and are excluded from real calibration.

See `docs/architecture.md`, `docs/scoring.md`, `docs/privacy.md`, and `docs/synthetic-data.md`. Everything people read or hear follows `docs/copy-guide.md`; run `npm run lint:copy` after changing copy.

