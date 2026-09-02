from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

import httpx

from .agents.definitions import AgentExecutionResult
from .config import Settings
from .skeptic_models import (
    SkepticAdminSessionResult,
    SkepticAdminTurnResult,
    SkepticAnalysis,
    SkepticClaim,
    SkepticClaimUpdate,
    SkepticEntity,
    SkepticFlagProposal,
    SkepticJob,
    SkepticObservation,
    SkepticProcessSummary,
    SkepticRelation,
    SkepticRetrievalData,
    SkepticTurn,
    StoredSkepticFlag,
    StoredSkepticObservation,
)


TURN_COLUMNS = (
    "id,session_id,turn_index,speaker,text,turn_type,phase,primary_thread_id,created_at"
)
CLAIM_COLUMNS = (
    "id,claim_text,claim_type,source,status,source_reference,confidence"
)


class SkepticPersistenceUnavailable(Exception):
    pass


class SkepticRepository(Protocol):
    async def publish_candidate_turn_completed(
        self, session_id: UUID, user_id: UUID, turn_id: UUID
    ) -> None: ...

    async def claim_job(self, worker_id: str, max_attempts: int) -> SkepticJob | None: ...

    async def load_retrieval_data(self, turn_id: UUID) -> SkepticRetrievalData: ...

    async def spoken_claim_exists(
        self, user_id: UUID, source_turn_id: UUID, normalized_text: str
    ) -> bool: ...

    async def create_observation(
        self,
        session_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        observation: SkepticObservation,
        dedupe_key: str,
    ) -> bool: ...

    async def create_claim_update_proposal(
        self,
        session_id: UUID,
        user_id: UUID,
        source_turn_id: UUID,
        execution_id: UUID,
        proposal: SkepticClaimUpdate,
        dedupe_key: str,
    ) -> bool: ...

    async def create_flag(
        self,
        session_id: UUID,
        user_id: UUID,
        turn_index: int,
        execution_id: UUID,
        proposal: SkepticFlagProposal,
        dedupe_key: str,
        shadow_mode: bool,
    ) -> bool: ...

    async def record_analysis(
        self,
        job: SkepticJob,
        execution: AgentExecutionResult,
        analysis: SkepticAnalysis | None,
        summary: SkepticProcessSummary,
        shadow_mode: bool,
    ) -> None: ...

    async def complete_job(self, job_id: UUID) -> None: ...

    async def fail_job(
        self,
        job: SkepticJob,
        failure_type: str,
        *,
        retry: bool,
        retry_base_seconds: int,
    ) -> None: ...

    async def is_admin(self, user_id: UUID) -> bool: ...

    async def inspect_session(self, session_id: UUID) -> SkepticAdminSessionResult | None: ...


def _turn(row: dict[str, Any]) -> SkepticTurn:
    return SkepticTurn.model_validate(
        {
            **row,
            "speaker": str(row["speaker"]).upper(),
            "turn_type": str(row["turn_type"]).upper(),
        }
    )


class SupabaseSkepticRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise SkepticPersistenceUnavailable("Skeptic persistence is not configured")
        self._url = settings.next_public_supabase_url.rstrip("/")
        key = settings.supabase_service_role_key
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    async def publish_candidate_turn_completed(
        self, session_id: UUID, user_id: UUID, turn_id: UUID
    ) -> None:
        await self._post(
            "rpc/enqueue_skeptic_turn_analysis",
            {
                "p_session_id": str(session_id),
                "p_user_id": str(user_id),
                "p_turn_id": str(turn_id),
                "p_prompt_version": "v1",
            },
        )

    async def claim_job(self, worker_id: str, max_attempts: int) -> SkepticJob | None:
        rows = await self._post(
            "rpc/claim_skeptic_turn_analysis",
            {"p_worker_id": worker_id, "p_max_attempts": max_attempts},
        )
        if not rows:
            return None
        row = rows[0]
        payload = row.get("payload")
        if not isinstance(payload, dict):
            raise SkepticPersistenceUnavailable("Skeptic job payload is invalid")
        try:
            return SkepticJob(
                id=row["id"],
                session_id=payload["session_id"],
                turn_id=payload["turn_id"],
                user_id=payload["user_id"],
                attempts=row["attempts"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SkepticPersistenceUnavailable("Skeptic job payload is invalid") from exc

    async def load_retrieval_data(self, turn_id: UUID) -> SkepticRetrievalData:
        current_rows = await self._get(
            "turns",
            {
                "id": f"eq.{turn_id}",
                "speaker": "eq.candidate",
                "select": f"{TURN_COLUMNS},sessions!inner(user_id)",
                "limit": "1",
            },
        )
        if not current_rows:
            raise SkepticPersistenceUnavailable("Candidate turn no longer exists")
        current_row = dict(current_rows[0])
        session = current_row.pop("sessions")
        user_id = session["user_id"] if isinstance(session, dict) else session[0]["user_id"]
        current = _turn(current_row)
        prior_rows = await self._get(
            "turns",
            {
                "session_id": f"eq.{current.session_id}",
                "turn_index": f"lt.{current.turn_index}",
                "select": TURN_COLUMNS,
                "order": "turn_index.desc",
                "limit": "8",
            },
        )
        claim_rows = await self._get(
            "claims",
            {
                "user_id": f"eq.{user_id}",
                "or": f"(session_id.eq.{current.session_id},session_id.is.null)",
                "select": CLAIM_COLUMNS,
                "order": "created_at.desc",
                "limit": "200",
            },
        )
        entity_rows = await self._get(
            "claim_entities",
            {
                "user_id": f"eq.{user_id}",
                "select": "id,entity_type,canonical_name",
                "limit": "200",
            },
        )
        relation_rows = await self._get(
            "claim_relations",
            {
                "user_id": f"eq.{user_id}",
                "select": (
                    "source_entity_type,source_entity_id,relation_type,"
                    "target_entity_type,target_entity_id,confidence"
                ),
                "limit": "500",
            },
        )
        entity_ids_by_claim: dict[UUID, list[UUID]] = {}
        for row in relation_rows:
            if str(row["source_entity_type"]).upper() == "CLAIM":
                entity_ids_by_claim.setdefault(UUID(str(row["source_entity_id"])), []).append(
                    UUID(str(row["target_entity_id"]))
                )
        claims = [
            SkepticClaim.model_validate(
                {
                    **row,
                    "claim_type": str(row["claim_type"]).upper(),
                    "source": str(row["source"]).upper(),
                    "status": str(row["status"]).upper(),
                    "related_entity_ids": entity_ids_by_claim.get(UUID(str(row["id"])), []),
                }
            )
            for row in claim_rows
        ]
        return SkepticRetrievalData(
            session_id=current.session_id,
            user_id=user_id,
            current_turn=current,
            prior_turns=[_turn(row) for row in reversed(prior_rows)],
            claims=claims,
            entities=[SkepticEntity.model_validate(row) for row in entity_rows],
            relations=[SkepticRelation.model_validate(row) for row in relation_rows],
        )

    async def spoken_claim_exists(
        self, user_id: UUID, source_turn_id: UUID, normalized_text: str
    ) -> bool:
        rows = await self._get(
            "claims",
            {
                "user_id": f"eq.{user_id}",
                "source": "eq.spoken",
                "source_reference": f"eq.turn:{source_turn_id}",
                "select": "claim_text",
                "limit": "50",
            },
        )
        target = " ".join(normalized_text.split()).casefold()
        return any(
            " ".join(str(row.get("claim_text", "")).split()).casefold() == target
            for row in rows
        )

    async def create_observation(
        self,
        session_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        observation: SkepticObservation,
        dedupe_key: str,
    ) -> bool:
        rows = await self._post(
            "skeptic_observations",
            {
                "session_id": str(session_id),
                "user_id": str(user_id),
                "source_turn_id": str(observation.source_turn_id),
                "skeptic_execution_id": str(execution_id),
                "observation_type": observation.observation_type.value,
                "summary": observation.summary,
                "confidence": observation.confidence,
                "related_claim_ids": [str(item) for item in observation.related_claim_ids],
                "related_turn_ids": [str(item) for item in observation.related_turn_ids],
                "dedupe_key": dedupe_key,
            },
            prefer="return=representation",
            ignore_conflict=True,
        )
        return bool(rows)

    async def create_claim_update_proposal(
        self,
        session_id: UUID,
        user_id: UUID,
        source_turn_id: UUID,
        execution_id: UUID,
        proposal: SkepticClaimUpdate,
        dedupe_key: str,
    ) -> bool:
        rows = await self._post(
            "skeptic_claim_update_proposals",
            {
                "session_id": str(session_id),
                "user_id": str(user_id),
                "source_turn_id": str(source_turn_id),
                "claim_id": str(proposal.claim_id),
                "skeptic_execution_id": str(execution_id),
                "proposed_status": proposal.proposed_status.value.lower(),
                "confidence": proposal.confidence,
                "reason": proposal.reason,
                "related_turn_ids": [str(item) for item in proposal.related_turn_ids],
                "dedupe_key": dedupe_key,
            },
            prefer="return=representation",
            ignore_conflict=True,
        )
        return bool(rows)

    async def create_flag(
        self,
        session_id: UUID,
        user_id: UUID,
        turn_index: int,
        execution_id: UUID,
        proposal: SkepticFlagProposal,
        dedupe_key: str,
        shadow_mode: bool,
    ) -> bool:
        rows = await self._post(
            "flags",
            {
                "session_id": str(session_id),
                "claim_id": str(proposal.claim_id) if proposal.claim_id else None,
                "flag_type": proposal.flag_type.value.lower(),
                "severity": proposal.severity.value,
                "confidence": proposal.confidence,
                "reason": proposal.reason,
                "suggested_probe": proposal.suggested_probe,
                "safe_to_surface": proposal.safe_to_surface,
                "source_turn_id": str(proposal.source_turn_id),
                "related_turn_ids": [str(item) for item in proposal.related_turn_ids],
                "detected_at_turn": turn_index,
                "shadow_mode": shadow_mode,
                "skeptic_execution_id": str(execution_id),
                "dedupe_key": dedupe_key,
                "distinction": proposal.flag_type.value.lower(),
            },
            prefer="return=representation",
            ignore_conflict=True,
        )
        return bool(rows)

    async def record_analysis(
        self,
        job: SkepticJob,
        execution: AgentExecutionResult,
        analysis: SkepticAnalysis | None,
        summary: SkepticProcessSummary,
        shadow_mode: bool,
    ) -> None:
        await self._post(
            "skeptic_analyses",
            {
                "skeptic_execution_id": str(execution.execution_id),
                "session_id": str(job.session_id),
                "user_id": str(job.user_id),
                "source_turn_id": str(job.turn_id),
                "model": execution.model,
                "prompt_version": execution.prompt_version,
                "shadow_mode": shadow_mode,
                "success": execution.success,
                "structured_output": analysis.model_dump(mode="json") if analysis else None,
                "latency_ms": execution.latency_ms,
                "retry_count": execution.retry_count,
                **summary.model_dump(mode="json"),
                "failure_type": execution.error_type.value if execution.error_type else None,
                "completed_at": datetime.now(UTC).isoformat(),
            },
            prefer="return=minimal",
        )

    async def complete_job(self, job_id: UUID) -> None:
        await self._patch(
            "jobs",
            {"id": f"eq.{job_id}"},
            {
                "status": "complete",
                "completed_at": datetime.now(UTC).isoformat(),
                "locked_at": None,
                "locked_by": None,
            },
        )

    async def fail_job(
        self,
        job: SkepticJob,
        failure_type: str,
        *,
        retry: bool,
        retry_base_seconds: int,
    ) -> None:
        values: dict[str, Any] = {
            "status": "pending" if retry else "failed",
            "error": failure_type[:500],
            "locked_at": None,
            "locked_by": None,
        }
        if retry:
            delay = retry_base_seconds * (2 ** max(0, job.attempts - 1))
            values["run_after"] = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
        else:
            values["completed_at"] = datetime.now(UTC).isoformat()
        await self._patch("jobs", {"id": f"eq.{job.id}"}, values)

    async def is_admin(self, user_id: UUID) -> bool:
        return bool(
            await self._get(
                "users",
                {"id": f"eq.{user_id}", "role": "eq.admin", "select": "id", "limit": "1"},
            )
        )

    async def inspect_session(self, session_id: UUID) -> SkepticAdminSessionResult | None:
        sessions = await self._get(
            "sessions", {"id": f"eq.{session_id}", "select": "id", "limit": "1"}
        )
        if not sessions:
            return None
        turns = [
            _turn(row)
            for row in await self._get(
                "turns",
                {
                    "session_id": f"eq.{session_id}",
                    "speaker": "eq.candidate",
                    "select": TURN_COLUMNS,
                    "order": "turn_index.asc",
                },
            )
        ]
        analyses = await self._get(
            "skeptic_analyses",
            {
                "session_id": f"eq.{session_id}",
                "select": "*",
                "order": "created_at.desc",
            },
        )
        observations = await self._get(
            "skeptic_observations",
            {"session_id": f"eq.{session_id}", "select": "*", "order": "created_at.asc"},
        )
        flags = await self._get(
            "flags",
            {"session_id": f"eq.{session_id}", "select": "*", "order": "created_at.asc"},
        )
        latest_by_turn: dict[str, dict[str, Any]] = {}
        for row in analyses:
            latest_by_turn.setdefault(str(row["source_turn_id"]), row)
        return SkepticAdminSessionResult(
            session_id=session_id,
            shadow_mode=all(bool(row.get("shadow_mode", True)) for row in analyses),
            turns=[
                SkepticAdminTurnResult(
                    turn=turn,
                    **self._execution_fields(latest_by_turn.get(str(turn.id))),
                    observations=[
                        self._observation(row)
                        for row in observations
                        if str(row["source_turn_id"]) == str(turn.id)
                    ],
                    flags=[
                        self._flag(row)
                        for row in flags
                        if str(row.get("source_turn_id")) == str(turn.id)
                    ],
                )
                for turn in turns
            ],
        )

    @staticmethod
    def _execution_fields(row: dict[str, Any] | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {
            "skeptic_execution_id": row["skeptic_execution_id"],
            "model": row["model"],
            "prompt_version": row["prompt_version"],
            "latency_ms": row["latency_ms"],
            "retry_count": row["retry_count"],
            "failure_type": row["failure_type"],
        }

    @staticmethod
    def _observation(row: dict[str, Any]) -> StoredSkepticObservation:
        return StoredSkepticObservation.model_validate(
            {
                "id": row["id"],
                "observation_type": row["observation_type"],
                "summary": row["summary"],
                "confidence": row["confidence"],
                "source_turn_id": row["source_turn_id"],
                "related_claim_ids": row["related_claim_ids"],
                "related_turn_ids": row["related_turn_ids"],
                "created_at": row["created_at"],
            }
        )

    @staticmethod
    def _flag(row: dict[str, Any]) -> StoredSkepticFlag:
        return StoredSkepticFlag.model_validate(
            {
                "id": row["id"],
                "session_id": row["session_id"],
                "claim_id": row["claim_id"],
                "flag_type": str(row["flag_type"]).upper(),
                "severity": str(row["severity"]).upper(),
                "confidence": row["confidence"],
                "reason": row["reason"],
                "suggested_probe": row["suggested_probe"],
                "safe_to_surface": row["safe_to_surface"],
                "source_turn_id": row["source_turn_id"],
                "related_turn_ids": row["related_turn_ids"],
                "detected_at_turn": row["detected_at_turn"],
                "consumed": row["consumed"],
                "shadow_mode": row["shadow_mode"],
                "disputed": row["disputed"],
                "created_at": row["created_at"],
                "resolved_at": row["resolved_at"],
                "consumed_at_turn": row.get("consumed_at_turn"),
                "consumed_at": row.get("consumed_at"),
                "interviewer_turn_id": row.get("interviewer_turn_id"),
            }
        )

    async def _get(self, resource: str, params: dict[str, str]) -> list[dict[str, Any]]:
        return await self._request("GET", resource, params=params)

    async def _post(
        self,
        resource: str,
        payload: dict[str, Any],
        *,
        prefer: str | None = None,
        ignore_conflict: bool = False,
    ) -> list[dict[str, Any]]:
        return await self._request(
            "POST",
            resource,
            payload=payload,
            prefer=prefer,
            ignore_conflict=ignore_conflict,
        )

    async def _patch(
        self, resource: str, params: dict[str, str], payload: dict[str, Any]
    ) -> None:
        await self._request(
            "PATCH", resource, params=params, payload=payload, prefer="return=minimal"
        )

    async def _request(
        self,
        method: str,
        resource: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        prefer: str | None = None,
        ignore_conflict: bool = False,
    ) -> list[dict[str, Any]]:
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.request(
                    method,
                    f"{self._url}/rest/v1/{resource}",
                    headers=headers,
                    params=params,
                    json=payload,
                )
                if ignore_conflict and response.status_code == 409:
                    return []
                response.raise_for_status()
                if response.status_code == 204 or not response.content:
                    return []
                body = response.json()
                return body if isinstance(body, list) else [body]
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise SkepticPersistenceUnavailable from exc

