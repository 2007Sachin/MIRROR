"""Practice modes: full interview, focused practice and quick drill.

All three run on the same session, planner record, interview engine and interviewer.
The only differences are decided here, deterministically:

- time budget (the engine's existing budgets, set per session at creation)
- the plan: a full interview is planned by the Planner agent as before; a focused
  practice or quick drill gets a short plan built from fixed questions for one area,
  personalised only with names already in the candidate's own role and resume data
- how many follow-ups each question allows (the interviewer enforces `max_probes`)

Nothing here invents experience: a question may name a project or a role theme only
when that name is already in the planning context.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from .planner_models import (
    DifficultyStart,
    InterviewObjective,
    InterviewPlan,
    InterviewPlannerInput,
    ObjectivePriority,
    PlanCoverageSummary,
)
from .schemas import Phase

PRACTICE_PLANNING_VERSION = "practice-plan-v1"
PRACTICE_PLANNER_MODEL = "deterministic"


class PracticeMode(StrEnum):
    FULL_INTERVIEW = "FULL_INTERVIEW"
    FOCUSED_PRACTICE = "FOCUSED_PRACTICE"
    QUICK_DRILL = "QUICK_DRILL"


class PracticeFocus(StrEnum):
    FULL = "full"
    STORY = "story"
    PROJECT = "project"
    DECISIONS = "decisions"
    IMPACT = "impact"
    DISAGREEMENT = "disagreement"
    FAILURE = "setback"
    ANALYTICS = "analytics"
    ROLE = "role"


@dataclass(frozen=True)
class ModeShape:
    questions: int
    follow_ups: int
    total_seconds: int


# The one place the size of each mode is decided.
MODE_SHAPE: dict[PracticeMode, ModeShape] = {
    PracticeMode.QUICK_DRILL: ModeShape(questions=3, follow_ups=1, total_seconds=5 * 60),
    PracticeMode.FOCUSED_PRACTICE: ModeShape(questions=4, follow_ups=2, total_seconds=9 * 60),
}


def budgets_for(mode: PracticeMode, *, full_total: int, full_phase: int) -> tuple[int, int]:
    """(total, per-phase) seconds. Short modes use one clock so no phase runs out early."""
    shape = MODE_SHAPE.get(mode)
    if shape is None:
        return full_total, full_phase
    return shape.total_seconds, shape.total_seconds


# ------------------------------------------------------------------ questions

# {project} and {theme} are filled only from the planning context; each template has a
# plain fallback used when that context is missing.
_QUESTIONS: dict[PracticeFocus, tuple[tuple[str, str], ...]] = {
    PracticeFocus.STORY: (
        ("Tell me about yourself, and what brings you to this {role} role.", "Tell me about yourself, and what brings you to this role."),
        ("What is one experience that best shows how you work?", "What is one experience that best shows how you work?"),
        ("Why this role, and why now?", "Why this role, and why now?"),
        ("What would the people you've worked with say you're best at?", "What would the people you've worked with say you're best at?"),
    ),
    PracticeFocus.PROJECT: (
        ("Walk me through {project} from start to finish.", "Walk me through a project you're proud of, from start to finish."),
        ("What was the hardest part of {project}, and how did you handle it?", "What was the hardest part of that project, and how did you handle it?"),
        ("Which part of {project} was yours, and which was the team's?", "Which part of that project was yours, and which was the team's?"),
        ("If you started {project} again, what would you change?", "If you started that project again, what would you change?"),
    ),
    PracticeFocus.DECISIONS: (
        ("Tell me about a decision you made where there was more than one reasonable option.", ""),
        ("In {project}, what was one choice you made, and what did you weigh up?", "Tell me about one choice you made on a recent project, and what you weighed up."),
        ("Tell me about a decision you made without all the information you wanted.", ""),
        ("What is a decision you would make differently now, and why?", ""),
    ),
    PracticeFocus.IMPACT: (
        ("Tell me about a piece of work where you can say what changed because of it.", ""),
        ("In {project}, what was different after your work? How did you know?", "Pick one piece of your work. What was different afterwards, and how did you know?"),
        ("Tell me about a result you're proud of. How much of it was down to you?", ""),
        ("Tell me about a time the result was smaller than you hoped. What happened?", ""),
    ),
    PracticeFocus.DISAGREEMENT: (
        ("Tell me about a time you disagreed with someone about how to approach the work.", ""),
        ("Tell me about a time you had to persuade someone who saw things differently.", ""),
        ("Tell me about a time a stakeholder wanted something you thought was a mistake.", ""),
        ("What do you do when you and your manager disagree on priorities?", ""),
    ),
    PracticeFocus.FAILURE: (
        ("Tell me about something you tried that didn't work.", ""),
        ("Tell me about a mistake you made at work and what you did next.", ""),
        ("What is the most useful piece of feedback you've received, and what did you do with it?", ""),
        ("Tell me about a time you had to change course partway through.", ""),
    ),
    PracticeFocus.ANALYTICS: (
        ("Tell me about a decision you made using data.", ""),
        ("Tell me about a time the numbers told you something you didn't expect.", ""),
        ("How did you check that the data you relied on in {project} was right?", "How do you check that the data you rely on is right?"),
        ("Tell me about a time you had to explain a finding to someone without a data background.", ""),
    ),
    PracticeFocus.ROLE: (
        ("{theme} matters a lot in this role. Tell me about a time you relied on it.", "Tell me about the part of your experience that fits this role best."),
        ("What would you want to learn in your first month, given how much this role relies on {theme}?", "What would you want to learn in your first month in this role?"),
        ("Tell me about a situation where {theme} was harder than it looked.", "Tell me about a situation in your work that was harder than it looked."),
        ("How would you explain your experience with {theme} to someone new to it?", "How would you explain your most relevant experience to someone new to it?"),
    ),
}

_AREA_NAME: dict[PracticeFocus, str] = {
    PracticeFocus.STORY: "telling your story",
    PracticeFocus.PROJECT: "explaining a project",
    PracticeFocus.DECISIONS: "explaining decisions",
    PracticeFocus.IMPACT: "showing impact",
    PracticeFocus.DISAGREEMENT: "handling disagreement",
    PracticeFocus.FAILURE: "learning from what didn't work",
    PracticeFocus.ANALYTICS: "analytical thinking",
    PracticeFocus.ROLE: "a role-specific theme",
}

_SIGNALS: dict[PracticeFocus, list[str]] = {
    PracticeFocus.STORY: ["clear through-line", "relevance to the role"],
    PracticeFocus.PROJECT: ["personal ownership", "sequence of work", "outcome"],
    PracticeFocus.DECISIONS: ["options considered", "reasoning", "trade-offs"],
    PracticeFocus.IMPACT: ["what changed", "size of the change", "personal contribution"],
    PracticeFocus.DISAGREEMENT: ["the other view", "how it was resolved", "what was learned"],
    PracticeFocus.FAILURE: ["honest account", "what was done next", "what was learned"],
    PracticeFocus.ANALYTICS: ["data used", "how it was checked", "decision it informed"],
    PracticeFocus.ROLE: ["relevant example", "depth of understanding"],
}

_PHASES = (Phase.INTRO, Phase.ROLE_CORE, Phase.DEEP_DIVE, Phase.BEHAVIOURAL)


def _fill(template: str, fallback: str, *, role: str, project: str | None, theme: str | None) -> str:
    needs_project = "{project}" in template
    needs_theme = "{theme}" in template
    if (needs_project and not project) or (needs_theme and not theme):
        return fallback or template
    text = template.format(role=role, project=project or "", theme=theme or "")
    return text[:1].upper() + text[1:]


# Practising stories the candidate chose. Each story gets an opening question first; the
# remaining questions go deeper into them in turn. Only the story's title is used here, from
# the exact version pinned for this session.
_CHOSEN_STORY_QUESTIONS: tuple[str, ...] = (
    "Tell me about “{story}”. What was going on, and what did you do?",
    "In “{story}”, which part was yours, and why did you take that approach?",
    "What changed because of your work on “{story}”, and how do you know?",
    "Looking back on “{story}”, what would you do differently?",
)


def chosen_story_questions(titles: Sequence[str], count: int) -> list[str]:
    """Question i is about story i mod n: every chosen story is asked about, in order."""
    if not titles:
        return []
    return [
        _CHOSEN_STORY_QUESTIONS[index // len(titles)].format(story=titles[index % len(titles)])
        for index in range(min(count, len(titles) * len(_CHOSEN_STORY_QUESTIONS)))
    ]


def practice_questions(
    focus: PracticeFocus,
    count: int,
    source: InterviewPlannerInput,
    theme: str | None = None,
    stories: Sequence[str] = (),
) -> list[str]:
    """The primary questions for one area, personalised only from the planning context."""
    if focus == PracticeFocus.FULL:
        raise ValueError("a full interview is planned by the Planner agent")
    if focus == PracticeFocus.STORY and stories:
        return chosen_story_questions(stories, count)
    project = source.projects[0].name if source.projects else None
    if focus == PracticeFocus.ROLE and not theme:
        top = sorted(source.role_competencies, key=lambda item: item.importance_weight, reverse=True)
        theme = top[0].name if top else None
    questions: list[str] = []
    for template, fallback in _QUESTIONS[focus]:
        text = _fill(template, fallback, role=source.target_role, project=project, theme=theme)
        if text not in questions:
            questions.append(text)
        if len(questions) == count:
            break
    return questions


STORY_OBJECTIVE = re.compile(r"^story-([1-4])-([1-9])$")


def _objective_id(focus: PracticeFocus, index: int, chosen: int) -> str:
    """A question about chosen story p is "story-p-n": the id is stored on every turn of that
    question, so Review can tell exactly which chosen story an answer was about."""
    if focus == PracticeFocus.STORY and chosen:
        return f"story-{index % chosen + 1}-{index + 1}"
    return f"practice-{focus.value}-{index + 1}"


def story_position(objective_id: str | None) -> int | None:
    """The chosen-story position an objective asked about, or None when it asked about none."""
    match = STORY_OBJECTIVE.match(objective_id or "")
    return int(match.group(1)) if match else None


def build_practice_plan(
    mode: PracticeMode,
    focus: PracticeFocus,
    source: InterviewPlannerInput,
    *,
    theme: str | None = None,
    stories: Sequence[str] = (),
) -> InterviewPlan:
    shape = MODE_SHAPE[mode]
    questions = practice_questions(focus, shape.questions, source, theme, stories)
    per_question = max(30, shape.total_seconds // len(questions))
    area = _AREA_NAME[focus] if focus != PracticeFocus.ROLE or not theme else theme.lower()
    matching_competencies = [
        item.id for item in source.role_competencies if theme and item.name.casefold() == theme.casefold()
    ]
    objectives = [
        InterviewObjective(
            objective_id=_objective_id(focus, index, len(stories)),
            phase=_PHASES[min(index, len(_PHASES) - 1)],
            objective=f"Practise {area}.",
            priority=ObjectivePriority.HIGH,
            target_competency_ids=matching_competencies,
            initial_question=question,
            question_intent=f"Give the candidate a chance to practise {area}.",
            expected_signal=_SIGNALS[focus],
            time_budget_seconds=per_question,
            max_probes=shape.follow_ups,
            difficulty_start=DifficultyStart.BASIC,
            completion_conditions=["Candidate has answered the question and any follow-up"],
        )
        for index, question in enumerate(questions)
    ]
    return InterviewPlan(
        session_id=source.session_id,
        target_role=source.target_role,
        total_time_budget_seconds=shape.total_seconds,
        planning_version=PRACTICE_PLANNING_VERSION,
        objectives=objectives,
        coverage_summary=PlanCoverageSummary(
            role_competency_coverage=matching_competencies,
            estimated_duration_seconds=shape.total_seconds,
        ),
        created_at=datetime.now(UTC),
    )
