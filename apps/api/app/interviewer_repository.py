from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import httpx

from .config import Settings
from .interviewer_models import (
    InterviewerTurnType,
    RelevantClaim,
    RelevantCompetency,
    StoredInterviewTurn,
)
from .schemas import Phase


TURN_COLUMNS = (
    "id,session_id,turn_index,speaker,text,turn_type,phase,primary_thread_id,"
    "response_to_turn_id,client_turn_id,agent_execution_id,model,prompt_version,"
    "latency_ms,retry_count,target_claim_ids,target_competency_ids,created_at"
)


class InterviewTurnsUnavailable(Exception):
    pass


class InterviewTurnRepository(Protocol):
    async def create_candidate_turn(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        text: str,
        client_turn_id: UUID,
        turn_type: InterviewerTurnType,
        phase: Phase,
        primary_thread_id: str | None,
    ) -> StoredInterviewTurn: ...

    async def create_interviewer_turn(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        response_to_turn_id: UUID | None,
        text: str,
        turn_type: InterviewerTurnType,
        phase: Phase,
        primary_thread_id: str,
        agent_execution_id: UUID | None,
        model: str | None,
        prompt_version: str | None,
        latency_ms: int | None,
        retry_count: int | None,
        target_claim_ids: list[UUID],
        target_competency_ids: list[UUID],
    ) -> StoredInterviewTurn: ...

    async def get_candidate_by_client_id(
        self, session_id: UUID, client_turn_id: UUID
    ) -> StoredInterviewTurn | None: ...

    async def get_response(
        self, session_id: UUID, candidate_turn_id: UUID
    ) -> StoredInterviewTurn | None: ...

    async def list_turns(
        self, session_id: UUID, *, limit: int | None = None
    ) -> list[StoredInterviewTurn]: ...

    async def get_claims(
        self, user_id: UUID, claim_ids: list[UUID]
    ) -> list[RelevantClaim]: ...

    async def get_competencies(
        self, user_id: UUID, competency_ids: list[UUID]
    ) -> list[RelevantCompetency]: ...


def _turn(row: dict[str, Any]) -> StoredInterviewTurn:
    normalized = dict(row)
    normalized["speaker"] = normalized["speaker"].upper()
    normalized["turn_type"] = normalized["turn_type"].upper()
    return StoredInterviewTurn.model_validate(normalized)


class SupabaseInterviewTurnRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise InterviewTurnsUnavailable("Supabase turn storage is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def create_candidate_turn(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        text: str,
        client_turn_id: UUID,
        turn_type: InterviewerTurnType,
        phase: Phase,
        primary_thread_id: str | None,
    ) -> StoredInterviewTurn:
        rows = await self._post(
            "rpc/create_candidate_text_turn",
            {
                "p_session_id": str(session_id),
                "p_user_id": str(user_id),
                "p_text": text,
                "p_client_turn_id": str(client_turn_id),
                "p_turn_type": turn_type.value.lower(),
                "p_phase": phase.value,
                "p_primary_thread_id": primary_thread_id,
            },
        )
        return self._one_turn(rows)

    async def create_interviewer_turn(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        response_to_turn_id: UUID | None,
        text: str,
        turn_type: InterviewerTurnType,
        phase: Phase,
        primary_thread_id: str,
        agent_execution_id: UUID | None,
        model: str | None,
        prompt_version: str | None,
        latency_ms: int | None,
        retry_count: int | None,
        target_claim_ids: list[UUID],
        target_competency_ids: list[UUID],
    ) -> StoredInterviewTurn:
        rows = await self._post(
            "rpc/create_interviewer_text_turn",
            {
                "p_session_id": str(session_id),
                "p_user_id": str(user_id),
                "p_response_to_turn_id": (
                    str(response_to_turn_id) if response_to_turn_id else None
                ),
                "p_text": text,
                "p_turn_type": turn_type.value.lower(),
                "p_phase": phase.value,
                "p_primary_thread_id": primary_thread_id,
                "p_agent_execution_id": (
                    str(agent_execution_id) if agent_execution_id else None
                ),
                "p_model": model,
                "p_prompt_version": prompt_version,
                "p_latency_ms": latency_ms,
                "p_retry_count": retry_count,
                "p_target_claim_ids": [str(item) for item in target_claim_ids],
                "p_target_competency_ids": [
                    str(item) for item in target_competency_ids
                ],
            },
        )
        return self._one_turn(rows)

    async def get_candidate_by_client_id(
        self, session_id: UUID, client_turn_id: UUID
    ) -> StoredInterviewTurn | None:
        return await self._query_one(
            {
                "session_id": f"eq.{session_id}",
                "client_turn_id": f"eq.{client_turn_id}",
                "speaker": "eq.candidate",
            }
        )

    async def get_response(
        self, session_id: UUID, candidate_turn_id: UUID
    ) -> StoredInterviewTurn | None:
        return await self._query_one(
            {
                "session_id": f"eq.{session_id}",
                "response_to_turn_id": f"eq.{candidate_turn_id}",
                "speaker": "eq.interviewer",
            }
        )

    async def list_turns(
        self, session_id: UUID, *, limit: int | None = None
    ) -> list[StoredInterviewTurn]:
        params = {
            "session_id": f"eq.{session_id}",
            "select": TURN_COLUMNS,
            "order": "turn_index.desc" if limit else "turn_index.asc",
        }
        if limit:
            params["limit"] = str(limit)
        rows = await self._get("turns", params)
        turns = [_turn(row) for row in rows]
        return list(reversed(turns)) if limit else turns

    async def get_claims(
        self, user_id: UUID, claim_ids: list[UUID]
    ) -> list[RelevantClaim]:
        if not claim_ids:
            return []
        rows = await self._get(
            "claims",
            {
                "user_id": f"eq.{user_id}",
                "id": f"in.({','.join(str(item) for item in claim_ids)})",
                "select": "id,claim_text,claim_type,source,status",
            },
        )
        return [
            RelevantClaim.model_validate(
                {
                    **row,
                    "claim_type": row["claim_type"].upper(),
                    "source": row["source"].upper(),
                    "status": row["status"].upper(),
                }
            )
            for row in rows
        ]

    async def get_competencies(
        self, user_id: UUID, competency_ids: list[UUID]
    ) -> list[RelevantCompetency]:
        if not competency_ids:
            return []
        rows = await self._get(
            "role_competencies",
            {
                "user_id": f"eq.{user_id}",
                "id": f"in.({','.join(str(item) for item in competency_ids)})",
                "select": "id,name,category,expected_level",
            },
        )
        return [RelevantCompetency.model_validate(row) for row in rows]

    async def _query_one(self, params: dict[str, str]) -> StoredInterviewTurn | None:
        rows = await self._get(
            "turns", {**params, "select": TURN_COLUMNS, "limit": "1"}
        )
        return _turn(rows[0]) if rows else None

    @staticmethod
    def _one_turn(rows: list[dict[str, Any]]) -> StoredInterviewTurn:
        try:
            return _turn(rows[0])
        except (IndexError, TypeError, ValueError) as exc:
            raise InterviewTurnsUnavailable from exc

    async def _get(self, resource: str, params: dict[str, str]) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/{resource}",
                    headers=self._headers,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise InterviewTurnsUnavailable from exc

    async def _post(
        self, resource: str, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/{resource}",
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise InterviewTurnsUnavailable from exc

