# Mirror by Pathwisse

Mirror is an evidence-backed interview diagnostic and claims-audit system. This repository contains the Stage 1 production foundation: the candidate web app, typed FastAPI service, deterministic interview state machine, Supabase schema/RLS, versioned prompt contracts, and synthetic evaluation fixtures.

## Quick start

1. Copy `.env.example` to `.env` and add Supabase credentials when available.
2. Run `npm install`.
3. Run `python -m venv .venv`, then `.\.venv\Scripts\Activate.ps1` on Windows.
4. Run `python -m pip install -r apps/api/requirements.txt`.
5. Run `npm run dev`.

Authentication fails closed without Supabase credentials. Configure the public URL and anonymous/publishable key for the web and API, and keep the service-role key available only to the API. See `docs/architecture/authentication.md` for the complete identity boundary.

## Important boundaries

- The Interviewer, Skeptic, and Assessor have separate contracts and versioned prompts.
- The interview phase controller is deterministic code.
- A flag detected on turn N is eligible only when `detected_at_turn < current_turn`.
- The Skeptic defaults to `shadow` mode.
- Numeric assessments cannot be published without candidate evidence.
- All supplied personas are marked synthetic and are excluded from real calibration.

See `docs/architecture.md`, `docs/scoring.md`, `docs/privacy.md`, and `docs/synthetic-data.md`.

