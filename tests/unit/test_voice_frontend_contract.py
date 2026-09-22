from pathlib import Path


VOICE_INTERVIEW = Path("apps/web/src/components/voice-interview.tsx")


def test_voice_interview_uses_automatic_conversation_turns() -> None:
    source = VOICE_INTERVIEW.read_text(encoding="utf-8")

    assert "VOICE_START_THRESHOLD" in source
    assert "END_OF_TURN_SILENCE_MS" in source
    assert "beginListening" in source
    assert "stopCapture(false)" in source
    assert "Join interview" in source
    assert "Start recording" not in source
    assert "Submit recording" not in source


def test_voice_interview_preserves_accessible_fallback_controls() -> None:
    source = VOICE_INTERVIEW.read_text(encoding="utf-8")

    assert 'aria-label={muted ? "Unmute microphone" : "Mute microphone"}' in source
    assert "Type your answer" in source
    assert "Replay question" in source
    assert "Step away" in (VOICE_INTERVIEW.parents[1] / "lib" / "copy.ts").read_text(encoding="utf-8")
    assert "saveAndContinueLater" in source


def test_live_captions_are_interim_only_and_browser_capability_aware() -> None:
    source = VOICE_INTERVIEW.read_text(encoding="utf-8")

    assert "SpeechRecognition" in source
    assert "interimResults = true" in source
    assert "startLiveTranscription" in source
    assert "You · Live" in source
    assert "confirmed server transcript remains the interview record" in source
    assert "uploadVoiceTurn" in source


def test_closing_turn_persists_completion_before_opening_the_workspace() -> None:
    source = VOICE_INTERVIEW.read_text(encoding="utf-8")

    assert "completeInterview" in source
    assert "mirrorApi.endInterview(sessionId)" in source
    assert 'router.replace("/dashboard")' in source
    assert 'router.replace(`/app/report/' not in source
    assert "signOut" not in source
    assert 'disabled={processing || roomState === "CANDIDATE_SPEAKING" || closing}' in source
    assert "uploadAbortRef.current?.abort();\n    audioRef.current?.pause();" not in source
