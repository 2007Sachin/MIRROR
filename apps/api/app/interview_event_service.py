"""Interview events: owner checks, then the pure brief and follow-up builders."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from .interview_brief import build_brief, event_view, follow_ups
from .interview_event_models import (
    InterviewBrief,
    InterviewDebriefView,
    InterviewDebriefWrite,
    InterviewEvent,
    InterviewEventCreate,
    InterviewEventRecord,
    InterviewEventUpdate,
)
from .interview_event_repository import InterviewEventRepository
from .readiness_service import ReadinessService
from .story_models import story_completeness
from .story_repository import StoryRepository


class InterviewEventNotFound(Exception):
    """Unknown, or another person's."""


MAX_INTERVIEWS_PER_ROLE = 50


class TooManyInterviews(Exception):
    """A role already holds MAX_INTERVIEWS_PER_ROLE interviews."""


class DebriefNotFound(Exception):
    """No debrief written for this interview yet."""


class InterviewEventService:
    def __init__(
        self,
        events: InterviewEventRepository,
        readiness: ReadinessService,
        stories: StoryRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._events = events
        self._readiness = readiness
        self._stories = stories
        self._clock = clock

    async def _owned(self, event_id: UUID, user_id: UUID) -> InterviewEventRecord:
        record = await self._events.get(event_id, user_id)
        if record is None:
            raise InterviewEventNotFound
        return record

    async def list_for_role(self, role_profile_id: UUID, user_id: UUID) -> list[InterviewEvent]:
        await self._readiness.role(role_profile_id, user_id)  # raises for another person's role
        now = self._clock()
        return [event_view(row, now) for row in await self._events.list_for_role(user_id, role_profile_id)]

    async def create(self, role_profile_id: UUID, user_id: UUID, values: InterviewEventCreate) -> InterviewEvent:
        await self._readiness.role(role_profile_id, user_id)
        if len(await self._events.list_for_role(user_id, role_profile_id)) >= MAX_INTERVIEWS_PER_ROLE:
            raise TooManyInterviews
        return event_view(await self._events.create(user_id, role_profile_id, values), self._clock())

    async def update(self, event_id: UUID, user_id: UUID, values: InterviewEventUpdate) -> InterviewEvent:
        record = await self._events.update(event_id, user_id, values)
        if record is None:
            raise InterviewEventNotFound
        return event_view(record, self._clock())

    async def delete(self, event_id: UUID, user_id: UUID) -> None:
        if not await self._events.delete(event_id, user_id):
            raise InterviewEventNotFound

    async def brief(self, event_id: UUID, user_id: UUID) -> InterviewBrief:
        record = await self._owned(event_id, user_id)
        interview_map, review = await self._readiness._map_and_review(record.role_profile_id, user_id)
        pressure = await self._readiness.pressure_test(record.role_profile_id, user_id)
        return build_brief(record, interview_map, pressure, review, now=self._clock())

    async def _view(self, record: InterviewEventRecord, user_id: UUID, debrief) -> InterviewDebriefView:
        interview_map = await self._readiness.interview_map(record.role_profile_id, user_id)
        completeness = {story.id: story_completeness(story)[0] for story in await self._stories.list_for_user(user_id)}
        return InterviewDebriefView(debrief=debrief, follow_ups=follow_ups(debrief.questions_asked, interview_map, completeness))

    async def get_debrief(self, event_id: UUID, user_id: UUID) -> InterviewDebriefView:
        record = await self._owned(event_id, user_id)
        debrief = await self._events.get_debrief(event_id, user_id)
        if debrief is None:
            raise DebriefNotFound
        return await self._view(record, user_id, debrief)

    async def put_debrief(self, event_id: UUID, user_id: UUID, values: InterviewDebriefWrite) -> InterviewDebriefView:
        record = await self._owned(event_id, user_id)
        return await self._view(record, user_id, await self._events.put_debrief(event_id, user_id, values))
