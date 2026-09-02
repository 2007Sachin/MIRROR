from __future__ import annotations

import base64
import binascii
from time import perf_counter
from typing import Any, Protocol

import httpx

from .voice_models import SpeechToTextResult, TextToSpeechResult


class SpeechProviderUnavailable(Exception):
    pass


class TranscriptionProviderFailure(Exception):
    pass


class SynthesisProviderFailure(Exception):
    pass


class SpeechToTextProvider(Protocol):
    provider_name: str

    async def transcribe(self, audio: bytes, mime_type: str) -> SpeechToTextResult: ...


class TextToSpeechProvider(Protocol):
    provider_name: str

    async def synthesize(self, text: str, language: str) -> TextToSpeechResult: ...


class DeepgramSpeechToTextProvider:
    provider_name = "deepgram"

    def __init__(self, api_key: str, *, model: str = "nova-3") -> None:
        self._api_key = api_key
        self.model = model

    async def transcribe(self, audio: bytes, mime_type: str) -> SpeechToTextResult:
        if not self._api_key:
            raise TranscriptionProviderFailure("Deepgram is not configured")
        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers={
                        "Authorization": f"Token {self._api_key}",
                        "Content-Type": mime_type,
                    },
                    params={
                        "model": self.model,
                        "smart_format": "true",
                        "punctuate": "true",
                        "detect_language": "true",
                    },
                    content=audio,
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
            channel = payload["results"]["channels"][0]
            alternative = channel["alternatives"][0]
            metadata = payload.get("metadata", {})
            model_ids = metadata.get("models")
            model_id = model_ids[0] if isinstance(model_ids, list) and model_ids else None
            model_info = metadata.get("model_info")
            actual_model = self.model
            if model_id and isinstance(model_info, dict):
                info = model_info.get(model_id)
                if isinstance(info, dict):
                    actual_model = str(info.get("name") or info.get("arch") or self.model)
            return SpeechToTextResult(
                transcript=str(alternative.get("transcript", "")).strip(),
                confidence=alternative.get("confidence"),
                detected_language=channel.get("detected_language"),
                provider=self.provider_name,
                model=actual_model,
                provider_metadata={
                    "request_id": metadata.get("request_id"),
                    "duration_seconds": metadata.get("duration"),
                    "language_confidence": channel.get("language_confidence"),
                    "requested_model": self.model,
                    "model_id": model_id,
                },
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise TranscriptionProviderFailure from exc


class SarvamTextToSpeechProvider:
    provider_name = "sarvam"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "bulbul:v2",
        voice: str = "anushka",
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.voice = voice

    async def synthesize(self, text: str, language: str) -> TextToSpeechResult:
        if not self._api_key:
            raise SynthesisProviderFailure("Sarvam is not configured")
        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://api.sarvam.ai/text-to-speech",
                    headers={
                        "api-subscription-key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": text,
                        "language_code": language,
                        "speaker": self.voice,
                        "model": self.model,
                    },
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
            audio = base64.b64decode(payload["audios"][0], validate=True)
            if not audio:
                raise ValueError("empty TTS audio")
            return TextToSpeechResult(
                audio_bytes=audio,
                mime_type="audio/wav",
                provider=self.provider_name,
                model=self.model,
                voice=self.voice,
                language=language,
                provider_metadata={"request_id": payload.get("request_id")},
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
            )
        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            binascii.Error,
        ) as exc:
            raise SynthesisProviderFailure from exc

