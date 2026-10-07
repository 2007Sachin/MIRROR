"""Mirror's practice rounds for an interview target, and their guarded prompt packs (pure).

A practice round is what a person can rehearse in Mirror; it is not a claim about any
company's hiring stages. Rounds and their templates are role-family data in the locked
taxonomy (``app.target_taxonomy``); nothing here knows any company or role family. Every
prompt is written by Mirror (class MIRROR_GENERATED) from those templates and may only be personalised with the person's own story titles. Each prompt
must pass ``prompt_originality.check_prompt`` (which refuses a repeat of anything served to this
person in the last 30 days) and never repeats inside one practice set. A pack with fewer than ``PACK_MIN`` prompts is reported as ``SHORT_PACK`` rather
than padded.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.prompt_originality import GuardContext, check_prompt, novelty_sha256

if TYPE_CHECKING:
    from app.target_taxonomy import PromptTemplateData, RoundData, Taxonomy

ROUND_PACK_VERSION = "round-pack-1"
PACK_MIN = 4

PackState = Literal["FULL", "SHORT_PACK"]
Rationale = Literal["PUBLISHED_GUIDANCE_AREA", "MIRROR_SUGGESTED", "YOUR_STORY"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PromptTemplate(_Frozen):
    id: str
    family_key: str
    competency_key: str
    text: str  # may contain one "{story}" slot
    fallback: str  # used when the slot cannot be filled from the person's own data
    slot: Literal["story"] | None = None


class PracticeRound(_Frozen):
    key: str
    ordinal: int
    label_key: str
    theme: str  # practice_theme for the session (role focus); plain words
    question_family: str  # the format its prompts take (taxonomy question family key)
    competency_keys: tuple[str, ...]
    claim_subjects: tuple[str, ...]  # research claim subjects that describe this area
    templates: tuple[PromptTemplate, ...]


class CandidateMaterial(_Frozen):
    """Only the person's own data that a prompt may name."""

    story_titles: tuple[str, ...] = ()


class GeneratedPrompt(_Frozen):
    position: int
    text: str
    template_id: str
    family_key: str
    competency_key: str
    rationale_code: Rationale
    derived_from: dict[str, Any]
    novelty_sha256: str
    question_family: str
    provenance_class: Literal["MIRROR_GENERATED"] = "MIRROR_GENERATED"


class RoundPack(_Frozen):
    round_key: str
    state: PackState
    minimum: int = PACK_MIN
    prompts: tuple[GeneratedPrompt, ...] = Field(default_factory=tuple)


def _template(data: PromptTemplateData) -> PromptTemplate:
    return PromptTemplate(
        id=data.id, family_key=data.family_key, competency_key=data.competency_key,
        fallback=data.fallback, text=data.story_text or data.fallback,
        slot="story" if data.story_text else None,
    )


def _round(data: RoundData) -> PracticeRound:
    return PracticeRound(
        key=data.key,
        ordinal=data.ordinal,
        label_key=f"round.{data.key}",
        theme=data.theme,
        question_family=data.question_family,
        competency_keys=data.competency_keys,
        claim_subjects=data.claim_subjects,
        templates=tuple(_template(t) for t in data.templates),
    )


_ROUNDS_CACHE: dict[tuple[str, str], tuple[PracticeRound, ...]] = {}


def practice_rounds_for(taxonomy: Taxonomy, role_family: str) -> tuple[PracticeRound, ...]:
    """The role family's practice rounds from taxonomy data, in ordinal order; () when unknown."""
    cache_key = (taxonomy.sha256, role_family)
    if cache_key not in _ROUNDS_CACHE:
        family = taxonomy.document.role_families.get(role_family)
        rounds = tuple(sorted((_round(r) for r in family.rounds), key=lambda r: r.ordinal)) if family else ()
        _ROUNDS_CACHE[cache_key] = rounds
    return _ROUNDS_CACHE[cache_key]


def find_round(rounds: Sequence[PracticeRound], key: str) -> PracticeRound:
    """The round with this key among a target's own rounds; KeyError for any other key."""
    for round_ in rounds:
        if round_.key == key:
            return round_
    raise KeyError(key)


def _candidates(template: PromptTemplate, stories: Sequence[str], next_story: int) -> list[tuple[str, list[str]]]:
    """(text, story titles used) options in preference order; a slot uses only given titles."""
    options: list[tuple[str, list[str]]] = []
    if template.slot == "story" and stories:
        title = stories[next_story % len(stories)]
        options.append((template.text.replace("{story}", title), [title]))
    options.append((template.fallback, []))
    return options


def build_round_pack(
    round_: PracticeRound,
    material: CandidateMaterial,
    context: GuardContext,
    *,
    researched: bool,
    used_hashes: frozenset[str] = frozenset(),
    limit: int | None = None,
) -> RoundPack:
    """Every template that yields a guarded, never-stored prompt, in template order."""
    stories = [title.strip() for title in material.story_titles if title and title.strip()]
    prompts: list[GeneratedPrompt] = []
    seen = set(used_hashes)
    story_index = 0
    for template in round_.templates:
        for text, titles in _candidates(template, stories, story_index):
            digest = novelty_sha256(text)
            if digest in seen or not check_prompt(text, context).ok:
                continue
            if titles:
                story_index += 1
            rationale: Rationale = (
                "YOUR_STORY" if titles else "PUBLISHED_GUIDANCE_AREA" if researched else "MIRROR_SUGGESTED"
            )
            seen.add(digest)
            prompts.append(GeneratedPrompt(
                position=len(prompts) + 1,
                text=text,
                template_id=template.id,
                family_key=template.family_key,
                competency_key=template.competency_key,
                rationale_code=rationale,
                derived_from={"round_key": round_.key, "story_titles": titles},
                novelty_sha256=digest,
                question_family=round_.question_family,
            ))
            break
        if limit is not None and len(prompts) >= limit:
            break
    state: PackState = "FULL" if len(prompts) >= PACK_MIN else "SHORT_PACK"
    return RoundPack(round_key=round_.key, state=state, prompts=tuple(prompts))
