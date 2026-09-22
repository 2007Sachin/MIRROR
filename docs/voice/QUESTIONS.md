# Open questions (defaults in use)

1. Where is the API hosted relative to the Supabase project (`kiflai...`)? Default: assume different regions; measure, then co-locate.
2. Can you supply 30+ short recordings of real Indian-English speech with reference transcripts? Default: no accuracy claims; WER stays unmeasured.
3. Is a Safari/iOS and Android test device available? Default: Chrome desktop only.
4. Is the goal "last word to first audio p50 1.5 s" for production traffic or a local demo? Default: production, measured after co-locating.
5. Draft retention: 14 days, audio retention unchanged.

6. The interviewer model call failed on every turn with a provider 400 (since fixed; the app now runs on Sarvam) (`interviewer_output`: `requested_phase_transition` uses an `anyOf` Groq's strict schema mode rejects), so the fallback question is used each turn. Found by the harness. Default: not touched (outside this brief); the interviewer time in the numbers is therefore a failed call (about 0.3 s). A real model call would add roughly 1 to 2 s. Should I fix the schema next?
7. The API runs only locally (`APP_URL=http://localhost:3000`); no deployed host exists to measure from. Default: numbers are from this machine (Bengaluru) to Supabase; the region recommendation will use those.
8. Harness audio is synthetic speech from the TTS provider (latency only). Default: no accuracy claims. Drop real recordings in `tests/fixtures/audio` to replace it.
