"""Resume Pressure Test: the follow-up questions a resume statement invites.

Framing: make sure you can explain what's on your resume clearly when someone digs
deeper. It is never "prove your resume is true".

Deterministic. Each question is chosen from what the statement itself leaves open
(no number, soft ownership words, no stated outcome), so every question can be traced
back to the statement it came from. The answer checks are presence checks on the
candidate's own words (a number, "I", a result, a reason); they describe what is in
the answer and never grade it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .interview_map import words
from .resume_models import ResumeAnalysisResponse, ResumeClaimReview, ResumeClaimType, VerificationPriority
from .role_models import RoleAnalysisResponse

MAX_ITEMS = 12
MAX_QUESTIONS = 5


class PressureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Readiness(StrEnum):
    CAN_EXPLAIN = "CAN_EXPLAIN"
    NEEDS_PREPARATION = "NEEDS_PREPARATION"


class QuestionKind(StrEnum):
    """What a follow-up digs into. Also the story part a good answer fills."""

    OWNERSHIP = "OWNERSHIP"
    MEASURE = "MEASURE"
    SOURCE_OF_NUMBER = "SOURCE_OF_NUMBER"
    OUTCOME = "OUTCOME"
    DECISION = "DECISION"
    ALTERNATIVE = "ALTERNATIVE"
    USAGE = "USAGE"


STORY_PART_FOR: dict[QuestionKind, str] = {
    QuestionKind.OWNERSHIP: "ownership",
    QuestionKind.MEASURE: "measurable_result",
    QuestionKind.SOURCE_OF_NUMBER: "measurable_result",
    QuestionKind.OUTCOME: "outcome",
    QuestionKind.DECISION: "outcome",
    QuestionKind.ALTERNATIVE: "reasoning",
    QuestionKind.USAGE: "actions",
}


class PressureQuestion(PressureModel):
    kind: QuestionKind
    text: str
    why: str
    story_part: str  # where the candidate's answer goes if they save it as a story


class PressureItem(PressureModel):
    claim_id: UUID
    statement: str
    where: str
    related_theme: str | None = None
    questions: list[PressureQuestion]
    readiness: Readiness | None = None
    story_id: UUID | None = None


class PressureTest(PressureModel):
    role_profile_id: UUID
    target_role: str
    state: str  # READY, NO_RESUME, READING, UNREADABLE
    items: list[PressureItem] = Field(default_factory=list)


class PressureResponse(PressureModel):
    claim_id: UUID
    readiness: Readiness
    updated_at: datetime


class ReadinessUpdate(PressureModel):
    readiness: Readiness


# ------------------------------------------------------------------ questions

_SOFT_OWNERSHIP = re.compile(
    r"\b(support(ed|ing)?|help(ed|ing)?|assist(ed|ing)?|contribut(ed|ing)?|involved|part of|"
    r"participat(ed|ing)?|worked on|collaborat(ed|ing)?|team)\b",
    re.IGNORECASE,
)
_RESULT_TYPES = {ResumeClaimType.OUTCOME, ResumeClaimType.SCALE, ResumeClaimType.PROJECT}
_WORK_TYPES = {ResumeClaimType.PROJECT, ResumeClaimType.RESPONSIBILITY, ResumeClaimType.EXPERIENCE}
_NAMED_TYPES = {ResumeClaimType.SKILL, ResumeClaimType.TOOL}


def statement_of(claim: ResumeClaimReview) -> str:
    """The candidate's corrected wording wins over the extracted one."""
    if claim.review_status == "NEEDS_CORRECTION" and claim.corrected_claim_text:
        return claim.corrected_claim_text
    return claim.claim_text


def questions_for(claim: ResumeClaimReview) -> list[PressureQuestion]:
    text = statement_of(claim)
    asked: list[PressureQuestion] = []

    def ask(kind: QuestionKind, question: str, why: str) -> None:
        if len(asked) < MAX_QUESTIONS and all(item.kind != kind for item in asked):
            asked.append(PressureQuestion(kind=kind, text=question, why=why, story_part=STORY_PART_FOR[kind]))

    soft = claim.ownership_language or (_SOFT_OWNERSHIP.search(text).group(0) if _SOFT_OWNERSHIP.search(text) else None)
    if claim.claim_type == ResumeClaimType.OWNERSHIP or soft:
        ask(
            QuestionKind.OWNERSHIP,
            "Which part of this did you personally own, and what did others do?",
            f"Words like “{soft}” make it hard to tell your part from the team's." if soft
            else "Interviewers want to separate your work from the team's.",
        )
    if claim.claim_type in _RESULT_TYPES and claim.metric_value is None:
        ask(QuestionKind.MEASURE, "How did you know it worked? What did you measure?",
            "The statement describes a result but doesn't say how big it was.")
    if claim.metric_value is not None:
        ask(QuestionKind.SOURCE_OF_NUMBER, "Where did that number come from, and what was it compared against?",
            "A number on a resume almost always invites this follow-up.")
    if claim.claim_type in _WORK_TYPES and not claim.outcome:
        ask(QuestionKind.OUTCOME, "What changed because of this work?",
            "The statement says what you did, not what happened afterwards.")
    if claim.claim_type in _NAMED_TYPES:
        ask(QuestionKind.USAGE, "Walk me through a time you used this, and why it was the right choice.",
            "Naming a skill invites a request for a real example.")
    if claim.claim_type in _WORK_TYPES or claim.claim_type in _RESULT_TYPES:
        ask(QuestionKind.DECISION, "What decision did this work influence?",
            "Interviewers often want to know why the work mattered.")
    ask(QuestionKind.ALTERNATIVE, "What alternative did you consider, and why didn't you choose it?",
        "Explaining a choice shows how you think, not only what you did.")
    return asked


# ------------------------------------------------------------------ ordering

_PRIORITY = {VerificationPriority.HIGH: 0, VerificationPriority.MEDIUM: 1, VerificationPriority.LOW: 2}
_TYPE_ORDER = {
    ResumeClaimType.OUTCOME: 0, ResumeClaimType.SCALE: 0, ResumeClaimType.OWNERSHIP: 1,
    ResumeClaimType.PROJECT: 1, ResumeClaimType.RESPONSIBILITY: 2, ResumeClaimType.EXPERIENCE: 2,
    ResumeClaimType.SKILL: 3, ResumeClaimType.TOOL: 3,
}


def _related_theme(statement: str, themes: Sequence[str]) -> str | None:
    tokens = words(statement)
    for theme in themes:
        if not words(theme).isdisjoint(tokens):
            return theme
    return None


def build_pressure_test(
    role: RoleAnalysisResponse,
    resume: ResumeAnalysisResponse | None,
    *,
    has_resume_document: bool,
    responses: Mapping[UUID, Readiness] | None = None,
    stories_by_claim: Mapping[UUID, UUID] | None = None,
) -> PressureTest:
    base = {"role_profile_id": role.id, "target_role": role.target_role}
    if not has_resume_document:
        return PressureTest(state="NO_RESUME", **base)
    if resume is None or resume.status == "PROCESSING":
        return PressureTest(state="READING", **base)
    if resume.status == "FAILED" or not resume.claims:
        return PressureTest(state="UNREADABLE", **base)

    responses = responses or {}
    stories_by_claim = stories_by_claim or {}
    themes = [item.name for item in sorted(role.competencies, key=lambda c: c.importance_weight, reverse=True)[:8]]

    seen: set[str] = set()
    candidates: list[tuple[tuple[int, int, int], PressureItem]] = []
    for claim in resume.claims:
        statement = statement_of(claim)
        key = " ".join(statement.casefold().split())
        if key in seen:
            continue
        seen.add(key)
        theme = _related_theme(statement, themes)
        item = PressureItem(
            claim_id=claim.id,
            statement=statement,
            where=claim.source_reference,
            related_theme=theme,
            questions=questions_for(claim),
            readiness=responses.get(claim.id),
            story_id=stories_by_claim.get(claim.id),
        )
        order = (0 if theme else 1, _PRIORITY.get(claim.verification_priority, 2), _TYPE_ORDER.get(claim.claim_type, 4))
        candidates.append((order, item))
    candidates.sort(key=lambda pair: pair[0])
    return PressureTest(state="READY", items=[item for _, item in candidates[:MAX_ITEMS]], **base)


# ------------------------------------------------------------------ answer checks


class AnswerCheckRequest(PressureModel):
    kind: QuestionKind
    answer: str = Field(min_length=1, max_length=6000)


class AnswerCheck(PressureModel):
    key: str
    present: bool
    text: str


class AnswerChecks(PressureModel):
    checks: list[AnswerCheck]
    follow_up: str | None = None


_NUMBER = re.compile(r"\d|\b(percent|half|double|twice|thousand|lakh|crore|million|hundred)\b", re.IGNORECASE)
_I = re.compile(r"\b(i|i'm|i've|i'd|my|me)\b", re.IGNORECASE)
_WE = re.compile(r"\b(we|our|us|the team)\b", re.IGNORECASE)
_RESULT = re.compile(r"\b(result|so that|which meant|led to|reduced|increased|improved|saved|cut|grew|changed|after)\b", re.IGNORECASE)
_REASON = re.compile(r"\b(because|so that|instead|rather than|chose|decided|trade-?off|option|alternative)\b", re.IGNORECASE)


def check_answer(request: AnswerCheckRequest) -> AnswerChecks:
    """Which of the things this kind of question looks for appear in the answer."""
    answer = request.answer
    singular = len(_I.findall(answer))
    plural = len(_WE.findall(answer))
    found = {
        "number": bool(_NUMBER.search(answer)),
        "own_part": singular > 0 and singular >= plural,
        "result": bool(_RESULT.search(answer)),
        "reason": bool(_REASON.search(answer)),
        "detail": len(answer.split()) >= 40,
    }
    wanted = {
        QuestionKind.OWNERSHIP: ("own_part", "detail"),
        QuestionKind.MEASURE: ("number", "result"),
        QuestionKind.SOURCE_OF_NUMBER: ("number", "detail"),
        QuestionKind.OUTCOME: ("result", "number"),
        QuestionKind.DECISION: ("result", "reason"),
        QuestionKind.ALTERNATIVE: ("reason", "detail"),
        QuestionKind.USAGE: ("own_part", "reason", "detail"),
    }[request.kind]
    labels = {
        "number": ("You gave a number or size.", "We didn't hear a number or size."),
        "own_part": ("You said what you did yourself.", "Most of this describes what “we” did."),
        "result": ("You said what happened as a result.", "We didn't hear what changed afterwards."),
        "reason": ("You explained why.", "We didn't hear why you chose this."),
        "detail": ("You gave enough detail to follow.", "This was brief. One or two more specifics would help."),
    }
    checks = [
        AnswerCheck(key=key, present=found[key], text=labels[key][0] if found[key] else labels[key][1])
        for key in wanted
    ]
    follow_ups = {
        "number": "Roughly how big was the change? A range is fine.",
        "own_part": "What did you personally do, as opposed to the team?",
        "result": "What was different after this work?",
        "reason": "Why that approach rather than another one?",
        "detail": "Can you give one concrete detail that only you would know?",
    }
    missing = next((check.key for check in checks if not check.present), None)
    return AnswerChecks(checks=checks, follow_up=follow_ups[missing] if missing else None)
