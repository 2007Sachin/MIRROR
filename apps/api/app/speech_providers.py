from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
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


def decode_to_pcm16k(audio: bytes) -> bytes:
    """Any browser container (webm/opus, mp4, ogg, wav, mp3) to 16 kHz mono signed 16-bit PCM."""
    import av  # imported lazily: only the streaming path needs it

    pcm = bytearray()
    with av.open(io.BytesIO(audio)) as container:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in container.decode(stream):
            for resampled in resampler.resample(frame):
                pcm += bytes(resampled.planes[0])[: resampled.samples * 2]
        for resampled in resampler.resample(None):
            pcm += bytes(resampled.planes[0])[: resampled.samples * 2]
    return bytes(pcm)


class SarvamStreamingSpeechToTextProvider(SarvamSpeechToTextProvider):
    """Sarvam over its WebSocket, which has no 30 second cap (flag: VOICE_STREAMING_STT).

    Answers up to `rest_limit_seconds` keep using the REST endpoint unchanged. Longer answers are
    decoded to PCM and streamed in one-second chunks, then flushed for the final transcript.
    """

    WS_URL = "wss://api.sarvam.ai/speech-to-text/ws"
    CHUNK_BYTES = 32_000  # one second of 16 kHz mono s16
    MAX_SECONDS = 600

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "saaras:v3",
        language: str = "en-IN",
        rest_limit_seconds: float = 25.0,
        ws_url: str | None = None,
        grace_seconds: float = 0.7,
    ) -> None:
        super().__init__(api_key, model=model, language=language)
        self._rest_limit = rest_limit_seconds
        self._ws_url = ws_url or self.WS_URL
        self._grace = grace_seconds

    async def transcribe(self, audio: bytes, mime_type: str) -> SpeechToTextResult:
        if not self._api_key:
            raise TranscriptionProviderFailure("Sarvam is not configured")
        try:
            pcm = await asyncio.to_thread(decode_to_pcm16k, audio)
        except Exception:  # noqa: BLE001 - an undecodable file falls back to the REST path
            logger.warning("Could not decode audio for streaming; using REST", exc_info=True)
            return await super().transcribe(audio, mime_type)
        seconds = len(pcm) / 32_000
        if seconds <= self._rest_limit:
            return await super().transcribe(audio, mime_type)
        if seconds > self.MAX_SECONDS:
            raise TranscriptionProviderFailure("audio is too long to transcribe")
        return await self._stream(pcm, seconds)

    async def _stream(self, pcm: bytes, seconds: float) -> SpeechToTextResult:
        import websockets

        started = perf_counter()
        query = f"language-code={self.language or 'unknown'}&model={self.model}&sample_rate=16000&input_audio_codec=pcm_s16le"
        parts: list[str] = []
        meta: dict[str, Any] = {}
        try:
            async with websockets.connect(
                f"{self._ws_url}?{query}",
                additional_headers={"Api-Subscription-Key": self._api_key},
                max_size=None,
                open_timeout=10,
            ) as ws:
                for offset in range(0, len(pcm), self.CHUNK_BYTES):
                    chunk = base64.b64encode(pcm[offset : offset + self.CHUNK_BYTES]).decode()
                    await ws.send(json.dumps({"audio": {"data": chunk, "sample_rate": "16000", "encoding": "audio/wav"}}))
                await ws.send(json.dumps({"type": "flush"}))
                wait = 30.0  # first result may take a moment; later ones follow closely
                while True:
                    try:
                        message = json.loads(await asyncio.wait_for(ws.recv(), timeout=wait))
                    except asyncio.TimeoutError:
                        break
                    except websockets.ConnectionClosed:
                        break
                    kind, data = message.get("type"), message.get("data") or {}
                    if kind == "error":
                        raise ValueError(f"Sarvam streaming error: {data.get('code')}")
                    if kind == "data":
                        text = str(data.get("transcript") or "").strip()
                        if text:
                            parts.append(text)
                        meta = {
                            "request_id": data.get("request_id"),
                            "language_code": data.get("language_code") or meta.get("language_code"),
                            "language_probability": data.get("language_probability"),
                        }
                        wait = self._grace
        except (OSError, ValueError, TypeError, websockets.WebSocketException) as exc:
            logger.warning(
                "Sarvam streaming transcription failed (model=%s): %s", self.model, type(exc).__name__, exc_info=True
            )
            raise TranscriptionProviderFailure from exc
        transcript = " ".join(parts).strip()
        if not transcript:
            raise TranscriptionProviderFailure("Sarvam streaming returned no transcript")
        return SpeechToTextResult(
            transcript=transcript,
            confidence=None,
            detected_language=meta.get("language_code"),
            provider=self.provider_name,
            model=self.model,
            provider_metadata={
                "request_id": meta.get("request_id"),
                "language_probability": meta.get("language_probability"),
                "requested_language": self.language or "unknown",
                "requested_model": self.model,
                "streaming": True,
                "audio_seconds": round(seconds, 1),
            },
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
        )


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

