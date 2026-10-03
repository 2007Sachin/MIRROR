"""The night-before brief and debrief follow-ups. Pure and deterministic: no I/O, no model.

The brief only selects and orders what the Interview Map, the resume follow-ups and the
latest review already say. Follow-ups say what to prepare next; they never say why an
interview went the way it did.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

from .dashboard_summary import LatestReview
from .interview_event_models import (
    BriefClaim,
    BriefFocus,
    BriefTheme,
    DebriefFollowUp,
    FollowUpAction,
    InterviewBrief,
    InterviewEvent,
    InterviewEventRecord,
    Timing,
)
from .interview_map import (
    DEFAULT_MATCHER,
    Coverage,
    InterviewMap,
    InterviewTheme,
    MapState,
    MatchStrength,
    _question_for,
)
from .pressure_test import PressureTest, Readiness
from .role_models import CompetencyCategory
from .story_models import StoryCompleteness

MAX_BRIEF_THEMES = 3
MAX_RECHECK = 3
SOON_WINDOW = timedelta(hours=48)

LIMITATION_SOURCES = "This brief is built only from the role brief and your own material. Mirror has not researched the company."
LIMITATION_NOT_PREDICTION = "Questions worth preparing for are not a prediction of what you will be asked."
LIMITATION_ROLE_NOT_READY = "We're still getting to know this role, so themes and questions to prepare will appear once that's done."

# Questions a person could ask the interviewer. Fixed wording, keyed only by the kind of
# theme the role emphasises, so nothing here claims to know anything about the company.
_ASK_BY_CATEGORY: dict[CompetencyCategory, str] = {
    CompetencyCategory.ANALYTICAL: "How does the team decide which numbers matter most?",
    CompetencyCategory.TECHNICAL: "What does a typical technical problem on this team look like?",
    CompetencyCategory.TOOL: "Which tools does the team rely on day to day, and how did it choose them?",
    CompetencyCategory.DOMAIN: "What is the part of this area that new people usually take longest to learn?",
    CompetencyCategory.BEHAVIOURAL: "How does the team work through disagreements about priorities?",
    CompetencyCategory.COMMUNICATION: "Who would I work with most closely outside the team, and how do you share updates?",
}
_ASK_GENERAL = (
    "What would a great first three months in this role look like?",
    "What is the team working on right now that this role would help with?",
    "How will I get feedback, and how often?",
)
MIN_ASK, MAX_ASK = 3, 5


def timing(scheduled_for: datetime, now: datetime) -> Timing:
    if scheduled_for < now:
        return Timing.PAST
    if scheduled_for <= now + SOON_WINDOW:
        return Timing.SOON
    return Timing.UPCOMING


def event_view(record: InterviewEventRecord, now: datetime) -> InterviewEvent:
    return InterviewEvent(
        **record.model_dump(exclude={"user_id"}),
        timing=timing(record.scheduled_for, now),
    )


def _support(theme: InterviewTheme) -> tuple[str | None, UUID | None]:
    if theme.coverage == Coverage.PREPARED:
        story = next((match for match in theme.matches if match.kind == "STORY"), None)
        if story is not None:
            return story.label, story.story_id
    if theme.coverage in (Coverage.PREPARED, Coverage.EXPERIENCE) and theme.matches:
        return theme.matches[0].text, None
    return None, None


def brief_themes(interview_map: InterviewMap) -> list[BriefTheme]:
    """The highest-importance themes (the map keeps them in importance order)."""
    prompts = {question.theme_key: question.text for question in interview_map.questions}
    themes: list[BriefTheme] = []
    for theme in interview_map.themes[:MAX_BRIEF_THEMES]:
        prompt = prompts.get(theme.key)
        if prompt is None:
            fallback = _question_for(theme, set())
            prompt = fallback.text if fallback else f"Tell me about a time you used {theme.name.lower()}."
        support, story_id = _support(theme)
        themes.append(
            BriefTheme(key=theme.key, label=theme.name, coverage=theme.coverage, support=support, story_id=story_id, prompt=prompt)
        )
    return themes


def recheck_claims(pressure: PressureTest | None) -> list[BriefClaim]:
    """Statements marked as needing preparation first, then never-marked ones, in pressure-test order."""
    if pressure is None or pressure.state != "READY":
        return []
    rank = {Readiness.NEEDS_PREPARATION: 0, None: 1}
    picked = sorted(
        (item for item in pressure.items if item.readiness in rank and item.questions),
        key=lambda item: rank[item.readiness],  # stable: keeps pressure-test order within a rank
    )
    return [
        BriefClaim(claim_id=item.claim_id, statement=item.statement, readiness=item.readiness, question=item.questions[0].text)
        for item in picked[:MAX_RECHECK]
    ]


def brief_focus(review: LatestReview | None, role_profile_id: UUID) -> BriefFocus | None:
    if review is None or review.role_profile_id not in (None, role_profile_id):
        return None
    return BriefFocus(title=review.next_step.title, body=review.next_step.body, session_id=review.session_id)


def questions_to_ask(interview_map: InterviewMap) -> list[str]:
    """Up to three keyed to the kinds of theme the role emphasises, topped up with general ones."""
    keyed: list[str] = []
    for theme in interview_map.themes:
        text = _ASK_BY_CATEGORY.get(theme.category)
        if text and text not in keyed:
            keyed.append(text)
    keyed = keyed[:MIN_ASK]
    return keyed + list(_ASK_GENERAL[: MAX_ASK - len(keyed)])


def build_brief(
    event: InterviewEventRecord,
    interview_map: InterviewMap,
    pressure: PressureTest | None,
    review: LatestReview | None,
    *,
    now: datetime,
) -> InterviewBrief:
    ready = interview_map.state == MapState.READY
    limitations = [LIMITATION_SOURCES, LIMITATION_NOT_PREDICTION]
    if not ready:
        limitations.append(LIMITATION_ROLE_NOT_READY)
    return InterviewBrief(
        event=event_view(event, now),
        role_title=interview_map.target_role,
        state=interview_map.state,
        themes=brief_themes(interview_map) if ready else [],
        recheck=recheck_claims(pressure) if ready else [],
        focus=brief_focus(review, event.role_profile_id),
        questions_to_ask=questions_to_ask(interview_map) if ready else list(_ASK_GENERAL),
        limitations=limitations,
    )


# ------------------------------------------------------------------ debrief follow-ups


def best_theme(question: str, themes: Sequence[InterviewTheme]) -> InterviewTheme | None:
    """The map theme the question speaks to most, by the map's own word overlap."""
    best: InterviewTheme | None = None
    for theme in themes:
        strength = DEFAULT_MATCHER.strength(theme.name, question)
        if strength == MatchStrength.USEFUL:
            return theme
        if strength == MatchStrength.WEAK and best is None:
            best = theme
    return best


def follow_ups(
    questions: Sequence[str],
    interview_map: InterviewMap,
    story_completeness: Mapping[UUID, StoryCompleteness],
) -> list[DebriefFollowUp]:
    themes = interview_map.themes if interview_map.state == MapState.READY else []
    result: list[DebriefFollowUp] = []
    for question in questions:
        theme = best_theme(question, themes)
        if theme is None:
            result.append(DebriefFollowUp(question=question, action=FollowUpAction.NONE))
            continue
        action, href = FollowUpAction.NONE, None
        if theme.coverage in (Coverage.MISSING, Coverage.MENTIONED):
            action, href = FollowUpAction.ADD_STORY, "/stories/new?" + urlencode({"guided": "1", "role": str(interview_map.role_profile_id), "theme": theme.name})
        elif theme.coverage == Coverage.PREPARED:
            story_id = next((match.story_id for match in theme.matches if match.kind == "STORY" and match.story_id), None)
            if story_id is not None and story_completeness.get(story_id) not in (None, StoryCompleteness.READY):
                action, href = FollowUpAction.STRENGTHEN_STORY, f"/stories/{story_id}"
        result.append(
            DebriefFollowUp(
                question=question, theme_key=theme.key, theme_label=theme.name, coverage=theme.coverage,
                action=action, action_href=href,
            )
        )
    return result
