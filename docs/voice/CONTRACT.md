# Voice contract (draft for approval)

Status: in progress. Fix 1 built behind flags; Fix 2 and later not yet built.

## Voice room states and maximum dwell (watchdog)
| State | Max dwell | On timeout |
|---|---|---|
| PREPARING | 10 s | retry once, then show "Let's try that once more" and the type option |
| CONNECTING | 8 s | same |
| INTERVIEWER_SPEAKING | question length + 5 s | stop audio, show the text, move to LISTENING |
| LISTENING | 90 s of no speech | gentle prompt ("Take your time"), keep listening; 5 min idle then auto-pause |
| CANDIDATE_SPEAKING | 120 s (existing) | end the turn |
| PROCESSING | 20 s | retry once with the same turn id (idempotent), then type option |
| PAUSED (new) | none | frozen timer; auto-expires per retention |

## Session lifecycle additions (backend)
`ACTIVE -> PAUSED -> ACTIVE`; `ACTIVE | PAUSED -> COMPLETED` with `ended_reason = ended_early`. Additive migration: `paused_at`, `last_heartbeat_at`, `engine_state jsonb`, `ended_reason`, `live_lease_id`, `live_lease_expires_at`.

## Endpoints (new, same auth and owner checks)
- `POST /api/v1/sessions/{id}/pause`
- `POST /api/v1/sessions/{id}/resume` (returns remaining time and the question to re-ask)
- `POST /api/v1/sessions/{id}/heartbeat` (also sent with `sendBeacon` on `pagehide`)
- `POST /api/v1/sessions/{id}/end` with `{ "generate_report": true }`

## Timing events per turn (same turn id, client and server)
`t_speech_start, t_speech_end, t_upload_done, t_stt_final, t_llm_first_token, t_llm_done, t_tts_first_byte, t_audio_play_start, t_turn_persisted`

## Feature flags (env vars; all default off; off means the original code path)
| Flag | Status | What it does |
|---|---|---|
| `VOICE_HTTP_POOL` | built | Shared keep-alive HTTP connections for all Supabase repository calls (`app/http_pool.py`). Reads retry once on a stale connection. |
| `VOICE_PARALLEL_CONTEXT` | built | Runs independent reads and writes together in the turn: plan prefetch, candidate lookup with previous turn, publish with audio attach and context build, claims/competencies/flags in one wave, audio upload overlapping speech-to-text, tail writes together. Passes the session read once instead of four times. |
| `VOICE_ASYNC_PERSIST` | built | Analytics events, latency metrics and the request-completion row are written after the reply (`app/deferred_writes.py`): per-session order, a queued key runs once, three retries, flushed before session close/end and on shutdown. Transcript rows stay synchronous, so the next turn never reads stale history. If the API crashes with writes queued, those events/metrics are lost (the transcript is not). |
| `VOICE_SESSION_CACHE` | built | Session reads are cached for the length of one voice turn; every state change updates the cache and a failed concurrency check drops it. Cuts about 8 session reads per turn. |
| `VOICE_STREAMING_STT` | built (server side) | Answers over 25 s go to Sarvam's WebSocket speech-to-text (no 30 s cap) instead of the REST endpoint, which rejects them. Short answers keep the REST path unchanged. Decodes with PyAV, streams 1 s chunks, flushes, joins result messages. Measured: a 58 s answer transcribes in 3.1 s. Live browser-to-server streaming (transcribing while the student speaks) is not built yet. |
| `VOICE_STREAMING_TTS`, `VOICE_ADAPTIVE_ENDPOINT`, `VOICE_DRAFT_RESUME` | planned | See earlier sections. |

New dependency (Agent rule: noted here): `av` (PyAV, bundles its own ffmpeg libraries, needs no system install) decodes browser audio to 16 kHz PCM for the WebSocket. `websockets` was already installed with uvicorn.

Rollback: set the flag to `false` (or remove it) and restart the API. No data migration is involved for these flags.

## New dependencies
None planned. Streaming STT/TTS may need provider WebSocket clients; decide after the fixes below are measured.
