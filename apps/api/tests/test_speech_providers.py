from __future__ import annotations

import asyncio
import base64

import httpx
import pytest

from app import speech_providers
from app.speech_providers import (
    DeepgramSpeechToTextProvider,
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
        "sarvam-secret", model="bulbul:v2", voice="anushka"
    )

    result = asyncio.run(provider.synthesize("What did you build?", "en-IN"))

    assert result.audio_bytes.startswith(b"RIFF")
    assert result.mime_type == "audio/wav"
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
        "speaker": "anushka",
        "model": "bulbul:v2",
    }


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

