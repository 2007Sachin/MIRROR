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
import threading
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
    prompt_set_state: Literal["NOT_APPLICABLE", "PENDING", "COMPLETE"] = "NOT_APPLICABLE"
    expected_prompt_count: int | None = None
    # UUIDv5 prompt_set_id binds owner/target/round/idempotency. This private first-writer snapshot freezes
    # blueprint/research, generation versions, exact text, and used candidate context; retries never regenerate it.
    prompt_manifest: tuple[QuestionCreate, ...] | None = None


class TargetSessionLink(TargetSessionLinkCreate):
    user_id: UUID
    created_at: datetime


def _validate_link_prompt_state(link: TargetSessionLinkCreate) -> None:
    manifest = link.prompt_manifest
    if link.prompt_set_id is None:
        if link.prompt_set_state != "NOT_APPLICABLE" or link.expected_prompt_count is not None or manifest is not None:
            raise TargetConflict()
        return
    if (link.prompt_set_state != "PENDING" or link.expected_prompt_count not in (3, 4)
        or manifest is None or len(manifest) != link.expected_prompt_count):
        raise TargetConflict()
    for position, row in enumerate(manifest, start=1):
        if (row.position != position or row.prompt_set_id != link.prompt_set_id
            or row.candidate_target_id != link.candidate_target_id
            or row.blueprint_id != link.blueprint_id or row.round_key != link.round_key):
            raise TargetConflict()


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
    async def questions_for_target(self, target_id: UUID, user_id: UUID, since: datetime | None = None) -> list[GeneratedQuestion]: ...
    async def create_link(self, user_id: UUID, link: TargetSessionLinkCreate) -> TargetSessionLink: ...
    async def complete_prompt_link(self, session_id: UUID, user_id: UUID) -> TargetSessionLink: ...
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
        # Check-and-write is one step, as in a database transaction with unique constraints:
        # a racing writer validates only after the winner's rows exist.
        self._write_lock = threading.Lock()

    async def probe(self) -> bool:
        return True

    async def create_target(self, user_id: UUID, values: TargetValues) -> CandidateTarget:
        # Construct before entering the critical section; uniqueness check + insert are atomic.
        now = datetime.now(UTC)
        target = CandidateTarget(
            **values.model_dump(), id=uuid4(), user_id=user_id, status="ACTIVE", created_at=now, updated_at=now
        )
        key = _scope_key(user_id, values)
        with self._write_lock:
            for row in self.targets.values():
                if row.status == "ACTIVE" and _scope_key(row.user_id, row) == key:
                    raise TargetConflict(row.id)
            self.targets[target.id] = target
        return target

    async def list_targets(self, user_id: UUID) -> list[CandidateTarget]:
        rows = [row for row in self.targets.values() if row.user_id == user_id]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    async def get_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget | None:
        row = self.targets.get(target_id)
        return row if row is not None and row.user_id == user_id else None

    async def archive_target(self, target_id: UUID, user_id: UUID) -> CandidateTarget | None:
        with self._write_lock:
            row = self.targets.get(target_id)
            if row is None or row.user_id != user_id:
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
        with self._write_lock:
            target = self.targets.get(target_id)
            if target is None or target.user_id != user_id:
                raise LookupError("target does not belong to this owner")
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
        with self._write_lock:  # no await inside: one atomic batch, like one INSERT statement
            return self._record_questions_locked(user_id, rows)

    def _record_questions_locked(self, user_id: UUID, rows: Sequence[QuestionCreate]) -> list[GeneratedQuestion]:
        for row in rows:
            link = next((item for item in self.links.values() if item.prompt_set_id == row.prompt_set_id), None)
            if link is None or link.user_id != user_id or link.candidate_target_id != row.candidate_target_id:
                raise LookupError("prompt set does not have a matching target-session link")
            if (link.prompt_set_state != "PENDING" or link.expected_prompt_count is None
                or row.position > link.expected_prompt_count or link.prompt_manifest is None):
                raise TargetConflict()
            if row.model_dump() != link.prompt_manifest[row.position - 1].model_dump():
                raise TargetConflict()
            if row.blueprint_id is not None and not any(
                b.id == row.blueprint_id and b.user_id == user_id and b.candidate_target_id == row.candidate_target_id
                for b in self.blueprint_rows
            ):
                raise LookupError("blueprint does not belong to the question target")
            for existing in self.questions:
                # Same rule as the database: no repeat inside one practice set; reuse across
                # sessions is limited by the originality guard's 30-day window, not here.
                if existing.user_id == user_id and existing.prompt_set_id == row.prompt_set_id and (
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

    async def questions_for_target(self, target_id: UUID, user_id: UUID, since: datetime | None = None) -> list[GeneratedQuestion]:
        linked_sets = set()
        for link in self.links.values():
            if link.candidate_target_id != target_id or link.user_id != user_id or link.prompt_set_id is None:
                continue
            rows = await self.questions_for_set(link.prompt_set_id, user_id)
            if (link.prompt_set_state == "COMPLETE" and link.expected_prompt_count is not None
                and all(q.candidate_target_id == link.candidate_target_id for q in rows)
                and [q.position for q in rows] == list(range(1, link.expected_prompt_count + 1))):
                linked_sets.add(link.prompt_set_id)
        return [
            q for q in self.questions
            if q.candidate_target_id == target_id and q.user_id == user_id
            and q.prompt_set_id in linked_sets
            and (since is None or q.created_at >= since)
        ]

    async def create_link(self, user_id: UUID, link: TargetSessionLinkCreate) -> TargetSessionLink:
        self._raise_if_session_linked(link.session_id, user_id)
        await self._owned_target(link.candidate_target_id, user_id)
        _validate_link_prompt_state(link)
        with self._write_lock:  # re-check after the await, then write, as one step
            self._raise_if_session_linked(link.session_id, user_id)
            if link.prompt_set_id is not None and any(existing.prompt_set_id == link.prompt_set_id for existing in self.links.values()):
                raise TargetConflict()
            stored = TargetSessionLink(**link.model_dump(), user_id=user_id, created_at=datetime.now(UTC))
            self.links[stored.session_id] = stored
            return stored

    def _raise_if_session_linked(self, session_id: UUID, user_id: UUID) -> None:
        if session_id in self.links:
            existing = self.links[session_id]
            raise LinkAlreadyExists(existing if existing.user_id == user_id else None)

    async def complete_prompt_link(self, session_id: UUID, user_id: UUID) -> TargetSessionLink:
        with self._write_lock:
            link = self.links.get(session_id)
            if link is None or link.user_id != user_id or link.prompt_set_id is None:
                raise TargetConflict()
            rows = sorted((q for q in self.questions if q.prompt_set_id == link.prompt_set_id and q.user_id == user_id),
                          key=lambda row: row.position)
            expected = link.expected_prompt_count
            if (expected is None or link.prompt_manifest is None
                or any(q.candidate_target_id != link.candidate_target_id for q in rows)
                or [q.position for q in rows] != list(range(1, expected + 1))
                or any(q.model_dump(exclude={"id", "user_id", "created_at", "provenance_class"})
                       != link.prompt_manifest[q.position - 1].model_dump() for q in rows)):
                raise TargetConflict()
            if link.prompt_set_state == "COMPLETE":
                return link
            if link.prompt_set_state != "PENDING":
                raise TargetConflict()
            completed = link.model_copy(update={"prompt_set_state": "COMPLETE"})
            self.links[session_id] = completed
            return completed

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

    async def questions_for_target(self, target_id: UUID, user_id: UUID, since: datetime | None = None) -> list[GeneratedQuestion]:
        links = await self._rows(
            "GET", "target_session_links",
            {"candidate_target_id": f"eq.{target_id}", "user_id": f"eq.{user_id}", "prompt_set_state": "eq.COMPLETE", "select": "prompt_set_id,expected_prompt_count"},
        )
        set_ids = sorted({str(row["prompt_set_id"]) for row in links if row.get("prompt_set_id")})
        if not set_ids:
            return []
        params = {
            "candidate_target_id": f"eq.{target_id}", "user_id": f"eq.{user_id}",
            "prompt_set_id": f"in.({','.join(set_ids)})", "select": "*", "order": "created_at.desc",
        }
        if since is not None:
            params["created_at"] = f"gte.{since.isoformat()}"
        rows = await self._rows("GET", "generated_questions", params)
        expected = {str(row["prompt_set_id"]): row.get("expected_prompt_count") for row in links if row.get("prompt_set_id")}
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row["prompt_set_id"]), []).append(row)
        valid = {key for key, group in grouped.items() if expected.get(key) is not None and sorted(int(r["position"]) for r in group) == list(range(1, int(expected[key]) + 1))}
        return [GeneratedQuestion.model_validate(row) for row in rows if str(row["prompt_set_id"]) in valid]

    async def create_link(self, user_id: UUID, link: TargetSessionLinkCreate) -> TargetSessionLink:
        _validate_link_prompt_state(link)
        try:
            rows = await self._rows(
                "POST", "target_session_links", {"select": "*"},
                json=self._dump(link, user_id), prefer="return=representation",
            )
        except TargetConflict:
            raise LinkAlreadyExists(await self.link_for_session(link.session_id, user_id)) from None
        return TargetSessionLink.model_validate(rows[0])

    async def complete_prompt_link(self, session_id: UUID, user_id: UUID) -> TargetSessionLink:
        current = await self.link_for_session(session_id, user_id)
        if current is None or current.prompt_set_id is None or current.expected_prompt_count is None:
            raise TargetConflict()
        questions = await self.questions_for_set(current.prompt_set_id, user_id)
        expected = current.expected_prompt_count
        if (any(q.candidate_target_id != current.candidate_target_id for q in questions)
            or [q.position for q in questions] != list(range(1, expected + 1))):
            raise TargetConflict()
        if current.prompt_set_state == "COMPLETE":
            return current
        if current.prompt_set_state != "PENDING":
            raise TargetConflict()
        rows = await self._rows("PATCH", "target_session_links", {"session_id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "prompt_set_state": "eq.PENDING", "select": "*"}, json={"prompt_set_state": "COMPLETE"}, prefer="return=representation")
        if rows:
            return TargetSessionLink.model_validate(rows[0])
        winner = await self.link_for_session(session_id, user_id)
        if winner and winner.prompt_set_state == "COMPLETE" and winner.expected_prompt_count == expected:
            return winner
        raise TargetConflict()

    async def link_for_session(self, session_id: UUID, user_id: UUID) -> TargetSessionLink | None:
        rows = await self._rows("GET", "target_session_links", {"session_id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "*"})
        return TargetSessionLink.model_validate(rows[0]) if rows else None

    async def links_for_target(self, target_id: UUID, user_id: UUID) -> list[TargetSessionLink]:
        rows = await self._rows(
            "GET", "target_session_links",
            {"candidate_target_id": f"eq.{target_id}", "user_id": f"eq.{user_id}", "select": "*", "order": "created_at.asc"},
        )
        return [TargetSessionLink.model_validate(row) for row in rows]
