"""My plan: each role need once, with what you already have, what would strengthen it and what to do.

The builder is pure. It reads the Interview Map (themes in role priority order), the person's
APPROVED experience items, their stories and their own coverage links, and calls no model.

Coverage rules:
- A link always cites why it exists (TOOL, OUTCOME, DECISION, CAPABILITY or CONFIRMED).
- Word matching may only suggest: a partial overlap is a suggestion the person confirms
  or dismisses, never a link on its own.
- The person's choice wins: a confirmed link always counts, a dismissed one never shows.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .career_evidence import EvidenceItem
from .config import Settings
from .http_pool import pooled
from .interview_map import (
    DEFAULT_MATCHER,
    Coverage,
    CoverageReason,
    ExperienceState,
    InterviewMap,
    InterviewTheme,
    MapState,
    MatchStrength,
    StoryEvidence,
    coverage_for,
)

MAX_PLAN_AREAS = 5
MAX_HAVE = 3
MAX_SUGGESTED = 2


class PlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanState(StrEnum):
    READY = "READY"
    NEEDS_REVIEW = "NEEDS_REVIEW"  # approve your experience first
    PREPARING = "PREPARING"        # the role is still being read
    UNAVAILABLE = "UNAVAILABLE"    # the role could not be read
    NO_ROLE = "NO_ROLE"


class PlanStatus(StrEnum):
    STRONG = "STRONG"  # a story speaks to it
    GOOD = "GOOD"      # an approved example is linked; the explanation needs practice
    BUILD = "BUILD"    # nothing linked yet


class PlanAction(StrEnum):
    PRACTICE = "PRACTICE"
    STORY = "STORY"
    ADD_EXAMPLE = "ADD_EXAMPLE"


class PlanRole(PlanModel):
    role_profile_id: UUID
    target_role: str


class PlanProof(PlanModel):
    kind: Literal["EXPERIENCE", "STORY"]
    title: str
    reason: CoverageReason | None = None  # always set for a link; a suggestion may carry none
    evidence_item_id: UUID | None = None
    story_id: UUID | None = None


class PlanArea(PlanModel):
    key: str
    title: str                      # sentence case, for display
    theme: str                      # the role's own wording, for practice and stories
    from_job_description: bool
    why: str | None = None          # the job description excerpt it came from
    status: PlanStatus
    have: list[PlanProof] = Field(default_factory=list)
    suggested: list[PlanProof] = Field(default_factory=list)
    strengthen: str
    primary_action: PlanAction


class Plan(PlanModel):
    role: PlanRole | None = None
    state: PlanState
    areas: list[PlanArea] = Field(default_factory=list)
    recommended_area_key: str | None = None


# ------------------------------------------------------------------ coverage links


class CoverageLink(PlanModel):
    id: UUID
    user_id: UUID = Field(exclude=True)
    role_profile_id: UUID
    requirement_key: str
    evidence_item_id: UUID | None = None
    story_id: UUID | None = None
    reason: CoverageReason | None = None
    confirmed: bool = False
    dismissed: bool = False


class LinkChoice(PlanModel):
    """PUT body: confirm (true) or dismiss (false) one approved item or story for one need."""

    evidence_item_id: UUID | None = None
    story_id: UUID | None = None
    confirmed: bool

    @model_validator(mode="after")
    def one_target(self) -> LinkChoice:
        if (self.evidence_item_id is None) == (self.story_id is None):
            raise ValueError("choose exactly one example or story")
        return self


class CoverageLinksUnavailable(Exception):
    """Storage for coverage links is not configured or did not answer."""


class CoverageLinkRepository(Protocol):
    """Owner-scoped: another person's links never read or change."""

    async def list_for_role(self, user_id: UUID, role_profile_id: UUID) -> list[CoverageLink]: ...
    async def save(self, user_id: UUID, role_profile_id: UUID, requirement_key: str, choice: LinkChoice) -> CoverageLink: ...


def _link_row(user_id: UUID, role_profile_id: UUID, requirement_key: str, choice: LinkChoice) -> dict[str, Any]:
    return {
        "user_id": str(user_id),
        "role_profile_id": str(role_profile_id),
        "requirement_key": requirement_key,
        "evidence_item_id": str(choice.evidence_item_id) if choice.evidence_item_id else None,
        "story_id": str(choice.story_id) if choice.story_id else None,
        "reason": CoverageReason.CONFIRMED.value if choice.confirmed else None,
        "confirmed": choice.confirmed,
        "dismissed": not choice.confirmed,
    }


class MemoryCoverageLinkRepository:
    """In-process links for tests and for running without Supabase."""

    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, UUID, str, UUID], CoverageLink] = {}

    async def list_for_role(self, user_id: UUID, role_profile_id: UUID) -> list[CoverageLink]:
        return [row for row in self.rows.values() if row.user_id == user_id and row.role_profile_id == role_profile_id]

    async def save(self, user_id: UUID, role_profile_id: UUID, requirement_key: str, choice: LinkChoice) -> CoverageLink:
        target = choice.evidence_item_id or choice.story_id
        key = (user_id, role_profile_id, requirement_key, target)
        current = self.rows.get(key)
        link = CoverageLink(id=current.id if current else uuid4(), **_link_row(user_id, role_profile_id, requirement_key, choice))
        self.rows[key] = link
        return link


class SupabaseCoverageLinkRepository:
    """Service-role access. Every query also filters by user_id."""

    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_enabled:
            raise CoverageLinksUnavailable("Supabase storage is not configured")
        self._url = f"{settings.next_public_supabase_url.rstrip('/')}/rest/v1/coverage_links"
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
            raise CoverageLinksUnavailable from exc

    async def list_for_role(self, user_id: UUID, role_profile_id: UUID) -> list[CoverageLink]:
        rows = await self._request(
            "GET",
            {"user_id": f"eq.{user_id}", "role_profile_id": f"eq.{role_profile_id}", "select": "*", "limit": "1000"},
        )
        return [CoverageLink.model_validate(row) for row in rows]

    async def save(self, user_id: UUID, role_profile_id: UUID, requirement_key: str, choice: LinkChoice) -> CoverageLink:
        target = "evidence_item_id" if choice.evidence_item_id else "story_id"
        rows = await self._request(
            "POST",
            {"on_conflict": f"user_id,role_profile_id,requirement_key,{target}", "select": "*"},
            json=_link_row(user_id, role_profile_id, requirement_key, choice),
            prefer="resolution=merge-duplicates,return=representation",
        )
        if not rows:
            raise CoverageLinksUnavailable("the link was not saved")
        return CoverageLink.model_validate(rows[0])


# ------------------------------------------------------------------ the builder


def sentence_case(text: str) -> str:
    """"Stakeholder Management" -> "Stakeholder management"; acronyms such as SQL stay."""
    words = text.split()
    if not words:
        return text
    rest = [word.lower() if word[:1].isupper() and word[1:].islower() else word for word in words[1:]]
    return " ".join([words[0][:1].upper() + words[0][1:], *rest])


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _story_proofs(theme: InterviewTheme, stories: Sequence[StoryEvidence]) -> tuple[list[PlanProof], list[PlanProof]]:
    """A story the person tagged with this exact need counts; a story that only shares words is a suggestion."""
    linked, suggested = [], []
    for story in stories:
        proof = PlanProof(kind="STORY", title=story.title, story_id=story.id)
        if any(tag.casefold() == theme.name.casefold() for tag in story.themes):
            linked.append(proof.model_copy(update={"reason": CoverageReason.CONFIRMED}))
        elif DEFAULT_MATCHER.strength(theme.name, " ".join(story.themes)) != MatchStrength.NONE:
            suggested.append(proof)
    return linked, suggested


def _experience_proofs(theme: InterviewTheme, approved: Sequence[EvidenceItem]) -> tuple[list[PlanProof], list[PlanProof]]:
    """A full match on a field of real work is a link with its reason; a partial overlap only suggests."""
    linked, suggested = [], []
    for item in approved:
        coverage, matches = coverage_for(theme.name, None, (), evidence=[item])
        proof = PlanProof(kind="EXPERIENCE", title=item.title, evidence_item_id=item.id)
        if coverage == Coverage.EXPERIENCE:
            linked.append(proof.model_copy(update={"reason": matches[0].reason}))
        elif coverage == Coverage.MENTIONED:
            suggested.append(proof)
    return linked, suggested


def _target(proof: PlanProof) -> UUID:
    return proof.evidence_item_id or proof.story_id  # type: ignore[return-value]


def _area(
    theme: InterviewTheme,
    approved: Sequence[EvidenceItem],
    stories: Sequence[StoryEvidence],
    links: Sequence[CoverageLink],
) -> PlanArea:
    mine = [link for link in links if link.requirement_key == theme.key]
    dismissed = {link.evidence_item_id or link.story_id for link in mine if link.dismissed}
    confirmed = {link.evidence_item_id or link.story_id for link in mine if link.confirmed}

    story_linked, story_suggested = _story_proofs(theme, stories)
    work_linked, work_suggested = _experience_proofs(theme, approved)
    candidates = [*story_linked, *work_linked, *story_suggested, *work_suggested]
    # Only the person's approved items and active stories can be confirmed into the plan.
    known = {
        **{item.id: PlanProof(kind="EXPERIENCE", title=item.title, evidence_item_id=item.id) for item in approved},
        **{story.id: PlanProof(kind="STORY", title=story.title, story_id=story.id) for story in stories},
    }

    have: dict[UUID, PlanProof] = {}
    for target in confirmed:
        if target in known and target not in dismissed:
            have[target] = known[target].model_copy(update={"reason": CoverageReason.CONFIRMED})
    for proof in [*story_linked, *work_linked]:
        if _target(proof) not in dismissed:
            have.setdefault(_target(proof), proof)
    suggested = [
        proof for proof in candidates
        if proof.reason is None and _target(proof) not in dismissed and _target(proof) not in have
    ]
    ordered = sorted(have.values(), key=lambda proof: (proof.kind != "STORY", proof.reason != CoverageReason.CONFIRMED))

    status = (
        PlanStatus.STRONG if any(proof.kind == "STORY" for proof in ordered)
        else PlanStatus.GOOD if ordered
        else PlanStatus.BUILD
    )
    return PlanArea(
        key=theme.key,
        title=sentence_case(theme.name),
        theme=theme.name,
        from_job_description=theme.from_job_description,
        why=theme.source_text if theme.from_job_description else None,
        status=status,
        have=ordered[:MAX_HAVE],
        suggested=list({_target(proof): proof for proof in suggested}.values())[:MAX_SUGGESTED],
        strengthen=_strengthen(theme, status, ordered, suggested, approved),
        primary_action=PlanAction.STORY if status == PlanStatus.BUILD else PlanAction.PRACTICE,
    )


def _strengthen(
    theme: InterviewTheme,
    status: PlanStatus,
    have: Sequence[PlanProof],
    suggested: Sequence[PlanProof],
    approved: Sequence[EvidenceItem],
) -> str:
    """One concrete sentence: the smallest thing that would make this need clearer."""
    need = theme.name if theme.name.isupper() else theme.name.lower()  # "SQL" stays SQL
    if status == PlanStatus.STRONG:
        return f"Practice telling “{_short(have[0].title)}” out loud, and finish with what changed because of your work."
    if status == PlanStatus.GOOD:
        item = next((item for item in approved if item.id == have[0].evidence_item_id), None)
        if item is not None and not item.metric:
            return f"Add what changed, and by how much, so “{_short(item.title)}” ends with a clear result."
        return f"Turn “{_short(have[0].title)}” into a story: the situation, what you did and the result."
    if suggested:
        return f"Check whether “{_short(suggested[0].title)}” shows {need}. Confirm it if it does, or add another example."
    return f"Add one real example of {need}: what you did, and what changed because of it."


def build_plan(
    interview_map: InterviewMap,
    approved: Sequence[EvidenceItem],
    stories: Sequence[StoryEvidence],
    links: Sequence[CoverageLink],
) -> Plan:
    """The plan for one role. ``approved`` must already be the APPROVED items only."""
    role = PlanRole(role_profile_id=interview_map.role_profile_id, target_role=interview_map.target_role)
    if interview_map.state == MapState.ROLE_PREPARING:
        return Plan(role=role, state=PlanState.PREPARING)
    if interview_map.state != MapState.READY:
        return Plan(role=role, state=PlanState.UNAVAILABLE)
    if interview_map.experience_state == ExperienceState.NEEDS_REVIEW:
        return Plan(role=role, state=PlanState.NEEDS_REVIEW)

    approved = [item for item in approved if item.status == "APPROVED"]  # never trust the caller on this
    areas = [_area(theme, approved, stories, links) for theme in interview_map.themes[:MAX_PLAN_AREAS]]
    # The highest-priority need that is not yet strong; when everything is, the top need.
    recommended = next((area for area in areas if area.status != PlanStatus.STRONG), areas[0] if areas else None)
    return Plan(
        role=role,
        state=PlanState.READY,
        areas=areas,
        recommended_area_key=recommended.key if recommended else None,
    )


def no_role_plan() -> Plan:
    return Plan(state=PlanState.NO_ROLE)
