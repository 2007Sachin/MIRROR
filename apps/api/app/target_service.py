"""Loop 2 target orchestration: the one place that composes catalog, storage and existing services.

Rules kept here (each has a route test):
- scope is immutable: a target is created once and can only be archived;
- the level is the person's explicit choice, ``not_sure`` by default; it is never mapped to the
  role's seniority and never read from the job description;
- geography is exact (owner rule): research scoped elsewhere, including ``global``, is never
  shown for a target; with no claims for exactly this target the state is NOT_RESEARCHED;
- a blueprint pins (catalog version, content hash); refresh appends a new pin and every
  earlier pin is still served from its own catalog version; a hash mismatch serves nothing;
- practice prompts are Mirror-written, guarded and stored before the session exists, and a
  session's target link is written once.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .practice_modes import MODE_SHAPE, PracticeFocus, PracticeMode
from .prompt_originality import ORIGINALITY_RULES_VERSION, GuardContext, RecentPrompt, excerpts_from_catalog
from .research_catalog import (
    KEY_PATTERN,
    Claim,
    RepoResearchCatalog,
    ScopeMatch,
    TargetScope,
    load_catalog,
    match_scope,
)
from .schemas import SessionCreate, SessionRead
from .target_capability import TargetAvailability, TargetCapability
from .target_priority import PRIORITY_RULES_VERSION, CompetencyInProcess, PracticeFact, prioritise
from .target_repository import (
    BlueprintPin,
    CandidateTarget,
    GeneratedQuestion,
    InterviewBlueprint,
    LinkAlreadyExists,
    QuestionCreate,
    TargetRepository,
    TargetSessionLink,
    TargetSessionLinkCreate,
    TargetValues,
)
from .target_rounds import (
    PACK_MIN,
    ROUND_PACK_VERSION,
    ROUNDS,
    CandidateMaterial,
    PracticeRound,
    RoundPack,
    build_round_pack,
    get_round,
)

logger = logging.getLogger("mirror.targets")

BLUEPRINT_RULES_VERSION = "blueprint-1"
ContentState = Literal["SERVED", "PIN_MISMATCH", "CATALOG_UNAVAILABLE"]
LevelKey = Literal["sde_i", "sde_ii", "sde_iii", "university", "not_sure"]
COMPANY_KEYS = {"amazon": "amazon"}  # exact, case-insensitive alias -> catalog company key
MAX_PRIORITIES = 3
MAX_STORY_TITLES = 4


# ------------------------------------------------------------------ errors


class TargetNotFound(Exception):
    pass


class TargetArchived(Exception):
    pass


class RoundNotFound(Exception):
    pass


class BlueprintNotFound(Exception):
    pass


class ShortPack(Exception):
    def __init__(self, available: int) -> None:
        super().__init__("not enough original prompts")
        self.available = available


class LinkConflict(Exception):
    pass


class CatalogUnavailable(Exception):
    pass


# ------------------------------------------------------------------ catalog access


class CatalogProvider(Protocol):
    def latest(self) -> RepoResearchCatalog: ...
    def at(self, version: int) -> RepoResearchCatalog | None: ...


class StaticCatalogProvider:
    def __init__(self, catalogs: Mapping[int, RepoResearchCatalog]) -> None:
        self._catalogs = dict(catalogs)

    def latest(self) -> RepoResearchCatalog:
        return self._catalogs[max(self._catalogs)]

    def at(self, version: int) -> RepoResearchCatalog | None:
        return self._catalogs.get(version)


class RepoCatalogProvider:
    """The locked repo catalog; every version is loaded through the same lock + policy check."""

    def latest(self) -> RepoResearchCatalog:
        return _load(None)

    def at(self, version: int) -> RepoResearchCatalog | None:
        try:
            return _load(version)
        except Exception:  # noqa: BLE001 - an unlocked version is simply not available
            return None


@lru_cache(maxsize=8)
def _load(version: int | None) -> RepoResearchCatalog:
    return load_catalog(version=version)


# ------------------------------------------------------------------ API models


class _Api(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TargetCreate(_Api):
    role_profile_id: UUID
    company: str = Field(min_length=1, max_length=120)
    role_family: str = Field(default="software_development_engineering", pattern=KEY_PATTERN)
    level: LevelKey = "not_sure"
    geography: str | None = Field(default=None, pattern=KEY_PATTERN)
    geography_label: str | None = Field(default=None, min_length=1, max_length=120)
    interview_date: date | None = None

    @field_validator("geography")
    @classmethod
    def _real_place(cls, value: str | None) -> str | None:
        if value == "global":
            raise ValueError("a target is a real place; 'global' is not one")
        return value

    @field_validator("company")
    @classmethod
    def _trimmed(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("company is required")
        return value.strip()


class TargetView(_Api):
    id: UUID
    role_profile_id: UUID
    company_label: str
    company_key: str | None
    role_family_key: str
    level_key: str | None
    geography_key: str | None
    geography_label: str | None
    interview_date: date | None
    status: str
    archived_at: datetime | None
    created_at: datetime


class BlueprintRef(_Api):
    version: int
    catalog_version: int
    catalog_sha256: str
    match_state: str
    rules_version: str
    created_at: datetime
    latest_version: int
    refresh_available: bool


class SourceRef(_Api):
    publisher: str
    url: str
    retrieved_at: date
    published_at: date | None


class ClaimView(_Api):
    key: str
    statement: str
    provenance_class: str
    class_label_key: str
    scope: dict[str, str]
    scope_label_key: str
    confidence_band: str
    dating: str
    retrieved_at: date
    published_at: date | None
    limits: list[str]
    sources: list[SourceRef]
    conflict_set: str | None


class ConflictView(_Api):
    key: str
    note: str
    claims: list[ClaimView]  # side by side; never merged or averaged


class UnknownView(_Api):
    key: str
    reason: str
    note: str


class RoundSummary(_Api):
    key: str
    ordinal: int
    label_key: str
    basis: Literal["PUBLISHED_GUIDANCE", "MIRROR_SUGGESTED"]
    competency_keys: list[str]


class BlueprintView(_Api):
    availability: TargetAvailability
    target: TargetView | None = None
    blueprint: BlueprintRef | None = None
    content_state: ContentState | None = None
    match_state: str | None = None
    research_label_key: str | None = None
    claims: list[ClaimView] = Field(default_factory=list)
    conflicts: list[ConflictView] = Field(default_factory=list)
    unknowns: list[UnknownView] = Field(default_factory=list)
    rounds: list[RoundSummary] = Field(default_factory=list)


class PriorityView(_Api):
    rank: int
    competency_key: str
    reason_codes: list[str]
    suggested_mode: str


class PromptView(_Api):
    position: int
    text: str
    competency_key: str
    rationale_code: str
    provenance_class: str


class PackView(_Api):
    state: str
    minimum: int
    label_key: str = "prompts.written_by_mirror"
    prompts: list[PromptView]


class PracticeHistoryItem(_Api):
    session_id: UUID
    created_at: datetime


class PracticeHistory(_Api):
    count: int
    sessions: list[PracticeHistoryItem]


class RoundDetail(_Api):
    availability: TargetAvailability
    target: TargetView | None = None
    round: RoundSummary | None = None
    match_state: str | None = None
    research_label_key: str | None = None
    content_state: str | None = None
    claims: list[ClaimView] = Field(default_factory=list)
    conflicts: list[ConflictView] = Field(default_factory=list)
    unknowns: list[UnknownView] = Field(default_factory=list)
    priorities: list[PriorityView] = Field(default_factory=list)
    priority_rules_version: str = PRIORITY_RULES_VERSION
    pack: PackView | None = None
    practice: PracticeHistory | None = None


class LinkView(_Api):
    session_id: UUID
    candidate_target_id: UUID
    blueprint_id: UUID | None
    round_key: str | None
    competency_key: str | None
    prompt_set_id: UUID | None
    created_at: datetime


class PracticeStart(_Api):
    mode: Literal["QUICK_DRILL", "FOCUSED_PRACTICE"] = "FOCUSED_PRACTICE"
    idempotency_key: UUID


class PracticePromptRef(_Api):
    position: int
    rationale_code: str


class PracticeStarted(_Api):
    session: SessionRead
    link: LinkView
    prompts: list[PracticePromptRef]  # prompt text is not shown before the interview


# ------------------------------------------------------------------ pure helpers

_RESEARCH_LABEL = {
    "RESEARCHED": "research.researched",
    "GENERAL_ONLY": "research.general_only",
    "NOT_RESEARCHED": "research.not_yet_researched",
}


def target_view(target: CandidateTarget) -> TargetView:
    return TargetView(**target.model_dump(include=set(TargetView.model_fields)))


def target_scope(target: CandidateTarget) -> TargetScope | None:
    """Catalog scope for a target, or None when it cannot match any research (unknown company)."""
    if target.company_key is None:
        return None
    level = None if target.level_key in (None, "not_sure") else target.level_key
    return TargetScope(
        company=target.company_key, role_family=target.role_family_key, level=level, geography=target.geography_key
    )


def scope_match(target: CandidateTarget, catalog: RepoResearchCatalog) -> ScopeMatch:
    scope = target_scope(target)
    if scope is None:
        return ScopeMatch(
            state="NOT_RESEARCHED", catalog_version=catalog.version, content_sha256=catalog.content_sha256,
            claims=(), conflict_sets=(), unknowns=(),
        )
    return match_scope(catalog, scope)


def _claim_view(claim: Claim, catalog: RepoResearchCatalog) -> ClaimView:
    sources = {source.id: source for source in catalog.document.sources}
    refs = [
        SourceRef(publisher=s.publisher, url=s.url, retrieved_at=s.retrieved_at, published_at=s.published_at)
        for s in (sources.get(item.source_id) for item in claim.evidence if item.stance == "SUPPORTS")
        if s is not None
    ]
    return ClaimView(
        key=claim.id,
        statement=claim.statement,
        provenance_class=claim.provenance_class,
        class_label_key=f"class.{claim.provenance_class.lower()}",
        scope=claim.scope.model_dump(),
        scope_label_key="scope.all_levels_here" if claim.scope.level == "all" else "scope.this_level_here",
        confidence_band=claim.confidence_band,
        dating=claim.dating,
        retrieved_at=claim.retrieved_at,
        published_at=claim.published_at,
        limits=list(claim.limits),
        sources=refs,
        conflict_set=claim.conflict_set,
    )


def _content(match: ScopeMatch, catalog: RepoResearchCatalog, subjects: frozenset[str] | None = None):
    """(flat claims, conflicts side by side, unknowns) of a match, optionally limited to subjects."""
    chosen = [c for c in match.claims if subjects is None or c.subject in subjects]
    flat = [_claim_view(c, catalog) for c in chosen if c.conflict_set is None]
    conflicts = []
    for conflict in match.conflict_sets:
        members = [c for c in chosen if c.conflict_set == conflict.key]
        if members:
            conflicts.append(ConflictView(key=conflict.key, note=conflict.note, claims=[_claim_view(c, catalog) for c in members]))
    unknowns = [UnknownView(key=u.key, reason=u.reason, note=u.note) for u in match.unknowns]
    return flat, conflicts, unknowns


def _round_claims(match: ScopeMatch, round_: PracticeRound) -> list[Claim]:
    if match.state == "NOT_RESEARCHED":
        return []
    return [c for c in match.claims if c.process_content and c.subject in round_.claim_subjects]


def round_summaries(match: ScopeMatch) -> list[RoundSummary]:
    return [
        RoundSummary(
            key=r.key, ordinal=r.ordinal, label_key=r.label_key, competency_keys=list(r.competency_keys),
            basis="PUBLISHED_GUIDANCE" if _round_claims(match, r) else "MIRROR_SUGGESTED",
        )
        for r in ROUNDS
    ]


_BAND_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def competencies_in_process(match: ScopeMatch) -> list[CompetencyInProcess]:
    """Research-derived coverage only when research matched; otherwise no round counts or bands."""
    out: dict[str, dict[str, Any]] = {}
    for round_ in ROUNDS:
        claims = _round_claims(match, round_)
        for key in round_.competency_keys:
            row = out.setdefault(key, {"round_count": 0, "ordinal": round_.ordinal, "band": None})
            row["ordinal"] = min(row["ordinal"], round_.ordinal)
            if claims:
                row["round_count"] += 1
                best = max((c.confidence_band for c in claims), key=_BAND_ORDER.__getitem__)
                if row["band"] is None or _BAND_ORDER[best] > _BAND_ORDER[row["band"]]:
                    row["band"] = best
    return [
        CompetencyInProcess(key=key, round_count=row["round_count"], first_round_ordinal=row["ordinal"], band=row["band"])
        for key, row in out.items()
    ]


def practice_facts(links: Sequence[TargetSessionLink]) -> dict[str, PracticeFact]:
    facts: dict[str, tuple[int, date | None]] = {}
    for link in links:
        if link.round_key is None:
            continue
        try:
            round_ = get_round(link.round_key)
        except KeyError:
            continue
        day = link.created_at.date()
        for key in round_.competency_keys:
            count, last = facts.get(key, (0, None))
            facts[key] = (count + 1, max(day, last) if last else day)
    return {key: PracticeFact(count=count, last_practised_on=last) for key, (count, last) in facts.items()}


def prompt_set_id_for(user_id: UUID, target_id: UUID, round_key: str, idempotency_key: UUID) -> UUID:
    """Deterministic, so a replayed start reuses the prompts it stored the first time."""
    return uuid5(NAMESPACE_URL, f"mirror:target-prompts:{user_id}:{target_id}:{round_key}:{idempotency_key}")


# ------------------------------------------------------------------ service


class TargetService:
    def __init__(
        self,
        repo: TargetRepository,
        catalogs: CatalogProvider,
        roles: Any,
        stories: Any,
        engine: Any,
        *,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._repo = repo
        self._catalogs = catalogs
        self._roles = roles
        self._stories = stories
        self._engine = engine
        self._today = today

    # targets ---------------------------------------------------------

    async def create(self, user_id: UUID, payload: TargetCreate) -> tuple[CandidateTarget, InterviewBlueprint]:
        await self._roles.get(payload.role_profile_id, user_id)  # RoleProfileNotFoundForUser -> 404
        catalog = self._latest()
        values = TargetValues(
            role_profile_id=payload.role_profile_id,
            company_label=payload.company,
            company_key=COMPANY_KEYS.get(payload.company.casefold()),
            role_family_key=payload.role_family,
            level_key=payload.level,  # explicit choice only; never derived from the role
            level_label=None,
            geography_key=payload.geography,
            geography_label=payload.geography_label,
            interview_date=payload.interview_date,
        )
        target = await self._repo.create_target(user_id, values)
        blueprint = await self._pin(user_id, target, catalog)
        return target, blueprint

    async def list(self, user_id: UUID) -> list[CandidateTarget]:
        return await self._repo.list_targets(user_id)

    async def get(self, target_id: UUID, user_id: UUID) -> CandidateTarget:
        target = await self._repo.get_target(target_id, user_id)
        if target is None:
            raise TargetNotFound
        return target

    async def archive(self, target_id: UUID, user_id: UUID) -> CandidateTarget:
        await self.get(target_id, user_id)
        archived = await self._repo.archive_target(target_id, user_id)
        if archived is None:
            raise TargetNotFound
        return archived

    # blueprint --------------------------------------------------------

    def _latest(self) -> RepoResearchCatalog:
        try:
            return self._catalogs.latest()
        except Exception as exc:  # noqa: BLE001 - lock/policy failure means no research is served
            raise CatalogUnavailable from exc

    async def _pin(self, user_id: UUID, target: CandidateTarget, catalog: RepoResearchCatalog) -> InterviewBlueprint:
        match = scope_match(target, catalog)
        pin = BlueprintPin(
            catalog_version=catalog.version, catalog_sha256=catalog.content_sha256,
            match_state=match.state, rules_version=BLUEPRINT_RULES_VERSION,
        )
        return await self._repo.create_blueprint(user_id, target.id, pin)

    async def _blueprints(self, user_id: UUID, target: CandidateTarget) -> list[InterviewBlueprint]:
        rows = await self._repo.blueprints(target.id, user_id)
        if not rows and target.status == "ACTIVE":
            rows = [await self._pin(user_id, target, self._latest())]
        return rows

    def _pinned_match(
        self, target: CandidateTarget, pin: InterviewBlueprint
    ) -> tuple[ContentState, ScopeMatch | None, RepoResearchCatalog | None]:
        catalog = self._catalogs.at(pin.catalog_version)
        if catalog is None:
            return "CATALOG_UNAVAILABLE", None, None
        if catalog.content_sha256 != pin.catalog_sha256:
            logger.error("blueprint pin hash mismatch", extra={"blueprint_id": str(pin.id)})
            return "PIN_MISMATCH", None, None
        return "SERVED", scope_match(target, catalog), catalog

    def _ref(self, pin: InterviewBlueprint, latest_version: int) -> BlueprintRef:
        try:
            newest = self._catalogs.latest()
            refresh = (newest.version, newest.content_sha256) != (pin.catalog_version, pin.catalog_sha256)
        except Exception:  # noqa: BLE001
            refresh = False
        return BlueprintRef(
            version=pin.version, catalog_version=pin.catalog_version, catalog_sha256=pin.catalog_sha256,
            match_state=pin.match_state, rules_version=pin.rules_version, created_at=pin.created_at,
            latest_version=latest_version, refresh_available=refresh and pin.version == latest_version,
        )

    async def blueprint(self, target_id: UUID, user_id: UUID, version: int | None = None) -> BlueprintView:
        target = await self.get(target_id, user_id)
        rows = await self._blueprints(user_id, target)
        if not rows:
            raise BlueprintNotFound
        pin = rows[-1] if version is None else next((row for row in rows if row.version == version), None)
        if pin is None:
            raise BlueprintNotFound
        state, match, catalog = self._pinned_match(target, pin)
        view = BlueprintView(
            availability=TargetAvailability.AVAILABLE, target=target_view(target),
            blueprint=self._ref(pin, rows[-1].version), content_state=state,
        )
        if match is None or catalog is None:
            return view
        claims, conflicts, unknowns = _content(match, catalog)
        return view.model_copy(update={
            "match_state": match.state, "research_label_key": _RESEARCH_LABEL[match.state],
            "claims": claims, "conflicts": conflicts, "unknowns": unknowns, "rounds": round_summaries(match),
        })

    async def refresh(self, target_id: UUID, user_id: UUID) -> tuple[BlueprintView, bool]:
        target = await self.get(target_id, user_id)
        if target.status != "ACTIVE":
            raise TargetArchived
        rows = await self._blueprints(user_id, target)
        catalog = self._latest()
        current = rows[-1]
        if (current.catalog_version, current.catalog_sha256) == (catalog.version, catalog.content_sha256):
            return await self.blueprint(target_id, user_id), False
        await self._pin(user_id, target, catalog)
        return await self.blueprint(target_id, user_id), True

    # rounds -----------------------------------------------------------

    async def _material(self, user_id: UUID, target: CandidateTarget) -> CandidateMaterial:
        stories = await self._stories.list_for_user(user_id)
        own = [
            s for s in stories
            if getattr(s, "archived_at", None) is None and getattr(s, "role_profile_id", None) in (None, target.role_profile_id)
        ]
        own.sort(key=lambda s: s.created_at)
        return CandidateMaterial(story_titles=tuple(s.title for s in own[:MAX_STORY_TITLES]))

    async def _pack(
        self, user_id: UUID, target: CandidateTarget, round_: PracticeRound, match: ScopeMatch | None,
        catalog: RepoResearchCatalog,
    ) -> RoundPack:
        stored = await self._repo.questions_for_target(target.id, user_id)
        context = GuardContext(
            source_excerpts=excerpts_from_catalog(catalog),
            company_names=tuple(name for name in {target.company_label, target.company_key or ""} if name),
            recent_prompts=tuple(RecentPrompt(text=q.question_text, served_on=q.created_at.date()) for q in stored),
            today=self._today(),
        )
        researched = match is not None and bool(_round_claims(match, round_))
        # Earlier prompts are excluded only while inside the guard's 30-day repeat window
        # (``recent_prompts``); older ones may be served again, so packs do not run out.
        return build_round_pack(round_, await self._material(user_id, target), context, researched=researched)

    async def round_detail(self, target_id: UUID, round_key: str, user_id: UUID) -> RoundDetail:
        try:
            round_ = get_round(round_key)
        except KeyError as exc:
            raise RoundNotFound from exc
        target = await self.get(target_id, user_id)
        rows = await self._blueprints(user_id, target)
        if not rows:
            raise BlueprintNotFound
        state, match, catalog = self._pinned_match(target, rows[-1])
        links = await self._repo.links_for_target(target.id, user_id)
        summary = next(r for r in round_summaries(match) if r.key == round_.key) if match else RoundSummary(
            key=round_.key, ordinal=round_.ordinal, label_key=round_.label_key,
            competency_keys=list(round_.competency_keys), basis="MIRROR_SUGGESTED",
        )
        mine = [link for link in links if link.round_key == round_.key]
        detail = RoundDetail(
            availability=TargetAvailability.AVAILABLE, target=target_view(target), round=summary, content_state=state,
            practice=PracticeHistory(
                count=len(mine),
                sessions=[PracticeHistoryItem(session_id=link.session_id, created_at=link.created_at) for link in mine],
            ),
        )
        # Plan coverage is not mapped to target competencies in v1, so every item is "not linked
        # to your plan"; research-derived round counts and bands only exist when research matched.
        ranked = prioritise(
            competencies_in_process(match or _empty_match()), {}, practice_facts(links), self._today(), target.interview_date,
        )
        in_round = [item for item in ranked if item.competency_key in round_.competency_keys][:MAX_PRIORITIES]
        priorities = [
            PriorityView(rank=index, competency_key=item.competency_key, reason_codes=list(item.reason_codes), suggested_mode=item.suggested_mode)
            for index, item in enumerate(in_round, start=1)
        ]
        detail = detail.model_copy(update={"priorities": priorities})
        if match is None or catalog is None:
            return detail
        claims, conflicts, unknowns = _content(match, catalog, frozenset(round_.claim_subjects))
        pack = await self._pack(user_id, target, round_, match, catalog)
        return detail.model_copy(update={
            "match_state": match.state, "research_label_key": _RESEARCH_LABEL[match.state],
            "claims": claims, "conflicts": conflicts, "unknowns": unknowns,
            "pack": PackView(
                state=pack.state, minimum=pack.minimum,
                prompts=[
                    PromptView(position=p.position, text=p.text, competency_key=p.competency_key,
                               rationale_code=p.rationale_code, provenance_class=p.provenance_class)
                    for p in pack.prompts
                ],
            ),
        })

    async def start_round_practice(
        self, target_id: UUID, round_key: str, user_id: UUID, payload: PracticeStart
    ) -> PracticeStarted:
        try:
            round_ = get_round(round_key)
        except KeyError as exc:
            raise RoundNotFound from exc
        target = await self.get(target_id, user_id)
        if target.status != "ACTIVE":
            raise TargetArchived
        role = await self._roles.get(target.role_profile_id, user_id)
        rows = await self._blueprints(user_id, target)
        pin = rows[-1]
        mode = PracticeMode(payload.mode)
        needed = MODE_SHAPE[mode].questions
        set_id = prompt_set_id_for(user_id, target.id, round_.key, payload.idempotency_key)
        stored = await self._repo.questions_for_set(set_id, user_id)
        if not stored:
            state, match, catalog = self._pinned_match(target, pin)
            if catalog is None:
                raise CatalogUnavailable
            pack = await self._pack(user_id, target, round_, match, catalog)
            if pack.state != "FULL" or len(pack.prompts) < max(needed, PACK_MIN):
                raise ShortPack(len(pack.prompts))
            try:
                stored = await self._repo.record_questions(user_id, [
                    QuestionCreate(
                        candidate_target_id=target.id, blueprint_id=pin.id, prompt_set_id=set_id, position=index,
                        round_key=round_.key, competency_key=p.competency_key, family_key=p.family_key,
                        template_id=p.template_id, generator_version=ROUND_PACK_VERSION,
                        originality_rules_version=ORIGINALITY_RULES_VERSION, question_text=p.text,
                        rationale_code=p.rationale_code, derived_from=p.derived_from, novelty_sha256=p.novelty_sha256,
                    )
                    for index, p in enumerate(pack.prompts[:needed], start=1)
                ])
            except TargetConflict:
                stored = await self._repo.questions_for_set(set_id, user_id)
                if not stored:
                    raise
        session = await self._engine.create_session_state(user_id, SessionCreate(
            target_role=role.target_role,
            role_profile_id=target.role_profile_id,
            practice_mode=mode.value,
            practice_focus=PracticeFocus.ROLE.value,
            practice_theme=round_.theme,
            idempotency_key=payload.idempotency_key,
        ))
        existing_link = await self._repo.link_for_session(session.id, user_id)
        if (
            session.role_profile_id != target.role_profile_id
            or session.practice_focus != PracticeFocus.ROLE.value
            or session.practice_theme != round_.theme
            or session.practice_mode != mode.value
            or (existing_link is not None and existing_link.prompt_set_id != set_id)
        ):
            raise LinkConflict
        wanted = TargetSessionLinkCreate(
            session_id=session.id, candidate_target_id=target.id, blueprint_id=pin.id,
            round_key=round_.key, competency_key=None, prompt_set_id=set_id,
        )
        try:
            link = await self._repo.create_link(user_id, wanted)
        except LinkAlreadyExists as exc:
            existing = exc.link
            same = existing is not None and (existing.candidate_target_id, existing.round_key, existing.prompt_set_id) == (
                wanted.candidate_target_id, wanted.round_key, wanted.prompt_set_id,
            )
            if not same:
                raise LinkConflict from exc
            link = existing
        assert link is not None
        return PracticeStarted(
            session=session,
            link=LinkView(**link.model_dump(exclude={"user_id"})),
            prompts=[PracticePromptRef(position=q.position, rationale_code=q.rationale_code) for q in sorted(stored, key=lambda q: q.position)],
        )

    # sessions and progress -------------------------------------------------

    async def session_link(self, session_id: UUID, user_id: UUID) -> LinkView | None:
        link = await self._repo.link_for_session(session_id, user_id)
        return LinkView(**link.model_dump(exclude={"user_id"})) if link else None

    async def linked_session_ids(self, target_id: UUID, user_id: UUID) -> tuple[CandidateTarget, frozenset[UUID]]:
        target = await self.get(target_id, user_id)
        links = await self._repo.links_for_target(target.id, user_id)
        return target, frozenset(link.session_id for link in links)


def _empty_match() -> ScopeMatch:
    return ScopeMatch(state="NOT_RESEARCHED", catalog_version=1, content_sha256="0" * 64, claims=(), conflict_sets=(), unknowns=())


async def linked_prompt_texts(
    repo: TargetRepository, capability: TargetCapability, session_id: UUID, user_id: UUID
) -> list[str]:
    """Load prompts linked to a session; unavailable capability or no link keeps legacy planning."""
    from .planner_repository import InterviewPlanningUnavailable

    try:
        if await capability.state() != TargetAvailability.AVAILABLE:
            return []
        link = await repo.link_for_session(session_id, user_id)
        if link is None or link.prompt_set_id is None:
            return []
        questions: list[GeneratedQuestion] = await repo.questions_for_set(link.prompt_set_id, user_id)
        return [q.question_text for q in sorted(questions, key=lambda q: q.position)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("target prompts unavailable for planning", extra={"session_id": str(session_id)}, exc_info=True)
        raise InterviewPlanningUnavailable from exc
