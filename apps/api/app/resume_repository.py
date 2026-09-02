from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import httpx

from .config import Settings
from .resume_models import (
    ClaimCorrectionCreate,
    ResumeAgentOutput,
    ResumeAnalysisRecord,
    ResumeAnalysisResponse,
    ResumeClaimReview,
)


ANALYSIS_COLUMNS = (
    "id,document_id,user_id,version,status,output,model,prompt_version,"
    "analysis_version,execution_id,error_type,created_at,completed_at"
)
CLAIM_COLUMNS = (
    "id,claim_text,claim_type,source_reference,confidence,verification_priority,"
    "skill,project_name,metric_value,metric_unit,ownership_language,outcome,tool"
)
CORRECTION_COLUMNS = "claim_id,version,review_status,corrected_claim_text"


class ResumeAnalysisUnavailable(Exception):
    pass


class ResumeAnalysisNotFound(Exception):
    pass


class ResumeAnalysisRepository(Protocol):
    async def begin(
        self,
        document_id: UUID,
        user_id: UUID,
        *,
        model: str,
        prompt_version: str,
        analysis_version: str,
    ) -> tuple[ResumeAnalysisRecord, bool]: ...

    async def complete(
        self,
        analysis_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        output: ResumeAgentOutput,
    ) -> ResumeAnalysisResponse: ...

    async def fail(
        self,
        analysis_id: UUID,
        user_id: UUID,
        *,
        execution_id: UUID | None,
        error_type: str,
    ) -> ResumeAnalysisRecord: ...

    async def get_latest(
        self, document_id: UUID, user_id: UUID
    ) -> ResumeAnalysisResponse | None: ...

    async def add_correction(
        self,
        document_id: UUID,
        user_id: UUID,
        claim_id: UUID,
        correction: ClaimCorrectionCreate,
    ) -> ResumeAnalysisResponse: ...


class SupabaseResumeAnalysisRepository:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise ResumeAnalysisUnavailable(
                "Supabase resume analysis storage is not configured"
            )
        self._url = settings.next_public_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def begin(
        self,
        document_id: UUID,
        user_id: UUID,
        *,
        model: str,
        prompt_version: str,
        analysis_version: str,
    ) -> tuple[ResumeAnalysisRecord, bool]:
        processing = await self._get_processing(document_id, user_id)
        if processing is not None:
            return processing, False
        latest = await self._get_analysis_row(document_id, user_id)
        version = (latest.version if latest else 0) + 1
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/resume_analyses",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={"select": ANALYSIS_COLUMNS},
                    json={
                        "document_id": str(document_id),
                        "user_id": str(user_id),
                        "version": version,
                        "status": "PROCESSING",
                        "model": model,
                        "prompt_version": prompt_version,
                        "analysis_version": analysis_version,
                    },
                )
                if response.status_code == 409:
                    concurrent = await self._get_processing(document_id, user_id)
                    if concurrent is not None:
                        return concurrent, False
                response.raise_for_status()
                return ResumeAnalysisRecord.model_validate(response.json()[0]), True
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise ResumeAnalysisUnavailable from exc

    async def complete(
        self,
        analysis_id: UUID,
        user_id: UUID,
        execution_id: UUID,
        output: ResumeAgentOutput,
    ) -> ResumeAnalysisResponse:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/rpc/complete_resume_analysis",
                    headers=self._headers,
                    json={
                        "p_analysis_id": str(analysis_id),
                        "p_user_id": str(user_id),
                        "p_execution_id": str(execution_id),
                        "p_output": output.model_dump(mode="json"),
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ResumeAnalysisUnavailable from exc
        completed = await self._get_by_id(analysis_id, user_id)
        if completed is None:
            raise ResumeAnalysisUnavailable("completed analysis could not be read")
        return await self._hydrate(completed)

    async def fail(
        self,
        analysis_id: UUID,
        user_id: UUID,
        *,
        execution_id: UUID | None,
        error_type: str,
    ) -> ResumeAnalysisRecord:
        values = {
            "status": "FAILED",
            "error_type": error_type,
            "execution_id": str(execution_id) if execution_id else None,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.patch(
                    f"{self._url}/rest/v1/resume_analyses",
                    headers={**self._headers, "Prefer": "return=representation"},
                    params={
                        "id": f"eq.{analysis_id}",
                        "user_id": f"eq.{user_id}",
                        "status": "eq.PROCESSING",
                        "select": ANALYSIS_COLUMNS,
                    },
                    json=values,
                )
                response.raise_for_status()
                return ResumeAnalysisRecord.model_validate(response.json()[0])
        except (httpx.HTTPError, IndexError, TypeError, ValueError) as exc:
            raise ResumeAnalysisUnavailable from exc

    async def get_latest(
        self, document_id: UUID, user_id: UUID
    ) -> ResumeAnalysisResponse | None:
        row = await self._get_analysis_row(document_id, user_id)
        return await self._hydrate(row) if row else None

    async def add_correction(
        self,
        document_id: UUID,
        user_id: UUID,
        claim_id: UUID,
        correction: ClaimCorrectionCreate,
    ) -> ResumeAnalysisResponse:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self._url}/rest/v1/rpc/create_resume_claim_correction",
                    headers=self._headers,
                    json={
                        "p_document_id": str(document_id),
                        "p_user_id": str(user_id),
                        "p_claim_id": str(claim_id),
                        "p_review_status": correction.review_status.value,
                        "p_corrected_claim_text": correction.corrected_claim_text,
                    },
                )
                if response.status_code in (400, 404):
                    raise ResumeAnalysisNotFound
                response.raise_for_status()
        except ResumeAnalysisNotFound:
            raise
        except httpx.HTTPError as exc:
            raise ResumeAnalysisUnavailable from exc
        latest = await self.get_latest(document_id, user_id)
        if latest is None:
            raise ResumeAnalysisNotFound
        return latest

    async def _get_processing(
        self, document_id: UUID, user_id: UUID
    ) -> ResumeAnalysisRecord | None:
        return await self._get_analysis_row(document_id, user_id, status="PROCESSING")

    async def _get_by_id(
        self, analysis_id: UUID, user_id: UUID
    ) -> ResumeAnalysisRecord | None:
        return await self._query_one(
            {"id": f"eq.{analysis_id}", "user_id": f"eq.{user_id}"}
        )

    async def _get_analysis_row(
        self, document_id: UUID, user_id: UUID, *, status: str | None = None
    ) -> ResumeAnalysisRecord | None:
        params = {
            "document_id": f"eq.{document_id}",
            "user_id": f"eq.{user_id}",
            "order": "version.desc",
            "limit": "1",
        }
        if status:
            params["status"] = f"eq.{status}"
        return await self._query_one(params)

    async def _query_one(self, params: dict[str, str]) -> ResumeAnalysisRecord | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self._url}/rest/v1/resume_analyses",
                    headers=self._headers,
                    params={**params, "select": ANALYSIS_COLUMNS},
                )
                response.raise_for_status()
                rows = response.json()
                return ResumeAnalysisRecord.model_validate(rows[0]) if rows else None
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise ResumeAnalysisUnavailable from exc

    async def _hydrate(self, analysis: ResumeAnalysisRecord) -> ResumeAnalysisResponse:
        if analysis.status != "COMPLETED":
            return ResumeAnalysisResponse(**analysis.model_dump(), claims=[])
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                claims_response = await client.get(
                    f"{self._url}/rest/v1/claims",
                    headers=self._headers,
                    params={
                        "resume_analysis_id": f"eq.{analysis.id}",
                        "select": CLAIM_COLUMNS,
                        "order": "created_at.asc",
                    },
                )
                claims_response.raise_for_status()
                corrections_response = await client.get(
                    f"{self._url}/rest/v1/resume_claim_corrections",
                    headers=self._headers,
                    params={
                        "resume_analysis_id": f"eq.{analysis.id}",
                        "select": CORRECTION_COLUMNS,
                        "order": "version.desc",
                    },
                )
                corrections_response.raise_for_status()
                corrections = {}
                for row in corrections_response.json():
                    corrections.setdefault(row["claim_id"], row)
                claims = []
                for row in claims_response.json():
                    correction = corrections.get(row["id"], {})
                    claims.append(
                        ResumeClaimReview.model_validate(
                            {
                                **row,
                                "claim_type": row["claim_type"].upper(),
                                "source": "RESUME",
                                "review_status": correction.get("review_status"),
                                "corrected_claim_text": correction.get(
                                    "corrected_claim_text"
                                ),
                                "correction_version": correction.get("version"),
                            }
                        )
                    )
                return ResumeAnalysisResponse(**analysis.model_dump(), claims=claims)
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise ResumeAnalysisUnavailable from exc

