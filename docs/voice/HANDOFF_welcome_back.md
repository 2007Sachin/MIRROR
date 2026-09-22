# Welcome back: browser wiring

The start endpoints now return, only when a saved conversation was resumed:
`welcome_back: true`, `welcome_text`, and (voice only) `welcome_audio_url`.
No extra interviewer turn is stored, so history is unchanged. The types are already
in `apps/web/src/lib/api.ts` (`InterviewStart`, `VoiceTurnResult`).

Change in `apps/web/src/components/voice-interview.tsx`, right after
`api.startVoiceInterview(id)` resolves and before the question is shown or played:

```ts
if (start.welcome_back && start.welcome_text) {
  // show the line as a calm status above the question, not as a transcript turn
  setWelcomeLine(start.welcome_text);
  if (start.welcome_audio_url) {
    await playAudioUrl(start.welcome_audio_url).catch(() => undefined); // wait for it to end
  }
  setWelcomeLine(null);
}
// then the existing code: show question_text and play start.audio_url
```

Notes: play the welcome audio to the end before the question audio; if it fails to play,
continue straight to the question. Do not add the welcome line to the message history.
