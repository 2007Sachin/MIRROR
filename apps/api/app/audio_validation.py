from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_AUDIO_MIME_TYPES = frozenset(
    {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}
)


class InvalidAudio(Exception):
    code = "INVALID_AUDIO"


class UnsupportedAudioType(InvalidAudio):
    code = "UNSUPPORTED_AUDIO_TYPE"


class AudioTooLarge(InvalidAudio):
    code = "AUDIO_TOO_LARGE"


class AudioTooShort(InvalidAudio):
    code = "AUDIO_TOO_SHORT"


@dataclass(frozen=True, slots=True)
class ValidatedAudio:
    content: bytes
    mime_type: str
    extension: str


def _detected_type(content: bytes) -> tuple[str, str] | None:
    if content.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm", "webm"
    if content.startswith(b"OggS"):
        return "audio/ogg", "ogg"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WAVE":
        return "audio/wav", "wav"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return "audio/mp4", "m4a"
    if content.startswith(b"ID3") or (
        len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
    ):
        return "audio/mpeg", "mp3"
    return None


class AudioValidator:
    def __init__(self, *, max_bytes: int, minimum_duration_ms: int) -> None:
        self._max_bytes = max_bytes
        self._minimum_duration_ms = minimum_duration_ms

    def validate(
        self, content: bytes, claimed_mime_type: str | None, duration_ms: int | None
    ) -> ValidatedAudio:
        if len(content) > self._max_bytes:
            raise AudioTooLarge
        if len(content) < 12:
            raise InvalidAudio
        if duration_ms is not None and duration_ms < self._minimum_duration_ms:
            raise AudioTooShort
        claimed = (claimed_mime_type or "").split(";", 1)[0].strip().lower()
        if claimed not in SUPPORTED_AUDIO_MIME_TYPES:
            raise UnsupportedAudioType
        detected = _detected_type(content)
        if detected is None or detected[0] != claimed:
            raise UnsupportedAudioType
        return ValidatedAudio(content=content, mime_type=detected[0], extension=detected[1])

