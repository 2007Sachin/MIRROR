"""Storage for Loop 2 interview targets (migration 20261004200000_loop2_candidate_targets.sql).

Four owner-scoped tables: ``candidate_targets`` (scope immutable; archive + recreate),
``interview_blueprints`` (catalog pin; refresh = new version row), ``generated_questions``
(Mirror-written prompts exactly as served) and ``target_session_links`` (write-once). The
backend writes with the service role and filters every query by ``user_id``; the database
triggers re-check ownership and immutability. ``MemoryTargetRepository`` applies the same
rules in-process for tests and for running without Supabase.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .http_pool import pooled

TargetStatus = Literal["ACTIVE", "ARCHIVED"]
MatchState = Literal["RESEARCHED", "GENERAL_ONLY", "NOT_RESEARCHED"]
TABLES = ("candidate_targets", "interview_blueprints", "generated_questions", "target_session_links")
_MISSING_RELATION_CODES = {"PGRST205", "42P01", "PGRST106"}


class TargetsUnavailable(Exception):
    """Target storage could not be reached just now (transient; never cached)."""


class TargetConflict(Exception):
    def __init__(self, existing_id: UUID | None = None) -> None:
        super().__init__("conflicting row exists")
        self.existing_id = existing_id


class LinkAlreadyExists(Exception):
    """A session already has its (write-once) target link."""

    def __init__(self, link: TargetSessionLink | None) -> None:
        super().__init__("session link is write-once")
        self.link = link


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetValues(_Model):
    role_profile_id: UUID
    company_label: str = Field(min_length=1, max_length=120)
    company_key: str | None = None
    role_family_key: str
    level_key: str | None = None
    level_label: str | None = None
    geography_key: str | None = None
    geography_label: str | None = None
    interview_date: date | None = None


class CandidateTarget(TargetValues):
    id: UUID
    user_id: UUID
    status: TargetStatus
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class BlueprintPin(_Model):
    catalog_version: int = Field(ge=1)
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    match_state: MatchState
    rules_version: str = Field(min_length=1, max_length=40)


class InterviewBlueprint(BlueprintPin):
    id: UUID
    user_id: UUID
    candidate_target_id: UUID
    version: int = Field(ge=1)
    created_at: datetime


class QuestionCreate(_Model):
    candidate_target_id: UUID
    blueprint_id: UUID | None = None
    prompt_set_id: UUID
    position: int = Field(ge=1, le=20)
    round_key: str | None = None
    competency_key: str
    family_key: str
    template_id: str
    generator_version: str
    originality_rules_version: str
    question_text: str = Field(min_length=20, max_length=400)
    rationale_code: str
    derived_from: dict[str, Any] = Field(default_factory=dict)
    novelty_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GeneratedQuestion(QuestionCreate):
    id: UUID
    user_id: UUID
    provenance_class: Literal["MIRROR_GENERATED"] = "MIRROR_GENERATED"
    created_at: datetime


class TargetSessionLinkCreate(_Model):
    session_id: UUID
    candidate_target_id: UUID
    blueprint_id: UUID | None = None
    round_key: str | None = None
    competency_key: str | None = None
    prompt_set_id: UUID | None = None


class TargetSessionLink(TargetSessionLinkCreate):
    user_id: UUID
    created_at: datetime


class TargetRepository(Protocol):
    async def probe(self) -> bool: ...
    async def create_target(self, user_id: UUID, values: TargetValues) -> CandidateTarget: ...
    async def list_targets(self, user_id: UUID) -> list[CandidateTarget]: ...
    async def get_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget | None: ...
    async def archive_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget | None: ...
    async def create_blueprint(self, user_id: UUID, target_id: UUID, pin: BlueprintPin) -> InterviewBlueprint: ...
    async def blueprints(self, target_id: UUID, user_id: UUID) -> list[InterviewBlueprint]: ...
    async def record_questions(self, user_id: UUID, rows: Sequence[QuestionCreate]) -> list[GeneratedQuestion]: ...
    async def questions_for_set(self, prompt_set_id: UUID, user_id: UUID) -> list[GeneratedQuestion]: ...
    async def questions_for_target(self, target_id: UUID, user_id: UUID) -> list[GeneratedQuestion]: ...
    async def create_link(self, user_id: UUID, link: TargetSessionLinkCreate) -> TargetSessionLink: ...
    async def link_for_session(self, session_id: UUID, user_id: UUID) -> TargetSessionLink | None: ...
    async def links_for_target(self, target_id: UUID, user_id: UUID) -> list[TargetSessionLink]: ...


def _scope_key(user_id: UUID, values: TargetValues) -> tuple:
    return (
        user_id, values.role_profile_id, values.company_key or values.company_label.strip().lower(),
        values.role_family_key, values.level_key or "", values.geography_key or "",
    )


# ------------------------------------------------------------------ memory


class MemoryTargetRepository:
    """In-process storage applying the same owner, uniqueness and write-once rules as the database."""

    def __init__(self) -> None:
        self.targets: dict[UUID, CandidateTarget] = {}
        self.blueprint_rows: list[InterviewBlueprint] = []
        self.questions: list[GeneratedQuestion] = []
        self.links: dict[UUID, TargetSessionLink] = {}

    async def probe(self) -> bool:
        return True

    async def create_target(self, user_id: UUID, values: TargetValues) -> CandidateTarget:
        key = _scope_key(user_id, values)
        for row in self.targets.values():
            if row.status == "ACTIVE" and _scope_key(row.user_id, row) == key:
                raise TargetConflict(row.id)
        now = datetime.now(UTC)
        target = CandidateTarget(
            **values.model_dump(), id=uuid4(), user_id=user_id, status="ACTIVE", created_at=now, updated_at=now
        )
        self.targets[target.id] = target
        return target

    async def list_targets(self, user_id: UUID) -> list[CandidateTarget]:
        rows = [row for row in self.targets.values() if row.user_id == user_id]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    async def get_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget | None:
        row = self.targets.get(target_id)
        return row if row is not None and row.user_id == user_id else None

    async def archive_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget | None:
        row = await self.get_target(target_id, user_id)
        if row is None:
            return None
        if row.status == "ARCHIVED":
            return row
        now = datetime.now(UTC)
        archived = row.model_copy(update={"status": "ARCHIVED", "archived_at": now, "updated_at": now})
        self.targets[target_id] = archived
        return archived

    async def _owned_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget:
        row = await self.get_target(target_id, user_id)
        if row is None:
            raise LookupError("target does not belong to this owner")
        return row

    async def create_blueprint(self, user_id: UUID, target_id: UUID, pin: BlueprintPin) -> InterviewBlueprint:
        await self._owned_target(target_id, user_id)
        version = 1 + max((b.version for b in self.blueprint_rows if b.candidate_target_id == target_id), default=0)
        row = InterviewBlueprint(
            **pin.model_dump(), id=uuid4(), user_id=user_id, candidate_target_id=target_id,
            version=version, created_at=datetime.now(UTC),
        )
        self.blueprint_rows.append(row)
        return row

    async def blueprints(self, target_id: UUID, user_id: UUID) -> list[InterviewBlueprint]:
        rows = [b for b in self.blueprint_rows if b.candidate_target_id == target_id and b.user_id == user_id]
        return sorted(rows, key=lambda row: row.version)

    async def record_questions(self, user_id: UUID, rows: Sequence[QuestionCreate]) -> list[GeneratedQuestion]:
        for row in rows:
            await self._owned_target(row.candidate_target_id, user_id)
            if row.blueprint_id is not None and not any(
                b.id == row.blueprint_id and b.user_id == user_id and b.candidate_target_id == row.candidate_target_id
                for b in self.blueprint_rows
            ):
                raise LookupError("blueprint does not belong to the question target")
            for existing in self.questions:
                if existing.user_id == user_id and existing.candidate_target_id == row.candidate_target_id and (
                    existing.novelty_sha256 == row.novelty_sha256
                ):
                    raise TargetConflict(existing.id)
                if existing.prompt_set_id == row.prompt_set_id and existing.position == row.position:
                    raise TargetConflict(existing.id)
        now = datetime.now(UTC)
        stored = [GeneratedQuestion(**row.model_dump(), id=uuid4(), user_id=user_id, created_at=now) for row in rows]
        self.questions.extend(stored)
        return stored

    async def questions_for_set(self, prompt_set_id: UUID, user_id: UUID) -> list[GeneratedQuestion]:
        rows = [q for q in self.questions if q.prompt_set_id == prompt_set_id and q.user_id == user_id]
        return sorted(rows, key=lambda row: row.position)

    async def questions_for_target(self, target_id: UUID, user_id: UUID) -> list[GeneratedQuestion]:
        return [q for q in self.questions if q.candidate_target_id == target_id and q.user_id == user_id]

    async def create_link(self, user_id: UUID, link: TargetSessionLinkCreate) -> TargetSessionLink:
        if link.session_id in self.links:
            existing = self.links[link.session_id]
            raise LinkAlreadyExists(existing if existing.user_id == user_id else None)
        await self._owned_target(link.candidate_target_id, user_id)
        row = TargetSessionLink(**link.model_dump(), user_id=user_id, created_at=datetime.now(UTC))
        self.links[link.session_id] = row
        return row

    async def link_for_session(self, session_id: UUID, user_id: UUID) -> TargetSessionLink | None:
        row = self.links.get(session_id)
        return row if row is not None and row.user_id == user_id else None

    async def links_for_target(self, target_id: UUID, user_id: UUID) -> list[TargetSessionLink]:
        rows = [row for row in self.links.values() if row.candidate_target_id == target_id and row.user_id == user_id]
        return sorted(rows, key=lambda row: row.created_at)


# ------------------------------------------------------------------ Supabase (PostgREST, service role)

ClientFactory = Callable[[], Any]


class SupabaseTargetRepository:
    """Service-role PostgREST access; every read and write carries ``user_id``."""

    def __init__(self, settings: Settings, client_factory: ClientFactory | None = None) -> None:
        if not settings.supabase_enabled:
            raise TargetsUnavailable("Supabase target storage is not configured")
        self._base = f"{settings.next_public_supabase_url.rstrip('/')}/rest/v1"
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }
        self._client_factory = client_factory or (lambda: pooled(10))

    async def _send(self, method: str, table: str, params: dict[str, str], json: Any = None, prefer: str | None = None) -> httpx.Response:
        headers = {**self._headers, **({"Prefer": prefer} if prefer else {})}
        try:
            async with self._client_factory() as client:
                return await client.request(method, f"{self._base}/{table}", headers=headers, params=params, json=json)
        except httpx.HTTPError as exc:
            raise TargetsUnavailable from exc

    async def _rows(self, method: str, table: str, params: dict[str, str], json: Any = None, prefer: str | None = None) -> list[dict[str, Any]]:
        response = await self._send(method, table, params, json, prefer)
        if response.status_code == 409:
            raise TargetConflict()
        if response.status_code >= 400:
            raise TargetsUnavailable(f"{table}: HTTP {response.status_code}")
        try:
            return response.json() if response.content else []
        except ValueError as exc:
            raise TargetsUnavailable from exc

    async def probe(self) -> bool:
        async def one(table: str) -> bool:
            response = await self._send("GET", table, {"select": "user_id", "limit": "0"})
            if response.status_code < 300:
                return True
            try:
                code = (response.json() or {}).get("code")
            except ValueError:
                code = None
            if response.status_code == 404 or code in _MISSING_RELATION_CODES:
                return False
            raise TargetsUnavailable(f"probe {table}: HTTP {response.status_code}")

        return all(await asyncio.gather(*(one(table) for table in TABLES)))

    @staticmethod
    def _dump(model: BaseModel, user_id: UUID) -> dict[str, Any]:
        return {**model.model_dump(mode="json"), "user_id": str(user_id)}

    async def create_target(self, user_id: UUID, values: TargetValues) -> CandidateTarget:
        try:
            rows = await self._rows("POST", "candidate_targets", {"select": "*"}, json=self._dump(values, user_id), prefer="return=representation")
        except TargetConflict:
            for row in await self.list_targets(user_id):
                if row.status == "ACTIVE" and _scope_key(user_id, row) == _scope_key(user_id, values):
                    raise TargetConflict(row.id) from None
            raise
        return CandidateTarget.model_validate(rows[0])

    async def list_targets(self, user_id: UUID) -> list[CandidateTarget]:
        rows = await self._rows("GET", "candidate_targets", {"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.desc"})
        return [CandidateTarget.model_validate(row) for row in rows]

    async def get_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget | None:
        rows = await self._rows("GET", "candidate_targets", {"id": f"eq.{target_id}", "user_id": f"eq.{user_id}", "select": "*"})
        return CandidateTarget.model_validate(rows[0]) if rows else None

    async def archive_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget | None:
        current = await self.get_target(target_id, user_id)
        if current is None or current.status == "ARCHIVED":
            return current
        rows = await self._rows(
            "PATCH", "candidate_targets",
            {"id": f"eq.{target_id}", "user_id": f"eq.{user_id}", "status": "eq.ACTIVE", "select": "*"},
            json={"status": "ARCHIVED", "archived_at": datetime.now(UTC).isoformat()},
            prefer="return=representation",
        )
        return CandidateTarget.model_validate(rows[0]) if rows else await self.get_target(target_id, user_id)

    async def create_blueprint(self, user_id: UUID, target_id: UUID, pin: BlueprintPin) -> InterviewBlueprint:
        if await self.get_target(target_id, user_id) is None:
            raise LookupError("target does not belong to this owner")
        for _ in range(3):  # a concurrent refresh takes the version; try the next one
            version = 1 + max((b.version for b in await self.blueprints(target_id, user_id)), default=0)
            body = {**self._dump(pin, user_id), "candidate_target_id": str(target_id), "version": version}
            try:
                rows = await self._rows("POST", "interview_blueprints", {"select": "*"}, json=body, prefer="return=representation")
            except TargetConflict:
                continue
            return InterviewBlueprint.model_validate(rows[0])
        raise TargetsUnavailable("blueprint version contention")

    async def blueprints(self, target_id: UUID, user_id: UUID) -> list[InterviewBlueprint]:
        rows = await self._rows(
            "GET", "interview_blueprints",
            {"candidate_target_id": f"eq.{target_id}", "user_id": f"eq.{user_id}", "select": "*", "order": "version.asc"},
        )
        return [InterviewBlueprint.model_validate(row) for row in rows]

    async def record_questions(self, user_id: UUID, rows: Sequence[QuestionCreate]) -> list[GeneratedQuestion]:
        if not rows:
            return []
        stored = await self._rows(
            "POST", "generated_questions", {"select": "*"},
            json=[self._dump(row, user_id) for row in rows], prefer="return=representation",
        )
        return [GeneratedQuestion.model_validate(row) for row in stored]

    async def questions_for_set(self, prompt_set_id: UUID, user_id: UUID) -> list[GeneratedQuestion]:
        rows = await self._rows(
            "GET", "generated_questions",
            {"prompt_set_id": f"eq.{prompt_set_id}", "user_id": f"eq.{user_id}", "select": "*", "order": "position.asc"},
        )
        return [GeneratedQuestion.model_validate(row) for row in rows]

    async def questions_for_target(self, target_id: UUID, user_id: UUID) -> list[GeneratedQuestion]:
        rows = await self._rows(
            "GET", "generated_questions",
            {"candidate_target_id": f"eq.{target_id}", "user_id": f"eq.{user_id}", "select": "*", "limit": "1000"},
        )
        return [GeneratedQuestion.model_validate(row) for row in rows]

    async def create_link(self, user_id: UUID, link: TargetSessionLinkCreate) -> TargetSessionLink:
        try:
            rows = await self._rows(
                "POST", "target_session_links", {"select": "*"},
                json=self._dump(link, user_id), prefer="return=representation",
            )
        except TargetConflict:
            raise LinkAlreadyExists(await self.link_for_session(link.session_id, user_id)) from None
        return TargetSessionLink.model_validate(rows[0])

    async def link_for_session(self, session_id: UUID, user_id: UUID) -> TargetSessionLink | None:
        rows = await self._rows("GET", "target_session_links", {"session_id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "*"})
        return TargetSessionLink.model_validate(rows[0]) if rows else None

    async def links_for_target(self, target_id: UUID, user_id: UUID) -> list[TargetSessionLink]:
        rows = await self._rows(
            "GET", "target_session_links",
            {"candidate_target_id": f"eq.{target_id}", "user_id": f"eq.{user_id}", "select": "*", "order": "created_at.asc"},
        )
        return [TargetSessionLink.model_validate(row) for row in rows]
