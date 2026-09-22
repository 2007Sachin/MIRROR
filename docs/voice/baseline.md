# Voice baseline (Phase 0)

Measured from the real `voice_turn_metrics` table (Supabase) and by timing the Supabase REST API from the dev machine. Nothing has been changed yet.

## What actually runs
- Web: Next.js. The room is `apps/web/src/components/voice-interview.tsx` (about 1,000 lines, one component).
- API: FastAPI. One turn is one request: `POST /api/v1/sessions/{id}/voice/turn` (`voice_service.submit`).
- STT: Sarvam (`SPEECH_TO_TEXT_PROVIDER=sarvam`); Deepgram Nova-3 was the earlier provider. TTS: Sarvam `bulbul:v3`, voice `priya`, mp3.
- The turn is turn-based by design (whole recording, then STT, then LLM, then full TTS). `docs/architecture/voice-pipeline.md` says streaming and WebRTC were deliberately left out; it does not record a failed attempt. No abandoned streaming work in git history.

## Real per-stage timings (4 complete Sarvam turns, 2026-09-19)
| Stage | Values (ms) |
|---|---|
| Upload + validation | 0 to 3 |
| STT (Sarvam) | 677, 697, 756, 860 |
| Interviewer model call | 264, 328, 384, 396 |
| **"Context build" (everything else in the text pipeline)** | **11,500 / 11,705 / 11,957 / 16,129** |
| TTS | 0 (cached or failed), 1,579, 2,176 |
| Audio storage upload | 874 to 2,460 |
| **Total turn** | **19,187 / 19,829 / 23,657 / 27,937** |

Target for "last word to first audio" is p50 1.5 s. Measured whole-turn time is 19 to 28 s. Only 4 complete turns exist, so p95 is not meaningful yet.

## Ranked root causes
1. **Sequential database round trips (about 12 s per turn). Evidence: strong.** Timing Supabase REST from the dev machine gives 257 to 784 ms per call (median about 330 ms). `interviewer_service.submit` and `interviewer_context.build` make dozens of awaited calls one after another (state, turns, claims, competencies, flags, plan, create turn, publish event, record events, get response). About 35 calls at about 330 ms matches the 12 s. The model call itself is only 0.3 s.
2. **Everything after STT is on the critical path. Evidence: strong.** Candidate-audio upload, request bookkeeping, event recording, metrics insert and TTS audio storage all run before the response returns (`voice_service.submit`, suspects 8 and 9).
3. **Whole reply is synthesized, then uploaded, then signed. Evidence: strong from code, 1.6 to 2.2 s TTS plus 0.9 to 2.5 s storage.** No sentence-level streaming (suspect 9).
4. **Cross-region round trips. Evidence: likely.** API host and Supabase project (`kiflai...`) may be in different regions; the 260 to 780 ms per call suggests it. Confirm the Supabase region and the API host location.
5. **Whole-recording upload after the user stops (suspect 7).** Cheap on localhost (0 ms measured); would be larger on real networks. Not yet measured.
6. **Unproven from data (need browser tests):** live captions vs recorder contention (suspect 1), iOS audio unlock (2), echo loop (4), no watchdog on states (5), codec mismatch on Safari (6). Code inspection: `voice-interview.tsx` uses browser `SpeechRecognition` alongside `MediaRecorder` on the same mic; silence hold is a fixed `END_OF_TURN_SILENCE_MS = 1150`; `echoCancellation: true` is set; there is no per-state max dwell.
7. **Background jobs (suspect 11):** the skeptic runs after each candidate turn through a queue; no evidence yet that it blocks the critical path.

## Not measured yet (blocked)
- Recorded Indian-English WAV samples: none in the repo. Word error rate before/after cannot be measured without real recordings and reference transcripts. Synthetic TTS audio is not a fair test.
- Client timestamps (`t_speech_start` etc.), Safari/iOS and Chrome Android behavior.
- The full-turn latency harness (needs the samples above).

## Measured with the harness (30 turns each, synthetic speech, this machine to Supabase)
Numbers are p50 / p95 in milliseconds. Interviewer model was failing instantly (fallback used) in the first three rows.

| Run | Flags | Whole turn (client) | Context/DB | Storage | TTS | STT |
|---|---|---|---|---|---|---|
| baseline | none | 24,017 / 32,821 | 12,502 / 16,622 | 1,485 / 2,996 | 0 / 3,524 | 752 / 1,097 |
| fix 1 | HTTP_POOL + PARALLEL_CONTEXT | 8,869 / 16,051 | 3,914 / 6,166 | 1,395 / 2,360 | 0 / 3,657 | 865 / 1,098 |
| fix 2 | + ASYNC_PERSIST | 7,725 / 14,110 | 3,584 / 5,551 | 1,211 / 2,437 | 0 / 3,377 | 800 / 1,121 |
| fix 2 + session cache | + SESSION_CACHE | 6,107 / 11,115 | 2,216 / 2,773 | 1,328 / 2,335 | 0 / 3,689 | 787 / 1,160 |

Supabase calls per turn: about 39 at fix 2, about 29.5 with the session cache (`GET sessions` 9.3 to 1.3 per turn). Still high: `GET turns` 7.3, `POST session_events` 3.4.

## Interviewer model fixed (schema)
The model provider rejected the interviewer's response schema (`anyOf` on optional fields), so the fallback question was used on every turn and the model time was never real. Fixed in `_strict_json_schema`. With a working model the isolated call is about 2.1 s (392 output tokens). Back-to-back harness turns triggered provider token-per-minute waits (4 to 10 s each), which a person speaking between turns would not; the harness now has `--pause`.

### With the interviewer working, paced like a person (20 s between turns), all four flags on, 30 turns
| Stage | p50 | p95 |
|---|---|---|
| Whole turn (client) | 9,605 | 12,189 |
| Speech-to-text | 749 | 957 |
| Context/DB | 1,893 | 2,631 |
| Interviewer model | 1,401 | 2,169 |
| Reply speech (TTS) | 1,879 | 3,505 |
| Audio storage + signing | 1,715 | 2,437 |

This is not directly comparable to the first four rows, whose interviewer call was failing instantly. Adding about 1.4 s of real model time to the baseline gives about 25.4 s, so the flags cut a real turn from about 25 s to 9.6 s. No rate-limit waits and no failures in this run; 2 fallback questions (the model output was rejected twice).

### After moving every AI step to Sarvam (`sarvam-105b-conversations`), 8 turns, paced 3 s
Whole turn 8,996 / 13,248 ms (p50 / p95); interviewer model 2,959 / 3,872 ms (about 1.5 s slower than Groq); no failures.
