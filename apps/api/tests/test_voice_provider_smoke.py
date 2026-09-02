"""Explicitly opt-in live provider check; never enabled by ordinary CI."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from app.speech_providers import (
    DeepgramSpeechToTextProvider,
    SarvamTextToSpeechProvider,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_VOICE_PROVIDER_SMOKE") != "1",
    reason="set RUN_VOICE_PROVIDER_SMOKE=1 to call live speech providers",
)


def test_live_deepgram_and_sarvam_round_trip() -> None:
    audio_path = Path(os.environ["VOICE_SMOKE_AUDIO_PATH"])
    mime_type = os.getenv("VOICE_SMOKE_AUDIO_MIME", "audio/webm")
    stt = DeepgramSpeechToTextProvider(os.environ["DEEPGRAM_API_KEY"])
    tts = SarvamTextToSpeechProvider(os.environ["SARVAM_API_KEY"])
    transcript = asyncio.run(stt.transcribe(audio_path.read_bytes(), mime_type))
    assert transcript.transcript.strip()
    spoken = asyncio.run(tts.synthesize("Voice provider check complete.", "en-IN"))
    assert spoken.audio_bytes.startswith(b"RIFF")

