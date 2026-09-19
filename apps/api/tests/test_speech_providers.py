from __future__ import annotations

import asyncio
import base64

import httpx
import pytest

from app import speech_providers
from app.speech_providers import (
    DeepgramSpeechToTextProvider,
    SarvamSpeechToTextProvider,
    SarvamTextToSpeechProvider,
    SynthesisProviderFailure,
    TranscriptionProviderFailure,
)


class StubResponse:
    def __init__(self, payload: object, error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error

    def raise_for_status(self) -> None:
        if self._error:
            raise self._error

    def json(self) -> object:
        return self._payload


class CapturingClient:
    def __init__(self, response: StubResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self) -> CapturingClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def post(self, url: str, **kwargs: object) -> StubResponse:
        self.calls.append((url, kwargs))
        return self.response


def install_client(monkeypatch: pytest.MonkeyPatch, response: StubResponse) -> CapturingClient:
    client = CapturingClient(response)
    monkeypatch.setattr(
        speech_providers.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )
    return client


def test_deepgram_contract_and_structured_response(monkeypatch: pytest.MonkeyPatch):
    client = install_client(
        monkeypatch,
        StubResponse(
            {
                "metadata": {
                    "request_id": "request-safe",
                    "duration": 1.25,
                    "models": ["model-uuid"],
                    "model_info": {
                        "model-uuid": {"name": "nova-3-general"},
                    },
                },
                "results": {
                    "channels": [
                        {
                            "detected_language": "en",
                            "language_confidence": 0.98,
                            "alternatives": [
                                {"transcript": "  Hello Mirror.  ", "confidence": 0.94}
                            ],
                        }
                    ]
                },
            }
        ),
    )
    provider = DeepgramSpeechToTextProvider("deepgram-secret", model="nova-3")

    result = asyncio.run(provider.transcribe(b"OggS-audio", "audio/ogg"))

    assert result.transcript == "Hello Mirror."
    assert result.confidence == 0.94
    assert result.detected_language == "en"
    assert result.model == "nova-3-general"
    assert result.provider_metadata["requested_model"] == "nova-3"
    url, request = client.calls[0]
    assert url == "https://api.deepgram.com/v1/listen"
    assert request["headers"] == {
        "Authorization": "Token deepgram-secret",
        "Content-Type": "audio/ogg",
    }
    assert request["params"] == {
        "model": "nova-3",
        "smart_format": "true",
        "punctuate": "true",
        "detect_language": "true",
    }
    assert request["content"] == b"OggS-audio"


def test_deepgram_timeout_is_provider_failure(monkeypatch: pytest.MonkeyPatch):
    request = httpx.Request("POST", "https://api.deepgram.com/v1/listen")
    install_client(
        monkeypatch,
        StubResponse({}, httpx.ReadTimeout("timed out", request=request)),
    )

    with pytest.raises(TranscriptionProviderFailure):
        asyncio.run(
            DeepgramSpeechToTextProvider("secret").transcribe(b"audio", "audio/webm")
        )


def test_sarvam_contract_and_base64_audio(monkeypatch: pytest.MonkeyPatch):
    encoded = base64.b64encode(b"RIFF\x00\x00\x00\x00WAVEaudio").decode()
    client = install_client(
        monkeypatch,
        StubResponse({"request_id": "request-safe", "audios": [encoded]}),
    )
    provider = SarvamTextToSpeechProvider(
        "sarvam-secret", model="bulbul:v3", voice="priya", output_codec="mp3"
    )

    result = asyncio.run(provider.synthesize("What did you build?", "en-IN"))

    assert result.audio_bytes.startswith(b"RIFF")
    assert result.mime_type == "audio/mpeg", "must follow the requested codec"
    assert result.provider == "sarvam"
    url, request = client.calls[0]
    assert url == "https://api.sarvam.ai/text-to-speech"
    assert request["headers"] == {
        "api-subscription-key": "sarvam-secret",
        "Content-Type": "application/json",
    }
    assert request["json"] == {
        "text": "What did you build?",
        "language_code": "en-IN",
        "speaker": "priya",
        "model": "bulbul:v3",
        "output_audio_codec": "mp3",
    }


def test_sarvam_tts_codec_drives_mime_type(monkeypatch: pytest.MonkeyPatch):
    encoded = base64.b64encode(b"RIFFsome-audio-bytes").decode()
    for codec, mime in (("wav", "audio/wav"), ("mp3", "audio/mpeg"), ("flac", "audio/flac")):
        install_client(monkeypatch, StubResponse({"audios": [encoded]}))
        provider = SarvamTextToSpeechProvider("secret", output_codec=codec)
        result = asyncio.run(provider.synthesize("Question", "en-IN"))
        assert result.mime_type == mime, codec


def test_sarvam_tts_rejects_an_unsupported_codec():
    from app.speech_providers import SpeechProviderUnavailable

    with pytest.raises(SpeechProviderUnavailable):
        SarvamTextToSpeechProvider("secret", output_codec="ogg-vorbis")


def test_sarvam_malformed_audio_is_provider_failure(monkeypatch: pytest.MonkeyPatch):
    install_client(monkeypatch, StubResponse({"audios": ["not base64"]}))

    with pytest.raises(SynthesisProviderFailure):
        asyncio.run(
            SarvamTextToSpeechProvider("secret").synthesize("Question", "en-IN")
        )


def test_missing_keys_fail_only_when_provider_is_invoked():
    with pytest.raises(TranscriptionProviderFailure):
        asyncio.run(DeepgramSpeechToTextProvider("").transcribe(b"audio", "audio/webm"))
    with pytest.raises(SynthesisProviderFailure):
        asyncio.run(SarvamTextToSpeechProvider("").synthesize("Question", "en-IN"))



def test_sarvam_stt_contract_and_structured_response(monkeypatch: pytest.MonkeyPatch):
    client = install_client(
        monkeypatch,
        StubResponse(
            {
                "request_id": "stt-1",
                "transcript": "  I owned the onboarding funnel.  ",
                "language_code": "en-IN",
                "language_probability": 0.97,
            }
        ),
    )
    provider = SarvamSpeechToTextProvider(
        "sarvam-secret", model="saaras:v3", language="en-IN"
    )

    result = asyncio.run(provider.transcribe(b"audio-bytes", "audio/webm;codecs=opus"))

    assert result.transcript == "I owned the onboarding funnel."
    assert result.provider == "sarvam"
    assert result.model == "saaras:v3"
    assert result.detected_language == "en-IN"
    assert result.provider_metadata["request_id"] == "stt-1"

    url, request = client.calls[0]
    assert url == "https://api.sarvam.ai/speech-to-text"
    assert request["headers"] == {"api-subscription-key": "sarvam-secret"}
    assert request["data"] == {"model": "saaras:v3", "language_code": "en-IN"}
    filename, content, mime = request["files"]["file"]
    assert filename == "answer.webm", "codec parameters must not leak into the name"
    assert content == b"audio-bytes"
    assert mime == "audio/webm"


def test_sarvam_stt_does_not_report_language_id_as_confidence(
    monkeypatch: pytest.MonkeyPatch,
):
    """language_probability is language ID, not transcription confidence."""
    install_client(
        monkeypatch,
        StubResponse(
            {"transcript": "mumbled answer", "language_probability": 0.99}
        ),
    )

    result = asyncio.run(SarvamSpeechToTextProvider("secret").transcribe(b"a", "audio/wav"))

    assert result.confidence is None, "would misfire the turn-quality gate"
    assert result.provider_metadata["language_probability"] == 0.99


def test_sarvam_stt_omits_language_when_auto_detecting(monkeypatch: pytest.MonkeyPatch):
    client = install_client(monkeypatch, StubResponse({"transcript": "hello"}))

    asyncio.run(SarvamSpeechToTextProvider("secret", language="").transcribe(b"a", "audio/mp4"))

    _url, request = client.calls[0]
    assert "language_code" not in request["data"]
    assert request["files"]["file"][0] == "answer.m4a"


def test_sarvam_stt_missing_transcript_is_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    install_client(monkeypatch, StubResponse({"request_id": "stt-2"}))

    with pytest.raises(TranscriptionProviderFailure):
        asyncio.run(SarvamSpeechToTextProvider("secret").transcribe(b"a", "audio/wav"))


def test_sarvam_stt_without_key_fails_only_when_invoked():
    with pytest.raises(TranscriptionProviderFailure):
        asyncio.run(SarvamSpeechToTextProvider("").transcribe(b"audio", "audio/webm"))


@pytest.mark.parametrize(
    "configured,expected",
    [
        ("sarvam", "sarvam"),
        ("SARVAM", "sarvam"),
        ("  sarvam  ", "sarvam"),
        ("deepgram", "deepgram"),
        ("", "deepgram"),
        ("unrecognised", "deepgram"),
    ],
)
def test_speech_to_text_provider_switch(monkeypatch: pytest.MonkeyPatch, configured, expected):
    """An unknown value must fall back rather than leave transcription unwired."""
    from app import dependencies
    from app.config import Settings

    settings = Settings(
        speech_to_text_provider=configured,
        sarvam_api_key="sarvam-key",
        deepgram_api_key="deepgram-key",
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    dependencies.get_speech_to_text_provider.cache_clear()
    try:
        provider = dependencies.get_speech_to_text_provider()
    finally:
        dependencies.get_speech_to_text_provider.cache_clear()

    assert provider.provider_name == expected
