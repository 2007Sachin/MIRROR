"""Interview Map: what a role is likely to explore, next to what the candidate can already show.

Deterministic and derived on read. Inputs are all versioned elsewhere (role analysis,
resume analysis, stories, the latest review), so nothing here is persisted and no
language model is called. Every coverage line carries the text it matched, so the
candidate can see why Mirror said it.

Rules this module keeps:
- Themes come only from the role analysis. Nothing is added from general knowledge.
- Coverage comes only from the candidate's own material. Nothing is inferred.
- When an approved-experience source is given, coverage reads only APPROVED Career
  Evidence items (never raw resume text), and every match says why it exists.
- Questions are "worth preparing for", never a prediction of what will be asked.
- No number is produced. States are the four codes below.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .dashboard_summary import LatestReview
from .resume_models import ResumeAgentOutput, ResumeAnalysisResponse, ResumeClaimType
from .role_models import (
    CompetencyCategory,
    CompetencySourceType,
    RoleAnalysisResponse,
    RoleAnalysisStatus,
    StoredRoleCompetency,
)

if TYPE_CHECKING:
    from .career_evidence import EvidenceItem

MAX_THEMES = 6
MAX_AREAS = 3
MAX_QUESTIONS = 5


class MapModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Coverage(StrEnum):
    PREPARED = "PREPARED"      # a story the candidate wrote speaks to it
    EXPERIENCE = "EXPERIENCE"  # a piece of work on the resume uses it
    MENTIONED = "MENTIONED"    # named on the resume, not shown in any work
    MISSING = "MISSING"        # nothing in the candidate's material speaks to it


class MapState(StrEnum):
    READY = "READY"
    ROLE_PREPARING = "ROLE_PREPARING"
    ROLE_UNREADABLE = "ROLE_UNREADABLE"


class ExperienceState(StrEnum):
    READY = "READY"
    MISSING = "MISSING"
    READING = "READING"
    UNREADABLE = "UNREADABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"  # the resume is read; review and approve your experience first


class CoverageReason(StrEnum):
    """Why a piece of approved experience counts for a theme: which field matched."""

    TOOL = "TOOL"              # the theme is a tool the item names
    OUTCOME = "OUTCOME"        # the item's outcome or measured result speaks to it
    DECISION = "DECISION"      # the item describes a decision or recommendation about it
    CAPABILITY = "CAPABILITY"  # the item's own statement shows it
    CONFIRMED = "CONFIRMED"    # the person tagged their own story with it


class AreaAction(StrEnum):
    FIND_STORY = "FIND_STORY"
    PRESSURE_TEST = "PRESSURE_TEST"
    PRACTICE = "PRACTICE"
    ADD_EXPERIENCE = "ADD_EXPERIENCE"


class CoverageMatch(MapModel):
    kind: str  # STORY, WORK, PROJECT, ACHIEVEMENT, SKILL, TOOL
    label: str
    text: str
    # Set only for a STORY match, so the frontend can link straight to practising that
    # exact story instead of the generic role-focused practice. Never set for work,
    # project, achievement, skill or tool matches, which have no story to open.
    story_id: UUID | None = None
    reason: CoverageReason | None = None
    # Set only for an approved experience item, so the frontend can link to it.
    evidence_id: UUID | None = None


class InterviewTheme(MapModel):
    key: str
    name: str
    category: CompetencyCategory
    from_job_description: bool
    source_text: str | None = None
    coverage: Coverage
    matches: list[CoverageMatch] = Field(default_factory=list)


class PreparationArea(MapModel):
    key: str
    title: str
    body: str
    action: AreaAction
    theme_key: str | None = None
    focus: str | None = None


class SuggestedQuestion(MapModel):
    text: str
    theme_key: str | None = None
    why: str


class InterviewMap(MapModel):
    role_profile_id: UUID
    target_role: str
    state: MapState
    experience_state: ExperienceState
    role_from_job_description: bool = False
    themes: list[InterviewTheme] = Field(default_factory=list)
    preparation_areas: list[PreparationArea] = Field(default_factory=list)
    questions: list[SuggestedQuestion] = Field(default_factory=list)
    also_expected: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class StoryEvidence:
    """The parts of a story the map reads. The story itself is the candidate's text."""

    id: UUID
    title: str
    themes: tuple[str, ...]
    text: str


# ------------------------------------------------------------------ word matching

_STOP = frozenset(
    """and the for with using use used of to in on a an or by at as is be are from into via
    ability able strong good great excellent solid working work experience experienced skill
    skills knowledge understanding proficiency proficient familiarity familiar hands
    related relevant basic advanced intermediate level years year etc other various across""".split()
)
_SUFFIXES = ("ations", "ation", "ings", "ing", "ment", "ments", "ies", "ers", "er", "ed", "es", "s", "al")


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[: -len(suffix)]
            break
    # "manage" and "managed" should meet at "manag"; "price" and "pricing" at "pric".
    return word[:-1] if word.endswith("e") and len(word) > 4 else word


def words(text: str) -> frozenset[str]:
    tokens = re.split(r"[^a-z0-9+#]+", text.casefold())
    return frozenset(_stem(token) for token in tokens if len(token) > 2 and token not in _STOP)


def _overlaps(needle: frozenset[str], text: str) -> bool:
    return bool(needle) and not needle.isdisjoint(words(text))


class MatchStrength(StrEnum):
    NONE = "NONE"
    WEAK = "WEAK"      # shares a word with the theme, not enough to say it is the same thing
    USEFUL = "USEFUL"  # most of the theme's words, or a known alias, appear


# A few common equivalents, written as plain words and stemmed once below.
# Deliberately small: each entry must be obvious to a reader.
_ALIAS_WORDS: dict[str, tuple[str, ...]] = {
    "stakeholder": ("client", "cross-functional", "partner"),
    "communication": ("presented", "presentation", "explained", "storytelling"),
    "analysis": ("analytics", "analytical", "insights"),
    "experimentation": ("hypothesis", "pilot", "a/b"),
    "sql": ("query", "database", "postgres", "mysql"),
    "leadership": ("led", "lead", "mentored", "managed"),
    "forecasting": ("projection", "predicted"),
}
_ALIASES: dict[str, frozenset[str]] = {
    _stem(key): frozenset(stem for value in values for stem in words(value))
    for key, values in _ALIAS_WORDS.items()
}


def _normalise(text: str) -> str:
    return text.replace("&", " and ").replace("/", " / ")


class ThemeMatcher(Protocol):
    """How strongly a piece of the candidate's text speaks to one role theme.

    The interface a semantic matcher would implement later; nothing else in this
    module depends on how the strength is decided.
    """

    def strength(self, theme: str, text: str) -> MatchStrength: ...


class WordMatcher:
    """Deterministic, explainable word overlap with light stemming and a few aliases."""

    def strength(self, theme: str, text: str) -> MatchStrength:
        needle = words(_normalise(theme))
        if not needle:
            return MatchStrength.NONE
        haystack = words(_normalise(text))
        covered = {
            stem for stem in needle
            if stem in haystack
            or not _ALIASES.get(stem, frozenset()).isdisjoint(haystack)
        }
        if not covered:
            return MatchStrength.NONE
        # Short themes ("Data analysis") need every word; longer ones need at least half.
        enough = len(covered) == len(needle) if len(needle) <= 2 else len(covered) * 2 >= len(needle)
        return MatchStrength.USEFUL if enough else MatchStrength.WEAK


DEFAULT_MATCHER: ThemeMatcher = WordMatcher()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:80] or "theme"


# ------------------------------------------------------------------ candidate material


@dataclass(frozen=True)
class _Material:
    kind: str
    label: str
    text: str


def _named(output: ResumeAgentOutput | None) -> list[_Material]:
    if output is None:
        return []
    named = [_Material("SKILL", skill.name, skill.name) for skill in output.skills]
    named += [_Material("TOOL", tool.name, tool.name) for tool in output.tools]
    return named


def _used(output: ResumeAgentOutput | None) -> list[_Material]:
    if output is None:
        return []
    used: list[_Material] = []
    for job in output.work_experience:
        body = " ".join([job.role, job.description, *job.claimed_responsibilities, *job.claimed_outcomes])
        used.append(_Material("WORK", f"{job.role}, {job.organization}", body))
    for project in output.projects:
        body = " ".join(
            [project.project_name, project.description, *project.technologies,
             *project.claimed_responsibilities, *project.claimed_outcomes]
        )
        used.append(_Material("PROJECT", project.project_name, body))
    for achievement in output.achievements:
        used.append(_Material("ACHIEVEMENT", achievement.title, f"{achievement.title} {achievement.description}"))
    return used


def _excerpt(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def coverage_for(
    name: str,
    output: ResumeAgentOutput | None,
    stories: Sequence[StoryEvidence],
    matcher: ThemeMatcher = DEFAULT_MATCHER,
    *,
    evidence: Sequence[EvidenceItem] | None = None,
) -> tuple[Coverage, list[CoverageMatch]]:
    """Strongest thing the candidate's own material shows for one theme.

    A story counts when the candidate tagged it with the theme (or a close wording).
    Work counts as useful experience only on a USEFUL match; a WEAK overlap with work,
    or a skill named on the resume, is "mentioned, not yet shown". With ``evidence`` (the
    person's APPROVED items), raw resume output is ignored entirely.
    """
    story_hits = [
        story for story in stories
        if any(theme.casefold() == name.casefold() for theme in story.themes)
        or matcher.strength(name, " ".join(story.themes)) != MatchStrength.NONE
    ]
    if story_hits:
        return Coverage.PREPARED, [
            CoverageMatch(
                kind="STORY", label=story.title, text=_excerpt(story.text or story.title), story_id=story.id,
                reason=CoverageReason.CONFIRMED,
            )
            for story in _unique(story_hits, lambda story: story.title)[:2]
        ]
    if evidence is not None:
        return _evidence_coverage(name, evidence, matcher)
    graded = [(item, matcher.strength(name, item.text)) for item in _used(output)]
    useful = [item for item, strength in graded if strength == MatchStrength.USEFUL]
    if useful:
        return Coverage.EXPERIENCE, [
            CoverageMatch(kind=item.kind, label=item.label, text=_excerpt(item.text))
            for item in _unique(useful, lambda item: item.label)[:2]
        ]
    weak = [item for item, strength in graded if strength == MatchStrength.WEAK]
    named = [item for item in _named(output) if matcher.strength(name, item.text) != MatchStrength.NONE]
    if named or weak:
        mentioned = _unique([*named, *weak], lambda item: item.label)
        return Coverage.MENTIONED, [
            CoverageMatch(kind=item.kind, label=item.label, text=_excerpt(item.text)) for item in mentioned[:2]
        ]
    return Coverage.MISSING, []


_DECISION = re.compile(
    r"\b(?:decid\w*|decision\w*|chose|chosen|choos\w*|recommend\w*|prioriti[sz]\w*|trade-?offs?|selected|proposed)\b",
    re.IGNORECASE,
)


def _reason(name: str, item: EvidenceItem, matcher: ThemeMatcher) -> CoverageReason | None:
    """Which field of an approved item shows the theme. A bare skill name never does."""
    if item.kind == "SKILL":
        return None
    if any(matcher.strength(name, tool) == MatchStrength.USEFUL for tool in item.tools):
        return CoverageReason.TOOL
    if matcher.strength(name, " ".join(filter(None, (item.outcome, item.metric)))) == MatchStrength.USEFUL:
        return CoverageReason.OUTCOME
    statement = " ".join(filter(None, (item.title, item.detail)))
    if matcher.strength(name, statement) == MatchStrength.USEFUL:
        return CoverageReason.DECISION if _DECISION.search(statement) else CoverageReason.CAPABILITY
    return None


def _evidence_match(item: EvidenceItem, reason: CoverageReason) -> CoverageMatch:
    return CoverageMatch(
        kind=str(item.kind), label=_excerpt(item.title, 120), text=_excerpt(item.title), reason=reason, evidence_id=item.id
    )


def _evidence_coverage(
    name: str, evidence: Sequence[EvidenceItem], matcher: ThemeMatcher
) -> tuple[Coverage, list[CoverageMatch]]:
    """EXPERIENCE needs a full match on a field of real work; a skill name or a partial overlap is MENTIONED."""
    approved = [item for item in evidence if item.status == "APPROVED"]
    shown = [(item, reason) for item in approved if (reason := _reason(name, item, matcher))]
    if shown:
        return Coverage.EXPERIENCE, [
            _evidence_match(item, reason) for item, reason in _unique(shown, lambda pair: pair[0].title)[:2]
        ]
    named = [
        item for item in approved
        if matcher.strength(name, " ".join(filter(None, (item.title, item.detail, item.outcome, *item.tools))))
        != MatchStrength.NONE
    ]
    if named:
        return Coverage.MENTIONED, [
            _evidence_match(item, CoverageReason.CAPABILITY) for item in _unique(named, lambda item: item.title)[:2]
        ]
    return Coverage.MISSING, []


def _unique(items, key):
    """Drop repeats (the same project listed twice, the same skill twice) keeping order."""
    seen: set[str] = set()
    kept = []
    for item in items:
        marker = " ".join(key(item).casefold().split())
        if marker in seen:
            continue
        seen.add(marker)
        kept.append(item)
    return kept


# ------------------------------------------------------------------ questions

_QUESTION_TEMPLATES: dict[CompetencyCategory, tuple[str, ...]] = {
    CompetencyCategory.ANALYTICAL: (
        "Tell me about a decision you made using data.",
        "Describe a time the numbers you worked with changed what the team decided.",
    ),
    CompetencyCategory.TECHNICAL: (
        "Walk me through how you used {name} on a real problem.",
        "What was the hardest part of {name} in your work, and how did you handle it?",
    ),
    CompetencyCategory.TOOL: ("Which parts of {name} have you used, and for what?",),
    CompetencyCategory.DOMAIN: ("What do you know about {name}, and where have you worked close to it?",),
    CompetencyCategory.BEHAVIOURAL: (
        "Tell me about a time {name} really mattered in your work.",
        "Describe a situation where you disagreed with someone about how to approach the work.",
    ),
    CompetencyCategory.COMMUNICATION: (
        "Tell me about a time you had to explain something complex to someone outside your team.",
    ),
}


def _question_for(theme: InterviewTheme, used: set[str]) -> SuggestedQuestion | None:
    for template in _QUESTION_TEMPLATES.get(theme.category, ()):
        text = template.format(name=theme.name.lower() if theme.category == CompetencyCategory.BEHAVIOURAL else theme.name)
        if text in used:
            continue
        why = {
            Coverage.MISSING: f"This role looks for {theme.name.lower()}, and you don't have an example for it yet.",
            Coverage.MENTIONED: f"Your resume names {theme.name.lower()}, so expect to be asked where you actually used it.",
            Coverage.EXPERIENCE: f"You have relevant experience for {theme.name.lower()}. Preparing it as a story makes it easier to explain.",
            Coverage.PREPARED: f"You've prepared a story for {theme.name.lower()}. Practise telling it out loud.",
        }[theme.coverage]
        return SuggestedQuestion(text=text, theme_key=theme.key, why=why)
    return None


# ------------------------------------------------------------------ the map


def _unmeasured_outcomes(
    resume: ResumeAnalysisResponse | None, evidence: Sequence[EvidenceItem] | None = None
) -> bool:
    """True when the person's results almost never say how big they were."""
    if evidence is not None:
        results = [item for item in evidence if item.status == "APPROVED" and item.kind in ("ACHIEVEMENT", "PROJECT")]
        return len(results) >= 3 and sum(1 for item in results if item.metric) * 4 < len(results)
    if resume is None:
        return False
    outcomes = [
        claim for claim in resume.claims
        if claim.claim_type in (ResumeClaimType.OUTCOME, ResumeClaimType.SCALE, ResumeClaimType.PROJECT)
    ]
    if len(outcomes) < 3:
        return False
    measured = [claim for claim in outcomes if claim.metric_value is not None]
    return len(measured) * 4 < len(outcomes)  # fewer than a quarter say by how much


def _review_needs_impact(review: LatestReview | None) -> bool:
    if review is None:
        return False
    impact = next((item for item in review.dimensions if item.key == "impact"), None)
    return impact is not None and impact.state in ("Needs attention", "Could go further")


def _themes(role: RoleAnalysisResponse) -> list[StoredRoleCompetency]:
    ordered = sorted(role.competencies, key=lambda item: item.importance_weight, reverse=True)
    seen: set[str] = set()
    unique: list[StoredRoleCompetency] = []
    for item in ordered:
        key = item.name.casefold().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:MAX_THEMES]


def experience_state(
    resume: ResumeAnalysisResponse | None,
    has_resume_document: bool,
    evidence: Sequence[EvidenceItem] | None = None,
) -> ExperienceState:
    """With an approved-experience source, READY means at least one APPROVED item."""
    if evidence is not None:
        if any(item.status == "APPROVED" for item in evidence):
            return ExperienceState.READY
        state = experience_state(resume, has_resume_document)
        return ExperienceState.NEEDS_REVIEW if state == ExperienceState.READY else state
    if not has_resume_document:
        return ExperienceState.MISSING
    if resume is None or resume.status == "PROCESSING":
        return ExperienceState.READING
    if resume.status == "FAILED" or resume.output is None:
        return ExperienceState.UNREADABLE
    return ExperienceState.READY


def build_interview_map(
    role: RoleAnalysisResponse,
    resume: ResumeAnalysisResponse | None,
    *,
    has_resume_document: bool,
    stories: Sequence[StoryEvidence] = (),
    latest_review: LatestReview | None = None,
    evidence: Sequence[EvidenceItem] | None = None,
) -> InterviewMap:
    """``evidence`` is the person's experience items. When given, only the APPROVED ones count
    and raw resume output is never read; ``None`` keeps the older path for callers without one."""
    version = role.latest_analysis
    experience = experience_state(resume, has_resume_document, evidence)
    base = {
        "role_profile_id": role.id,
        "target_role": role.target_role,
        "experience_state": experience,
    }
    if version is None or version.status == RoleAnalysisStatus.PROCESSING:
        return InterviewMap(state=MapState.ROLE_PREPARING, **base)
    if version.status == RoleAnalysisStatus.FAILED or version.output is None or not role.competencies:
        return InterviewMap(state=MapState.ROLE_UNREADABLE, **base)

    output = resume.output if evidence is None and experience == ExperienceState.READY and resume else None
    approved = [item for item in evidence if item.status == "APPROVED"] if evidence is not None else None
    themes: list[InterviewTheme] = []
    for item in _themes(role):
        coverage, matches = coverage_for(item.name, output, stories, evidence=approved)
        from_jd = item.source_type != CompetencySourceType.SYNTHETIC_CANONICAL
        themes.append(
            InterviewTheme(
                key=slug(item.name),
                name=item.name,
                category=item.category,
                from_job_description=from_jd,
                source_text=_excerpt(item.source_reference, 220) if from_jd else None,
                coverage=coverage,
                matches=matches,
            )
        )

    return InterviewMap(
        state=MapState.READY,
        role_from_job_description=any(theme.from_job_description for theme in themes),
        themes=themes,
        preparation_areas=preparation_areas(themes, experience, resume, latest_review, approved),
        questions=suggested_questions(themes),
        also_expected=list(version.output.behavioural_expectations[:4]),
        **base,
    )


def preparation_areas(
    themes: Sequence[InterviewTheme],
    experience: ExperienceState,
    resume: ResumeAnalysisResponse | None,
    latest_review: LatestReview | None,
    evidence: Sequence[EvidenceItem] | None = None,
) -> list[PreparationArea]:
    """At most three things worth preparing, each with one action and a reason."""
    if experience == ExperienceState.NEEDS_REVIEW:
        # ADD_EXPERIENCE already leads to /experience, where the review happens.
        return [
            PreparationArea(
                key="review-experience",
                title="Review your experience first",
                body="Mirror has read your resume. Check what it found and approve what's accurate, so this plan only uses experience you've confirmed.",
                action=AreaAction.ADD_EXPERIENCE,
            )
        ]
    if experience == ExperienceState.MISSING:
        return [
            PreparationArea(
                key="add-experience",
                title="Add your experience",
                body="Mirror can see what this role looks for, but not your background yet. Add your resume to see which areas you already have examples for.",
                action=AreaAction.ADD_EXPERIENCE,
            )
        ]

    areas: list[PreparationArea] = []
    if _review_needs_impact(latest_review):
        areas.append(
            PreparationArea(
                key="impact-from-practice",
                title="Measurable impact",
                body="In your latest practice for this role, your answers explained the work but often stopped before saying what changed because of it.",
                action=AreaAction.PRACTICE,
                focus="impact",
            )
        )
    elif _unmeasured_outcomes(resume, evidence):
        areas.append(
            PreparationArea(
                key="impact-from-resume",
                title="Measurable impact",
                body="Your resume describes what you worked on, but few statements say what changed or by how much. Expect to be asked.",
                action=AreaAction.PRESSURE_TEST,
                focus="impact",
            )
        )

    for theme in themes:
        if len(areas) >= MAX_AREAS:
            break
        if theme.coverage == Coverage.MISSING:
            areas.append(
                PreparationArea(
                    key=f"find-{theme.key}",
                    title=theme.name,
                    body=f"This role emphasises {theme.name.lower()}, but we haven't found an example of it in your experience yet.",
                    action=AreaAction.FIND_STORY,
                    theme_key=theme.key,
                )
            )
        elif theme.coverage == Coverage.MENTIONED:
            areas.append(
                PreparationArea(
                    key=f"show-{theme.key}",
                    title=theme.name,
                    body=f"Your resume names {theme.name.lower()}, but no project or role shows you using it. Prepare one real example.",
                    action=AreaAction.FIND_STORY,
                    theme_key=theme.key,
                )
            )
    return areas[:MAX_AREAS]


def suggested_questions(themes: Iterable[InterviewTheme]) -> list[SuggestedQuestion]:
    """Least-prepared themes first, one question each, no repeats."""
    rank = {Coverage.MISSING: 0, Coverage.MENTIONED: 1, Coverage.EXPERIENCE: 2, Coverage.PREPARED: 3}
    used: set[str] = set()
    questions: list[SuggestedQuestion] = []
    for theme in sorted(themes, key=lambda item: rank[item.coverage]):
        question = _question_for(theme, used)
        if question is None:
            continue
        used.add(question.text)
        questions.append(question)
        if len(questions) >= MAX_QUESTIONS:
            break
    return questions
