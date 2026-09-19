from __future__ import annotations

import base64
import binascii
import logging
from time import perf_counter
from typing import Any, Protocol

import httpx

from .voice_models import SpeechToTextResult, TextToSpeechResult

logger = logging.getLogger("mirror.speech")

# Audio uploads are large and candidate uplinks are often slow; a write that
# is merely slow should not be reported as a provider outage.
SPEECH_TIMEOUT_SECONDS = 120.0


def _provider_detail(exc: Exception) -> str:
    """Speech failures degrade silently, so the vendor's reason must be logged."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f" status={exc.response.status_code} body={exc.response.text[:400]}"
    return ""


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
            async with httpx.AsyncClient(timeout=SPEECH_TIMEOUT_SECONDS) as client:
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
            logger.warning(
                "Deepgram transcription failed (model=%s): %s%s",
                self.model, type(exc).__name__, _provider_detail(exc),
            )
            raise TranscriptionProviderFailure from exc


class SarvamSpeechToTextProvider:
    """Sarvam's Saaras transcription, for running voice in and out on one vendor."""

    provider_name = "sarvam"

    # The REST endpoint takes a file part, so the audio needs a plausible filename
    # and the container has to be one Sarvam accepts.
    _EXTENSIONS = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/wave": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "m4a",
        "audio/m4a": "m4a",
        "audio/x-m4a": "m4a",
        "audio/aac": "aac",
        "audio/ogg": "ogg",
        "audio/opus": "opus",
        "audio/flac": "flac",
        "audio/webm": "webm",
    }

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "saaras:v3",
        language: str = "en-IN",
    ) -> None:
        self._api_key = api_key
        self.model = model
        # "unknown" asks Sarvam to auto-detect rather than forcing a language.
        self.language = language

    def _filename(self, mime_type: str) -> str:
        base = (mime_type or "").split(";")[0].strip().lower()
        return f"answer.{self._EXTENSIONS.get(base, 'wav')}"

    async def transcribe(self, audio: bytes, mime_type: str) -> SpeechToTextResult:
        if not self._api_key:
            raise TranscriptionProviderFailure("Sarvam is not configured")
        started = perf_counter()
        base_mime = (mime_type or "").split(";")[0].strip().lower() or "audio/wav"
        data: dict[str, str] = {"model": self.model}
        if self.language:
            data["language_code"] = self.language
        try:
            async with httpx.AsyncClient(timeout=SPEECH_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    "https://api.sarvam.ai/speech-to-text",
                    headers={"api-subscription-key": self._api_key},
                    files={"file": (self._filename(mime_type), audio, base_mime)},
                    data=data,
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
            transcript = payload.get("transcript")
            if transcript is None:
                raise ValueError("Sarvam response did not include a transcript")
            return SpeechToTextResult(
                transcript=str(transcript).strip(),
                # Sarvam reports language-identification probability, not
                # transcription confidence. Reporting it as `confidence` would let
                # the turn-quality gate reject or accept answers on the wrong
                # signal, so it stays in metadata and confidence is left unset.
                confidence=None,
                detected_language=payload.get("language_code"),
                provider=self.provider_name,
                model=self.model,
                provider_metadata={
                    "request_id": payload.get("request_id"),
                    "language_probability": payload.get("language_probability"),
                    "requested_language": self.language or "unknown",
                    "requested_model": self.model,
                },
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning(
                "Sarvam transcription failed (model=%s): %s%s",
                self.model, type(exc).__name__, _provider_detail(exc),
            )
            raise TranscriptionProviderFailure from exc


class SarvamTextToSpeechProvider:
    provider_name = "sarvam"

    # Sarvam returns uncompressed 24kHz WAV by default, which is ~700KB for a
    # short interview question. That has to be stored and then fetched by the
    # candidate, so a compressed codec is materially faster on a slow link.
    _CODEC_MIME = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "flac": "audio/flac",
        "aac": "audio/aac",
        "opus": "audio/ogg",
    }

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "bulbul:v3",
        voice: str = "priya",
        output_codec: str = "mp3",
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.voice = voice
        self.output_codec = (output_codec or "wav").strip().lower()
        if self.output_codec not in self._CODEC_MIME:
            raise SpeechProviderUnavailable(
                f"unsupported Sarvam audio codec: {output_codec}"
            )

    async def synthesize(self, text: str, language: str) -> TextToSpeechResult:
        if not self._api_key:
            raise SynthesisProviderFailure("Sarvam is not configured")
        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=SPEECH_TIMEOUT_SECONDS) as client:
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
                        "output_audio_codec": self.output_codec,
                    },
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
            audio = base64.b64decode(payload["audios"][0], validate=True)
            if not audio:
                raise ValueError("empty TTS audio")
            return TextToSpeechResult(
                audio_bytes=audio,
                mime_type=self._CODEC_MIME[self.output_codec],
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
            logger.warning(
                "Sarvam synthesis failed (model=%s, voice=%s): %s%s",
                self.model, self.voice, type(exc).__name__, _provider_detail(exc),
            )
            raise SynthesisProviderFailure from exc

