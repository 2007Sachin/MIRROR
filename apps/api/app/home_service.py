"""Home: what should this person do now?

One response, decided on the server, so the page renders it and never decides. Nothing
here recalculates what other parts already own: practice progress (`role_progress`),
what to practise (`practice_recommendation`), the interview map, story readiness and
the session lifecycle. This module only picks which one comes first.

Which role Home is about. A person's role profiles are their roles (`families`, one per
role name). The page may ask for one by id; an id that is not this person's is refused.
With no request, Home is about the active role (`profiles.current_role_profile_id`, else
the onboarding role) when it is still one of theirs, else the role of the newest practice,
else the newest role. This is a view choice; it changes nothing stored.

State precedence for the selected role, first match wins:
 1. NO_ROLE            no role set up
 2. ACTIVE_PRACTICE    an unfinished practice for this role
 3. REVIEW_PROCESSING / REVIEW_FAILED   the newest practice for this role is still being reviewed
 4. REVIEW_READY       the newest practice's review is ready and finished within REVIEW_FRESH
 5. FIRST_PRACTICE     no finished practice for this role
 6. EARLY_BASELINE     exactly one
 7. RECOMMENDED_NEXT   two or more, and a practice is recommended
 8. RETURNING          two or more, nothing to recommend
An unfinished practice for another role never hides behind the selected role: it comes
back as `other_active`, next to whichever state the selected role is in.
Likewise a recorded interview within the next 48 hours (timing SOON), for any role, comes
back as `upcoming_interview`; it never changes the state.

Review "ready" has no read-tracking, so it stays the headline for REVIEW_FRESH after a
practice finishes, then gives way to the next step.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .dashboard_models import DashboardDiagnostic
from .dashboard_repository import DashboardUnavailable
from .document_repository import DocumentUnavailable
from .interview_brief import timing
from .interview_event_models import RoundKind, Timing
from .interview_event_repository import InterviewEventsUnavailable
from .interview_map import Coverage, MapState
from .practice_modes import MODE_SHAPE, PracticeMode
from .practice_recommendation import PracticeRecommendation
from .resume_repository import ResumeAnalysisUnavailable
from .role_models import RoleProfileRead
from .role_repository import RoleAnalysisUnavailable
from .role_progress import DIMENSION_FOCUS, Insight, RoleProgress, Stage
from .schemas import SessionStatus
from .story_models import StoryCompleteness, story_completeness
from .story_repository import StoriesUnavailable

logger = logging.getLogger("mirror.home")
REVIEW_FRESH = timedelta(hours=24)
# What a summary part may fail with and still leave Home honest: it says so. Anything else is a bug and surfaces.
_PART_UNAVAILABLE = (RoleAnalysisUnavailable, DocumentUnavailable, StoriesUnavailable, DashboardUnavailable, ResumeAnalysisUnavailable)
ACTIVITY_LIMIT = 3
_REVIEW_KINDS = ("REVIEW_READY", "REVIEW_PROCESSING", "REVIEW_FAILED")
_FOCUS_DIMENSION = {focus: key for key, focus in DIMENSION_FOCUS.items()}


class HomeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HomeState(StrEnum):
    NO_ROLE = "NO_ROLE"
    ACTIVE_PRACTICE = "ACTIVE_PRACTICE"
    REVIEW_PROCESSING = "REVIEW_PROCESSING"
    REVIEW_FAILED = "REVIEW_FAILED"
    REVIEW_READY = "REVIEW_READY"
    FIRST_PRACTICE = "FIRST_PRACTICE"
    EARLY_BASELINE = "EARLY_BASELINE"
    RECOMMENDED_NEXT = "RECOMMENDED_NEXT"
    RETURNING = "RETURNING"


class SessionKind(StrEnum):
    ACTIVE = "ACTIVE"
    READY = "READY"
    REVIEW_READY = "REVIEW_READY"
    REVIEW_PROCESSING = "REVIEW_PROCESSING"
    REVIEW_FAILED = "REVIEW_FAILED"
    OTHER = "OTHER"


class HomeRole(HomeModel):
    role_profile_id: UUID
    target_role: str


class ActivePractice(HomeModel):
    session_id: UUID
    role_profile_id: UUID | None = None
    target_role: str
    kind: SessionKind  # ACTIVE (started) or READY (created, not begun)
    practice_mode: str
    practice_focus: str | None = None
    practice_theme: str | None = None
    question_number: int  # the primary question it is on; 0 before the first
    question_total: int | None = None  # known for a focused practice and a quick drill only
    last_active_at: datetime


class ReviewCard(HomeModel):
    session_id: UUID
    kind: SessionKind  # REVIEW_READY, REVIEW_PROCESSING or REVIEW_FAILED
    target_role: str
    practice_mode: str
    practice_focus: str | None = None
    practice_theme: str | None = None
    question_count: int | None = None
    finished_at: datetime


class NextStep(HomeModel):
    role_profile_id: UUID
    target_role: str
    mode: str
    focus: str
    theme: str | None = None
    reason: str
    dimension: str | None = None  # the progress area this practises, for "see why"


class Highlight(HomeModel):
    dimension: str
    state: str
    note: str | None = None


class ProgressPart(HomeModel):
    stage: Stage
    practice_count: int
    last_practised_at: datetime | None = None
    insights: list[Insight] = []
    highlights: list[Highlight] = []  # what one practice showed, used only for the first baseline


class MapPart(HomeModel):
    state: str  # READY, PREPARING or UNAVAILABLE
    without_example: int = 0  # role areas with nothing of yours to show for them yet


class StoriesPart(HomeModel):
    state: str  # READY or UNAVAILABLE
    ready: int = 0
    developing: int = 0


class ActivityItem(HomeModel):
    kind: str  # PRACTICE or STORY
    at: datetime
    session_id: UUID | None = None
    story_id: UUID | None = None
    title: str
    session_kind: SessionKind | None = None
    practice_mode: str | None = None
    practice_focus: str | None = None
    practice_theme: str | None = None


class UpcomingInterview(HomeModel):
    event_id: UUID
    role_profile_id: UUID
    target_role: str
    scheduled_for: datetime
    round_kind: RoundKind
    company_label: str | None = None


class HomeResponse(HomeModel):
    state: HomeState
    roles: list[HomeRole]
    selected: HomeRole | None = None
    active: ActivePractice | None = None
    other_active: ActivePractice | None = None
    review: ReviewCard | None = None
    next_step: NextStep | None = None
    progress: ProgressPart | None = None
    map: MapPart | None = None
    stories: StoriesPart | None = None
    activity: list[ActivityItem] = []
    upcoming_interview: UpcomingInterview | None = None


# ----------------------------------------------------------------------------- pure decisions


def session_kind(session: DashboardDiagnostic) -> SessionKind:
    """Which stage a session is really at. A review is ready only when its result exists."""
    if session.diagnostic_available:
        return SessionKind.REVIEW_READY
    status = session.interview_status
    if status == SessionStatus.ACTIVE:
        return SessionKind.ACTIVE
    if status == SessionStatus.READY:
        return SessionKind.READY
    if status in (SessionStatus.COMPLETED, SessionStatus.ASSESSING):
        failed = session.assessment is not None and session.assessment.status.value == "FAILED"
        return SessionKind.REVIEW_FAILED if failed else SessionKind.REVIEW_PROCESSING
    return SessionKind.OTHER


def in_role(session: DashboardDiagnostic, family: frozenset[UUID], role_name: str) -> bool:
    """Bound to this role, or (for a practice from before roles were bound) named the same."""
    if session.role_profile_id is not None:
        return session.role_profile_id in family
    return session.target_role.casefold().strip() == role_name.casefold().strip()


def _finished_at(session: DashboardDiagnostic) -> datetime:
    return session.completed_at or session.updated_at


def preferred_role(
    families: Sequence[tuple[RoleProfileRead, frozenset[UUID]]], preferred: Sequence[UUID | None]
) -> tuple[RoleProfileRead, frozenset[UUID]] | None:
    """The first stored preference that is still one of these roles (any profile of the role counts)."""
    for wanted in preferred:
        for entry in families:
            if wanted is not None and wanted in entry[1]:
                return entry
    return None


def choose_role(
    families: Sequence[tuple[RoleProfileRead, frozenset[UUID]]], requested: UUID | None, sessions: Sequence[DashboardDiagnostic]
) -> tuple[RoleProfileRead, frozenset[UUID]] | None:
    """The role Home is about. An id that is not one of these roles is refused, never guessed."""
    if not families:
        return None
    if requested is not None:
        for entry in families:
            if requested in entry[1]:
                return entry
        raise LookupError("not one of this person's roles")
    for session in sessions:  # newest first
        for entry in families:
            if session.role_profile_id is not None and session.role_profile_id in entry[1]:
                return entry
    return families[0]


def active_practice(session: DashboardDiagnostic) -> ActivePractice:
    kind = session_kind(session)
    try:
        shape = MODE_SHAPE.get(PracticeMode(session.practice_mode))
    except ValueError:
        shape = None
    return ActivePractice(
        session_id=session.id,
        role_profile_id=session.role_profile_id,
        target_role=session.target_role,
        kind=kind,
        practice_mode=session.practice_mode,
        practice_focus=session.practice_focus,
        practice_theme=session.practice_theme,
        question_number=session.total_questions,
        question_total=shape.questions if shape else None,
        last_active_at=session.updated_at,
    )


def review_card(session: DashboardDiagnostic) -> ReviewCard:
    return ReviewCard(
        session_id=session.id,
        kind=session_kind(session),
        target_role=session.target_role,
        practice_mode=session.practice_mode,
        practice_focus=session.practice_focus,
        practice_theme=session.practice_theme,
        question_count=session.total_questions or None,
        finished_at=_finished_at(session),
    )


def next_step(recommendation: PracticeRecommendation | None) -> NextStep | None:
    if recommendation is None:
        return None
    return NextStep(
        role_profile_id=recommendation.role_profile_id,
        target_role=recommendation.target_role,
        mode=recommendation.mode.value,
        focus=recommendation.focus.value,
        theme=recommendation.theme,
        reason=recommendation.reason,
        dimension=_FOCUS_DIMENSION.get(recommendation.focus.value),
    )


def progress_part(progress: RoleProgress) -> ProgressPart:
    seen = [
        Highlight(dimension=item.key, state=item.state.value, note=item.note)
        for item in progress.dimensions
        if item.state.value != "NOT_EXPLORED"
    ]
    return ProgressPart(
        stage=progress.stage,
        practice_count=progress.practice_count,
        last_practised_at=progress.last_practised_at,
        insights=progress.insights,
        highlights=seen[:3],
    )


def decide(
    *,
    active: ActivePractice | None,
    newest: DashboardDiagnostic | None,
    practice_count: int,
    has_next_step: bool,
    now: datetime,
) -> HomeState:
    """The one place Home's dominant action is chosen. Same inputs, same answer."""
    if active is not None:
        return HomeState.ACTIVE_PRACTICE
    if newest is not None:
        kind = session_kind(newest)
        if kind == SessionKind.REVIEW_PROCESSING:
            return HomeState.REVIEW_PROCESSING
        if kind == SessionKind.REVIEW_FAILED:
            return HomeState.REVIEW_FAILED
        if kind == SessionKind.REVIEW_READY and now - _finished_at(newest) <= REVIEW_FRESH:
            return HomeState.REVIEW_READY
    if practice_count == 0:
        return HomeState.FIRST_PRACTICE
    if practice_count == 1:
        return HomeState.EARLY_BASELINE
    return HomeState.RECOMMENDED_NEXT if has_next_step else HomeState.RETURNING


def activity_items(role_sessions: Sequence[DashboardDiagnostic], stories: Sequence[Any]) -> list[ActivityItem]:
    """Recent preparation for this role, plus edits to stories (stories belong to the person, not a role)."""
    items: list[ActivityItem] = []
    for session in role_sessions:
        kind = session_kind(session)
        if kind in (SessionKind.OTHER, SessionKind.READY):
            continue
        items.append(
            ActivityItem(
                kind="PRACTICE",
                at=_finished_at(session) if kind != SessionKind.ACTIVE else session.updated_at,
                session_id=session.id,
                title=session.target_role,
                session_kind=kind,
                practice_mode=session.practice_mode,
                practice_focus=session.practice_focus,
                practice_theme=session.practice_theme,
            )
        )
    for story in stories:
        items.append(ActivityItem(kind="STORY", at=story.updated_at, story_id=story.id, title=story.title))
    items.sort(key=lambda item: item.at, reverse=True)
    return items[:ACTIVITY_LIMIT]


# ----------------------------------------------------------------------------- service


class HomeService:
    """Owner-scoped throughout: every read takes the signed-in user's id."""

    def __init__(
        self,
        roles: Any,
        dashboard: Any,
        progress: Any,
        readiness: Any,
        stories: Any,
        interviews: Any = None,
        active_role: Callable[[UUID], Awaitable[Sequence[UUID | None]]] | None = None,
    ) -> None:
        self._roles = roles
        self._dashboard = dashboard
        self._progress = progress
        self._readiness = readiness
        self._stories = stories
        self._interviews = interviews
        self._active_role = active_role  # stored role ids, most preferred first

    async def home(self, user_id: UUID, requested_role: UUID | None = None, *, now: datetime | None = None) -> HomeResponse:
        from .role_service import RoleProfileNotFoundForUser

        now = now or datetime.now(UTC)
        families, sessions, preferred = await asyncio.gather(
            self._roles.families(user_id), self._dashboard.sessions(user_id), self._preference(user_id, requested_role)
        )
        roles = [HomeRole(role_profile_id=profile.id, target_role=profile.target_role) for profile, _ in families]
        try:
            chosen = preferred_role(families, preferred) or choose_role(families, requested_role, sessions)
        except LookupError as exc:
            raise RoleProfileNotFoundForUser from exc
        if chosen is None:
            return HomeResponse(state=HomeState.NO_ROLE, roles=roles)

        profile, family = chosen
        role_sessions = [item for item in sessions if in_role(item, family, profile.target_role)]
        # A practice from before roles were bound can still be an unfinished one, so it is not
        # hidden. It never speaks for the review or the activity, which Progress cannot count.
        bound = [item for item in role_sessions if item.role_profile_id is not None]
        newest = next((item for item in bound if session_kind(item) in _REVIEW_KINDS), None)
        # A practice already begun always comes first. One created but never begun does not hide
        # a review that finished after it.
        active = next(
            (
                item for item in role_sessions
                if session_kind(item) == SessionKind.ACTIVE
                or (session_kind(item) == SessionKind.READY and (newest is None or item.updated_at > _finished_at(newest)))
            ),
            None,
        )
        others = [item for item in sessions if not in_role(item, family, profile.target_role)]
        elsewhere = next((item for item in others if session_kind(item) in (SessionKind.ACTIVE, SessionKind.READY)), None)

        progress, extras, stories, upcoming = await asyncio.gather(
            self._progress.summary_from(profile, family, sessions, user_id),
            self._map_and_step(profile.id, user_id),
            self._story_counts(user_id),
            self._upcoming_interview(user_id, families, now),
        )
        map_part, recommendation = extras
        step = next_step(recommendation)
        state = decide(
            active=active_practice(active) if active else None,
            newest=newest,
            practice_count=progress.practice_count,
            has_next_step=step is not None,
            now=now,
        )
        story_rows, story_part = stories
        review = None
        if newest is not None and state in (HomeState.REVIEW_READY, HomeState.REVIEW_PROCESSING, HomeState.REVIEW_FAILED):
            review = review_card(newest)
        return HomeResponse(
            state=state,
            roles=roles,
            selected=HomeRole(role_profile_id=profile.id, target_role=profile.target_role),
            active=active_practice(active) if active else None,
            other_active=active_practice(elsewhere) if elsewhere else None,
            review=review,
            next_step=step,
            progress=progress_part(progress),
            map=map_part,
            stories=story_part,
            activity=activity_items(bound, story_rows),
            upcoming_interview=upcoming,
        )

    async def _preference(self, user_id: UUID, requested_role: UUID | None) -> Sequence[UUID | None]:
        """An explicit request always wins, so the stored choice is only read without one."""
        if requested_role is not None or self._active_role is None:
            return ()
        return await self._active_role(user_id)

    async def _map_and_step(self, role_profile_id: UUID, user_id: UUID) -> tuple[MapPart, PracticeRecommendation | None]:
        try:
            built, recommendation = await self._readiness.map_and_recommendation(role_profile_id, user_id)
        except _PART_UNAVAILABLE:  # a summary here: its outage is said plainly, not hidden and not zero
            logger.exception("home map summary unavailable", extra={"user_id": str(user_id), "role_profile_id": str(role_profile_id)})
            return MapPart(state="UNAVAILABLE"), None
        if built.state != MapState.READY:
            return MapPart(state="PREPARING" if built.state == MapState.ROLE_PREPARING else "UNAVAILABLE"), None
        missing = sum(1 for theme in built.themes if theme.coverage == Coverage.MISSING)
        return MapPart(state="READY", without_example=missing), recommendation

    async def _story_counts(self, user_id: UUID) -> tuple[list[Any], StoriesPart]:
        try:
            rows = await self._stories.list_for_user(user_id)
        except _PART_UNAVAILABLE:
            logger.exception("home story summary unavailable", extra={"user_id": str(user_id)})
            return [], StoriesPart(state="UNAVAILABLE")
        levels = [story_completeness(story)[0] for story in rows]
        ready = sum(1 for level in levels if level == StoryCompleteness.READY)
        return rows, StoriesPart(state="READY", ready=ready, developing=len(levels) - ready)

    async def _upcoming_interview(
        self, user_id: UUID, families: Sequence[tuple[RoleProfileRead, frozenset[UUID]]], now: datetime
    ) -> UpcomingInterview | None:
        """The soonest interview within the next 48 hours, across all this person's roles."""
        if self._interviews is None:
            return None
        try:
            events = await self._interviews.list_for_user(user_id)
        except (InterviewEventsUnavailable, *_PART_UNAVAILABLE):  # a nudge only: its outage hides it, never Home
            logger.exception("home upcoming interview unavailable", extra={"user_id": str(user_id)})
            return None
        names = {member: profile.target_role for profile, family in families for member in family}
        soon = sorted(
            (e for e in events if e.user_id == user_id and e.role_profile_id in names and timing(e.scheduled_for, now) == Timing.SOON),
            key=lambda e: e.scheduled_for,
        )
        if not soon:
            return None
        event = soon[0]
        return UpcomingInterview(
            event_id=event.id,
            role_profile_id=event.role_profile_id,
            target_role=names[event.role_profile_id],
            scheduled_for=event.scheduled_for,
            round_kind=event.round_kind,
            company_label=event.company_label,
        )
