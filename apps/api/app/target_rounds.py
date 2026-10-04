"""Mirror's practice rounds for an interview target, and their guarded prompt packs (pure).

A practice round is what a person can rehearse in Mirror; it is not a claim about any
company's hiring stages. Every prompt is written by Mirror (class MIRROR_GENERATED) from the
templates below and may only be personalised with the person's own story titles. Each prompt
must pass ``prompt_originality.check_prompt`` and must never have been stored for this person's
target before. A pack with fewer than ``PACK_MIN`` prompts is reported as ``SHORT_PACK`` rather
than padded.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.prompt_originality import GuardContext, check_prompt, novelty_sha256

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
    provenance_class: Literal["MIRROR_GENERATED"] = "MIRROR_GENERATED"


class RoundPack(_Frozen):
    round_key: str
    state: PackState
    minimum: int = PACK_MIN
    prompts: tuple[GeneratedPrompt, ...] = Field(default_factory=tuple)


def _t(id_: str, family: str, competency: str, fallback: str, text: str | None = None) -> PromptTemplate:
    return PromptTemplate(
        id=id_, family_key=family, competency_key=competency, fallback=fallback,
        text=text or fallback, slot="story" if text else None,
    )


ROUNDS: tuple[PracticeRound, ...] = (
    PracticeRound(
        key="coding_reasoning",
        ordinal=1,
        label_key="round.coding_reasoning",
        theme="Talking through a coding approach",
        competency_keys=("algorithmic_problem_solving", "coding_quality", "technical_communication"),
        claim_subjects=("coding_interview", "online_assessment", "interview_topics"),
        templates=(
            _t("coding.parcel_status", "stateful_stream", "algorithmic_problem_solving",
               "Status updates for parcels can arrive late or twice. Talk me through how you would keep only the newest status for each parcel."),
            _t("coding.repeated_log_lines", "counting_under_memory", "algorithmic_problem_solving",
               "You have a very long list of log lines and little memory. How would you find which messages repeat most often, and what would you trade off?"),
            _t("coding.merge_streams", "ordered_merge", "algorithmic_problem_solving",
               "Walk me through how you would merge several already ordered streams of events into one ordered stream, and how the cost grows as streams are added."),
            _t("coding.same_person", "fuzzy_matching", "algorithmic_problem_solving",
               "Explain how you would spot that two entries in a large contact list are the same person when their names are spelled differently."),
            _t("coding.edge_case", "edge_cases", "coding_quality",
               "Pick one piece of code you wrote that had a tricky edge case. Explain the case and how you made sure it was handled.",
               "In “{story}”, pick one piece of logic with a tricky edge case. Explain the case and how you made sure your code handled it."),
            _t("coding.lookup_choice", "data_structure_choice", "technical_communication",
               "Talk me through how you would choose a data structure for a lookup that also needs every key between two values."),
            _t("coding.job_order", "dependency_order", "algorithmic_problem_solving",
               "How would you order a set of jobs that depend on each other, and what would you do if the dependencies formed a loop?"),
            _t("coding.check_before_handover", "self_checking", "coding_quality",
               "You have just written a small function. Which inputs would you try first before handing it over, and why those?"),
        ),
    ),
    PracticeRound(
        key="system_design",
        ordinal=2,
        label_key="round.system_design",
        theme="Designing a system",
        competency_keys=("system_design", "technical_communication"),
        claim_subjects=("online_assessment", "interview_topics"),
        templates=(
            _t("design.scheduled_prices", "scheduled_work", "system_design",
               "Design a service that lets shop owners schedule price changes for a future time. What are the main parts, and what happens if the scheduler falls behind?"),
            _t("design.order_updates", "fan_out_messaging", "system_design",
               "Sketch a system that sends order updates to millions of phones. Where would messages wait, and how would you stop the same update arriving twice?"),
            _t("design.ten_times", "growth_limits", "system_design",
               "Think of a system you worked on. What would break first if usage grew ten times, and what would you change?",
               "In “{story}”, what would break first if usage grew ten times, and what would you change?"),
            _t("design.clinic_booking", "booking_consistency", "system_design",
               "Design a booking system for a small chain of clinics. How would you stop two people booking the same slot?"),
            _t("design.van_tracking", "location_updates", "system_design",
               "Design a service that shows which delivery vans are near each depot right now. How often would you update positions, and why?"),
            _t("design.activity_feed", "precompute_vs_on_demand", "system_design",
               "How would you design a list of recent activity for each user, and what would you prepare ahead of time versus build when asked?"),
            _t("design.explain_tradeoff", "explaining_tradeoffs", "technical_communication",
               "Pick one design choice you would make for a busy online shop and explain it to someone who has never built a large system."),
        ),
    ),
    PracticeRound(
        key="behavioural",
        ordinal=3,
        label_key="round.behavioural",
        theme="Examples from your own work",
        competency_keys=("behavioural_examples",),
        claim_subjects=("interview_loop",),
        templates=(
            _t("behavioural.deadline_scope", "trade_offs", "behavioural_examples",
               "Tell me about a time you shipped something under a deadline that was not as complete as you wanted. What did you leave out, and what did you do afterwards?"),
            _t("behavioural.beyond_task", "ownership", "behavioural_examples",
               "Tell me about a time you noticed a problem outside your own task and decided to act on it."),
            _t("behavioural.user_need", "user_focus", "behavioural_examples",
               "Tell me about a time a user's need changed how you built something."),
            _t("behavioural.own_decision", "decisions", "behavioural_examples",
               "Tell me about a decision at work that was yours alone. What did you weigh up before making it?",
               "In “{story}”, which decision was yours alone, and what did you weigh up before making it?"),
            _t("behavioural.root_cause", "digging_in", "behavioural_examples",
               "Tell me about a time you dug into the details to understand why something kept breaking."),
            _t("behavioural.technical_disagreement", "disagreement", "behavioural_examples",
               "Tell me about a time you and a teammate disagreed about a technical choice. How did you settle it?"),
            _t("behavioural.simplified", "simplifying", "behavioural_examples",
               "Tell me about a time you made something simpler for the people who had to use it."),
            _t("behavioural.own_standard", "standards", "behavioural_examples",
               "Tell me about a time you held your own work to a higher standard than anyone asked for. What did that cost, and was it worth it?"),
        ),
    ),
)

_BY_KEY = {round_.key: round_ for round_ in ROUNDS}


def get_round(key: str) -> PracticeRound:
    return _BY_KEY[key]


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
            ))
            break
        if limit is not None and len(prompts) >= limit:
            break
    state: PackState = "FULL" if len(prompts) >= PACK_MIN else "SHORT_PACK"
    return RoundPack(round_key=round_.key, state=state, prompts=tuple(prompts))
