"""Career Evidence: the experience a person has reviewed and approved.

The one source of truth for what someone has done. Pending items are created from the
newest resume reading on first read (idempotent per ``source_key``), then the person
approves, edits, removes or merges them. Only APPROVED items feed other features, through
``approved_items``. Every read and write is owner-scoped by the authenticated user id.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import Settings
from .document_repository import DocumentRepository
from .evidence_quality import EvidenceDraft, evidence_drafts, rank_key
from .http_pool import pooled
from .readiness_service import newest_resume
from .resume_models import ResumeAnalysisResponse, ResumeAnalysisStatus
from .resume_service import ResumeAnalysisService, ResumeNotFound

COLUMNS = "id,user_id,source_document_id,source_key,kind,title,detail,outcome,metric,tools,source_label,status,merged_into,edited,updated_at"
TEXT_FIELDS = ("title", "detail", "outcome", "metric")


class EvidenceUnavailable(Exception):
    """Storage for experience items is not configured or did not answer."""


class EvidenceNotFound(Exception):
    """The item does not exist or belongs to someone else."""


class EvidenceMergeInvalid(Exception):
    pass


class EvidenceKind(StrEnum):
    ACHIEVEMENT = "ACHIEVEMENT"
    PROJECT = "PROJECT"
    RESPONSIBILITY = "RESPONSIBILITY"
    SKILL = "SKILL"


class EvidenceStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REMOVED = "REMOVED"


class EvidenceState(StrEnum):
    NO_RESUME = "NO_RESUME"
    READING = "READING"
    UNREADABLE = "UNREADABLE"
    READY = "READY"


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceItem(EvidenceModel):
    id: UUID
    # Stored, never sent: ownership and provenance stay on the server.
    user_id: UUID = Field(exclude=True)
    source_document_id: UUID | None = Field(default=None, exclude=True)
    source_key: str = Field(exclude=True)
    kind: EvidenceKind
    title: str
    detail: str | None = None
    outcome: str | None = None
    metric: str | None = None
    tools: list[str] = Field(default_factory=list)
    source_label: str | None = None
    status: EvidenceStatus = EvidenceStatus.PENDING
    merged_into: UUID | None = None
    edited: bool = False
    updated_at: datetime


class EvidenceList(EvidenceModel):
    state: EvidenceState
    items: list[EvidenceItem] = Field(default_factory=list)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


class EvidenceUpdate(EvidenceModel):
    status: EvidenceStatus | None = None
    title: str | None = Field(default=None, min_length=3, max_length=500)
    detail: str | None = Field(default=None, max_length=3000)
    outcome: str | None = Field(default=None, max_length=2000)
    metric: str | None = Field(default=None, max_length=200)

    @field_validator("title", "detail", "outcome", "metric", mode="before")
    @classmethod
    def tidy(cls, value: Any) -> Any:
        return _clean(value) if isinstance(value, str) else value

    @field_validator("status", "title")
    @classmethod
    def not_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("cannot be empty")
        return value


class EvidenceApprove(EvidenceModel):
    ids: list[UUID] = Field(min_length=1, max_length=200)


class EvidenceMerge(EvidenceModel):
    into: UUID


def ordered(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Removed last; otherwise quantified outcomes and action statements first (stable)."""
    return sorted(
        items, key=lambda item: (item.status == EvidenceStatus.REMOVED, *rank_key(item.kind, item.title, item.metric))
    )


def _draft_row(user_id: UUID, document_id: UUID | None, draft: EvidenceDraft) -> dict[str, Any]:
    return {
        "user_id": str(user_id),
        "source_document_id": str(document_id) if document_id else None,
        "source_key": draft.source_key,
        "kind": draft.kind,
        "title": draft.title,
        "detail": draft.detail,
        "outcome": draft.outcome,
        "metric": draft.metric,
        "tools": draft.tools,
        "source_label": draft.source_label,
    }


# ------------------------------------------------------------------ storage


class EvidenceRepository(Protocol):
    """Every method is owner-scoped: another person's item reads as not found."""

    async def list_for_user(self, user_id: UUID) -> list[EvidenceItem]: ...
    async def get(self, user_id: UUID, item_id: UUID) -> EvidenceItem | None: ...
    async def create_missing(self, user_id: UUID, document_id: UUID | None, drafts: list[EvidenceDraft]) -> None: ...
    async def update(self, user_id: UUID, item_id: UUID, changes: dict[str, Any]) -> EvidenceItem | None: ...
    async def update_many(self, user_id: UUID, item_ids: list[UUID], changes: dict[str, Any]) -> list[EvidenceItem]: ...


class MemoryEvidenceRepository:
    """In-process items for tests and for running without Supabase."""

    def __init__(self) -> None:
        self.rows: dict[UUID, EvidenceItem] = {}

    async def list_for_user(self, user_id: UUID) -> list[EvidenceItem]:
        return [row for row in self.rows.values() if row.user_id == user_id]

    async def get(self, user_id: UUID, item_id: UUID) -> EvidenceItem | None:
        row = self.rows.get(item_id)
        return row if row and row.user_id == user_id else None

    async def create_missing(self, user_id: UUID, document_id: UUID | None, drafts: list[EvidenceDraft]) -> None:
        keys = {row.source_key for row in self.rows.values() if row.user_id == user_id}
        for draft in drafts:
            if draft.source_key in keys:
                continue  # the unique (user_id, source_key) constraint
            keys.add(draft.source_key)
            row = _draft_row(user_id, document_id, draft)
            item = EvidenceItem(id=uuid4(), updated_at=datetime.now(UTC), **row)
            self.rows[item.id] = item

    async def update(self, user_id: UUID, item_id: UUID, changes: dict[str, Any]) -> EvidenceItem | None:
        current = await self.get(user_id, item_id)
        if current is None:
            return None
        if changes.get("merged_into") is not None and await self.get(user_id, changes["merged_into"]) is None:
            return None  # as the ownership trigger does
        updated = current.model_copy(update={**changes, "updated_at": datetime.now(UTC)})
        self.rows[item_id] = updated
        return updated

    async def update_many(self, user_id: UUID, item_ids: list[UUID], changes: dict[str, Any]) -> list[EvidenceItem]:
        updated = [await self.update(user_id, item_id, changes) for item_id in item_ids]
        return [item for item in updated if item is not None]


class SupabaseEvidenceRepository:
    """Service-role access. Every query also filters by user_id."""

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise EvidenceUnavailable("Supabase storage is not configured")
        self._url = f"{settings.next_public_supabase_url.rstrip('/')}/rest/v1/evidence_items"
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, params: dict[str, str], json: Any = None, prefer: str | None = None) -> list[dict[str, Any]]:
        headers = {**self._headers, **({"Prefer": prefer} if prefer else {})}
        try:
            async with pooled(10) as client:
                response = await client.request(method, self._url, headers=headers, params=params, json=json)
                response.raise_for_status()
                return response.json() if response.content else []
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise EvidenceUnavailable from exc

    async def list_for_user(self, user_id: UUID) -> list[EvidenceItem]:
        rows = await self._request(
            "GET", {"user_id": f"eq.{user_id}", "select": COLUMNS, "order": "created_at.asc,id.asc", "limit": "1000"}
        )
        return [EvidenceItem.model_validate(row) for row in rows]

    async def get(self, user_id: UUID, item_id: UUID) -> EvidenceItem | None:
        rows = await self._request("GET", {"id": f"eq.{item_id}", "user_id": f"eq.{user_id}", "select": COLUMNS})
        return EvidenceItem.model_validate(rows[0]) if rows else None

    async def create_missing(self, user_id: UUID, document_id: UUID | None, drafts: list[EvidenceDraft]) -> None:
        if drafts:
            await self._request(
                "POST",
                {"on_conflict": "user_id,source_key"},
                json=[_draft_row(user_id, document_id, draft) for draft in drafts],
                prefer="resolution=ignore-duplicates,return=minimal",
            )

    async def update(self, user_id: UUID, item_id: UUID, changes: dict[str, Any]) -> EvidenceItem | None:
        updated = await self.update_many(user_id, [item_id], changes)
        return updated[0] if updated else None

    async def update_many(self, user_id: UUID, item_ids: list[UUID], changes: dict[str, Any]) -> list[EvidenceItem]:
        body = {key: str(value) if isinstance(value, UUID) else value for key, value in changes.items()}
        rows = await self._request(
            "PATCH",
            {"id": f"in.({','.join(str(item) for item in item_ids)})", "user_id": f"eq.{user_id}", "select": COLUMNS},
            json=body,
            prefer="return=representation",
        )
        return [EvidenceItem.model_validate(row) for row in rows]


# ------------------------------------------------------------------ service


def _statements(resume: ResumeAnalysisResponse):
    """The person's corrected wording wins over the extracted one."""
    for claim in resume.claims:
        if claim.review_status == "NEEDS_CORRECTION" and claim.corrected_claim_text:
            yield claim.model_copy(update={"claim_text": claim.corrected_claim_text})
        else:
            yield claim


class CareerEvidenceService:
    def __init__(self, items: EvidenceRepository, documents: DocumentRepository, resumes: ResumeAnalysisService) -> None:
        self._items = items
        self._documents = documents
        self._resumes = resumes

    async def _reading(self, user_id: UUID) -> tuple[EvidenceState, UUID | None, ResumeAnalysisResponse | None]:
        document = newest_resume(await self._documents.list_for_user(user_id))
        if document is None:
            return EvidenceState.NO_RESUME, None, None
        try:
            resume = await self._resumes.get(document.id, user_id)
        except ResumeNotFound:
            return EvidenceState.READING, document.id, None  # uploaded, not read yet
        if resume.status == ResumeAnalysisStatus.PROCESSING:
            return EvidenceState.READING, document.id, None
        if resume.status == ResumeAnalysisStatus.FAILED or resume.output is None:
            return EvidenceState.UNREADABLE, document.id, None
        return EvidenceState.READY, document.id, resume

    async def list(self, user_id: UUID) -> EvidenceList:
        state, document_id, resume = await self._reading(user_id)
        items = await self._items.list_for_user(user_id)
        if resume is not None and resume.output is not None:
            known = {item.source_key for item in items}
            missing = [draft for draft in evidence_drafts(resume.output, _statements(resume)) if draft.source_key not in known]
            if missing:
                await self._items.create_missing(user_id, document_id, missing)
                items = await self._items.list_for_user(user_id)
        return EvidenceList(state=state, items=ordered(items))

    async def update(self, user_id: UUID, item_id: UUID, values: EvidenceUpdate) -> EvidenceItem:
        current = await self._items.get(user_id, item_id)
        if current is None:
            raise EvidenceNotFound
        changes = {key: value for key, value in values.model_dump(exclude_unset=True).items() if getattr(current, key) != value}
        if not changes:
            return current
        if any(key in TEXT_FIELDS for key in changes):
            changes["edited"] = True
        if "status" in changes and changes["status"] != EvidenceStatus.REMOVED:
            changes["merged_into"] = None  # restoring a merged item un-merges it
        updated = await self._items.update(user_id, item_id, changes)
        if updated is None:
            raise EvidenceNotFound
        return updated

    async def approve(self, user_id: UUID, item_ids: list[UUID]) -> list[EvidenceItem]:
        """All or nothing: one id that is not the person's means nothing changes."""
        wanted = list(dict.fromkeys(item_ids))
        owned = {item.id for item in await self._items.list_for_user(user_id)}
        if any(item_id not in owned for item_id in wanted):
            raise EvidenceNotFound
        approved = await self._items.update_many(
            user_id, wanted, {"status": EvidenceStatus.APPROVED, "merged_into": None}
        )
        return ordered(approved)

    async def merge(self, user_id: UUID, item_id: UUID, into: UUID) -> EvidenceItem:
        """The item is removed and points at the one it was combined into."""
        if item_id == into:
            raise EvidenceMergeInvalid("An item can't be combined with itself.")
        source, target = await self._items.get(user_id, item_id), await self._items.get(user_id, into)
        if source is None or target is None:
            raise EvidenceNotFound
        if target.status == EvidenceStatus.REMOVED:
            raise EvidenceMergeInvalid("That item was removed, so nothing can be combined into it.")
        merged = await self._items.update(
            user_id, item_id, {"status": EvidenceStatus.REMOVED, "merged_into": into}
        )
        if merged is None:
            raise EvidenceNotFound
        return merged

    async def approved_items(self, user_id: UUID) -> list[EvidenceItem]:
        """What other features may use: only what the person approved, best first."""
        return ordered([item for item in await self._items.list_for_user(user_id) if item.status == EvidenceStatus.APPROVED])
