from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from urllib.parse import quote
from uuid import UUID

import httpx

from .config import Settings
from .voice_models import (
    OwnedVoiceTurn,
    TtsCacheRecord,
    VoiceLatencyMetrics,
    VoiceRequestClaim,
    VoiceRequestRecord,
)


class VoicePersistenceUnavailable(Exception):
    pass


class InterviewAudioStorage(Protocol):
    async def upload(
        self, path: str, content: bytes, mime_type: str, *, upsert: bool = False
    ) -> None: ...
    async def delete(self, path: str) -> None: ...
    async def signed_url(self, path: str, expires_seconds: int) -> str: ...


class VoiceRepository(Protocol):
    async def claim_request(
        self, session_id: UUID, user_id: UUID, client_turn_id: UUID,
        duration_ms: int | None
    ) -> VoiceRequestClaim: ...
    async def set_request_audio(
        self, request_id: UUID, user_id: UUID, path: str, mime_type: str
    ) -> None: ...
    async def fail_request(
        self, request_id: UUID, user_id: UUID, error_code: str
    ) -> None: ...
    async def complete_request(
        self, request_id: UUID, user_id: UUID, candidate_turn_id: UUID,
        interviewer_turn_id: UUID, response: dict[str, Any]
    ) -> None: ...
    async def attach_candidate_audio(
        self, turn_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> None: ...
    async def attach_interviewer_audio(
        self, turn_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> None: ...
    async def get_owned_turn(
        self, turn_id: UUID, user_id: UUID
    ) -> OwnedVoiceTurn | None: ...
    async def get_cache(
        self, cache_key: str, user_id: UUID, session_id: UUID
    ) -> TtsCacheRecord | None: ...
    async def save_cache(self, record: TtsCacheRecord, text_hash: str) -> None: ...
    async def record_metrics(self, metrics: VoiceLatencyMetrics) -> None: ...


class SupabaseInterviewAudioStorage:
    bucket = "private-interview-audio"

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise VoicePersistenceUnavailable("Interview audio storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._key = settings.supabase_service_role_key

    @property
    def _headers(self) -> dict[str, str]:
        return {"apikey": self._key, "Authorization": f"Bearer {self._key}"}

    async def upload(
        self, path: str, content: bytes, mime_type: str, *, upsert: bool = False
    ) -> None:
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    f"{self._url}/storage/v1/object/{self.bucket}/{quote(path, safe='/')}",
                    headers={
                        **self._headers,
                        "Content-Type": mime_type,
                        "x-upsert": "true" if upsert else "false",
                    },
                    content=content,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VoicePersistenceUnavailable from exc

    async def delete(self, path: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.delete(
                    f"{self._url}/storage/v1/object/{self.bucket}/{quote(path, safe='/')}",
                    headers=self._headers,
                )
                if response.status_code not in (200, 404):
                    response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VoicePersistenceUnavailable from exc

    async def signed_url(self, path: str, expires_seconds: int) -> str:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self._url}/storage/v1/object/sign/{self.bucket}/{quote(path, safe='/')}",
                    headers={**self._headers, "Content-Type": "application/json"},
                    json={"expiresIn": expires_seconds},
                )
                response.raise_for_status()
                signed = response.json()["signedURL"]
            return signed if str(signed).startswith("http") else f"{self._url}/storage/v1{signed}"
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise VoicePersistenceUnavailable from exc


class SupabaseVoiceRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise VoicePersistenceUnavailable("Voice persistence is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        key = settings.supabase_service_role_key
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def claim_request(
        self, session_id: UUID, user_id: UUID, client_turn_id: UUID,
        duration_ms: int | None
    ) -> VoiceRequestClaim:
        rows = await self._request(
            "POST", "rpc/claim_voice_turn_request",
            json={
                "p_session_id": str(session_id),
                "p_user_id": str(user_id),
                "p_client_turn_id": str(client_turn_id),
                "p_recorded_duration_ms": duration_ms,
            },
        )
        try:
            row = dict(rows[0])
            claimed = bool(row.pop("claimed"))
            return VoiceRequestClaim(
                request=VoiceRequestRecord.model_validate(row), claimed=claimed
            )
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise VoicePersistenceUnavailable from exc

    async def set_request_audio(
        self, request_id: UUID, user_id: UUID, path: str, mime_type: str
    ) -> None:
        await self._patch_request(
            request_id, user_id,
            {"candidate_audio_path": path, "candidate_audio_mime_type": mime_type},
        )

    async def fail_request(
        self, request_id: UUID, user_id: UUID, error_code: str
    ) -> None:
        await self._patch_request(
            request_id, user_id, {"status": "FAILED", "error_code": error_code}
        )

    async def complete_request(
        self, request_id: UUID, user_id: UUID, candidate_turn_id: UUID,
        interviewer_turn_id: UUID, response: dict[str, Any]
    ) -> None:
        await self._patch_request(
            request_id,
            user_id,
            {
                "status": "COMPLETED",
                "candidate_turn_id": str(candidate_turn_id),
                "interviewer_turn_id": str(interviewer_turn_id),
                "response_json": response,
                "error_code": None,
            },
        )

    async def _patch_request(
        self, request_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> None:
        await self._request(
            "PATCH", "voice_turn_requests",
            params={"id": f"eq.{request_id}", "user_id": f"eq.{user_id}"},
            json={**values, "updated_at": datetime.now().astimezone().isoformat()},
            prefer="return=minimal",
        )

    async def attach_candidate_audio(
        self, turn_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> None:
        await self._patch_owned_turn(turn_id, user_id, values)

    async def attach_interviewer_audio(
        self, turn_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> None:
        await self._patch_owned_turn(turn_id, user_id, values)

    async def _patch_owned_turn(
        self, turn_id: UUID, user_id: UUID, values: dict[str, Any]
    ) -> None:
        if await self.get_owned_turn(turn_id, user_id) is None:
            raise VoicePersistenceUnavailable("owned turn not found")
        await self._request(
            "PATCH", "turns", params={"id": f"eq.{turn_id}"}, json=values,
            prefer="return=minimal",
        )

    async def get_owned_turn(
        self, turn_id: UUID, user_id: UUID
    ) -> OwnedVoiceTurn | None:
        rows = await self._request(
            "GET", "turns",
            params={
                "id": f"eq.{turn_id}",
                "sessions.user_id": f"eq.{user_id}",
                "select": (
                    "id,session_id,turn_index,speaker,text,turn_type,phase,"
                    "audio_storage_path,audio_mime_type,audio_status,tts_provider,tts_model,"
                    "sessions!inner(user_id)"
                ),
                "limit": "1",
            },
        )
        if not rows:
            return None
        row = dict(rows[0])
        session = row.pop("sessions")
        row["user_id"] = session["user_id"] if isinstance(session, dict) else session[0]["user_id"]
        row["speaker"] = str(row["speaker"]).upper()
        row["turn_type"] = str(row["turn_type"]).upper()
        return OwnedVoiceTurn.model_validate(row)

    async def get_cache(
        self, cache_key: str, user_id: UUID, session_id: UUID
    ) -> TtsCacheRecord | None:
        rows = await self._request(
            "GET", "tts_audio_cache",
            params={
                "cache_key": f"eq.{cache_key}", "user_id": f"eq.{user_id}",
                "session_id": f"eq.{session_id}",
                "select": "cache_key,user_id,session_id,provider,model,voice,language,storage_path,mime_type",
                "limit": "1",
            },
        )
        return TtsCacheRecord.model_validate(rows[0]) if rows else None

    async def save_cache(self, record: TtsCacheRecord, text_hash: str) -> None:
        await self._request(
            "POST", "tts_audio_cache",
            json={**record.model_dump(mode="json"), "normalized_text_hash": text_hash},
            prefer="resolution=merge-duplicates,return=minimal",
        )

    async def record_metrics(self, metrics: VoiceLatencyMetrics) -> None:
        await self._request(
            "POST", "voice_turn_metrics", json=metrics.model_dump(mode="json"),
            prefer="return=minimal",
        )

    async def _request(
        self, method: str, resource: str, *, params: dict[str, str] | None = None,
        json: Any = None, prefer: str | None = None
    ) -> list[dict[str, Any]]:
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.request(
                    method, f"{self._url}/rest/v1/{resource}", headers=headers,
                    params=params, json=json,
                )
                response.raise_for_status()
                if response.status_code == 204 or not response.content:
                    return []
                value = response.json()
                return value if isinstance(value, list) else [value]
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise VoicePersistenceUnavailable from exc

