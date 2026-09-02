# Turn-based voice pipeline

## Why turn-based audio

Mirror adds voice as an adapter around the existing text interviewer. It does
not introduce a second interview engine:

```text
candidate recording
  -> private storage
  -> Deepgram Nova-3 STT
  -> transcript
  -> existing TextInterviewService and deterministic State Machine
  -> interviewer question text
  -> Sarvam bulbul:v2 TTS
  -> private storage and short-lived signed playback URL
```

This milestone intentionally does not use WebRTC, full realtime streaming,
LiveKit, Pipecat, interruption, or barge-in. A complete recording is easier to
retry idempotently, keeps the deterministic turn boundary intact, and makes
provider failures observable without changing the interview lifecycle. The
official [Deepgram pre-recorded API](https://developers.deepgram.com/docs/pre-recorded-audio)
supports Nova-3 binary uploads, while the [Sarvam REST TTS API](https://docs.sarvam.ai/api-reference/text-to-speech/convert)
supports `bulbul:v2` and the `anushka` voice.

## Provider boundaries

`SpeechToTextProvider` accepts validated bytes plus a normalized MIME type and
returns a provider-neutral transcript, confidence, detected language, safe
metadata, model, and latency. `DeepgramSpeechToTextProvider` is the production
adapter. Deepgram receives candidate audio only; it receives no resume, Claims
Graph data, interview plan, or unrelated transcript history.

`TextToSpeechProvider` accepts only the interviewer question and configured
language. It returns audio bytes plus provider-neutral metadata and latency.
`SarvamTextToSpeechProvider` uses `bulbul:v2` with `anushka`. Sarvam never
receives candidate audio, candidate transcripts, resume content, claims, or
scores.

Provider API keys are server-only settings. They are never prefixed with
`NEXT_PUBLIC_` and never enter the browser bundle.

## Audio validation and lifecycle

The API accepts browser MediaRecorder output as multipart form data. Supported
containers are WebM/Opus, Ogg, MP4/M4A, WAV, and MP3. Validation checks both the
declared MIME type and deterministic container signatures; filenames and
extensions are ignored. Maximum bytes and the minimum client-recorded duration
are configurable.

Candidate recordings use server-generated paths:

```text
interviews/{user_id}/{session_id}/candidate/{voice_request_id}.{container}
```

Mirror audio uses:

```text
interviews/{user_id}/{session_id}/mirror/{turn_id}-{cache_digest}.{provider_container}
```

The `private-interview-audio` Supabase bucket is private. No public object URLs
are persisted. Playback uses short-lived signed URLs. Candidate audio is never
returned to the normal interview UI. Failed or unusable STT recordings are
deleted and do not create a candidate turn.

## Idempotency and persistence

`voice_turn_requests` has a unique `(session_id, client_turn_id)` constraint.
The claim RPC locks the owned ACTIVE session before claiming work. Completed
network retries return the existing interviewer turn; concurrent in-progress
duplicates receive a recoverable conflict. Stale processing requests can be
reclaimed after two minutes. The existing text turn RPC continues to allocate
unique turn indexes under the same session lock.

Candidate transcript text is stored in `turns.text` for later evidence work,
but the candidate-facing voice response and UI omit it. STT provenance and the
private audio path are attached to the candidate turn immediately after that
turn is created and before context building or Interviewer inference begins.
TTS metadata and private storage path are stored on the interviewer turn.
Signed URLs are not stored.

## TTS cache

The cache key hashes the session, provider, normalized question text, voice,
model, and language. The cache table stores only the hash and private object
metadata—not the question text. Replaying or restarting an identical planned
question in a session reuses its audio. Adaptive questions are synthesized
after their text turn has been safely persisted.

## Failure handling

- Deepgram failure, an empty/punctuation-only transcript, an oversized
  transcript, or confidence below the configured floor returns
  `TRANSCRIPTION_FAILED`. No candidate turn is created and interview state does
  not advance.
- Interviewer model failure follows the existing retry and deterministic-plan
  fallback. The candidate transcript remains stored.
- Sarvam or question-audio storage failure does not roll back either text turn.
  The response contains the question text with `audio_status=FAILED`. The UI can
  call `POST /api/v1/turns/{turn_id}/audio/retry`, which synthesizes audio only
  and never reruns the Interviewer.
- The UI always renders the current Mirror question as accessible text and
  offers typed-answer fallback. It never renders the candidate's live
  transcript.

## Latency and logging

`voice_turn_metrics` records server-observed `audio_upload_ms`, validation and
processing time, STT, context-build estimate, interviewer inference, TTS,
storage, and total turn latency. Metrics include session/turn identifiers and
provider/model names. Structured application logs include those identifiers and
timings but exclude audio bytes, signed URLs, candidate transcript text, resume
content, and question text.

`context_build_ms` is currently derived as the text-pipeline duration minus the
recorded Interviewer-agent latency because the shared text orchestrator does not
yet expose a dedicated context timer. It is explicitly an estimate.

## Retention

Database deletion cascades remove voice metadata, but PostgreSQL foreign-key
cascades cannot delete Supabase Storage objects. Production deployment must run
a storage-cleanup job when a session or account is deleted and apply a written
audio-retention period. Until that lifecycle job exists, private recordings can
become orphaned; operators should use bucket lifecycle cleanup as a compensating
control. This is a known limitation, not permission for public or indefinite
retention.

## Local configuration and smoke test

Set `DEEPGRAM_API_KEY` and `SARVAM_API_KEY`, apply migration
`202609010011_turn_based_voice.sql`, and ensure the private storage bucket was
created. Ordinary tests use mocks.

An explicit paid-provider smoke test is available and is skipped by normal CI:

```powershell
$env:RUN_VOICE_PROVIDER_SMOKE='1'
$env:VOICE_SMOKE_AUDIO_PATH='C:\safe-test-data\short-answer.webm'
$env:VOICE_SMOKE_AUDIO_MIME='audio/webm'
python -m pytest apps/api/tests/test_voice_provider_smoke.py -q
```

Use synthetic, non-sensitive audio for this test.

