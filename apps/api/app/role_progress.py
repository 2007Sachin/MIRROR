"""Role progress: how one role's practice is developing, and the answers that show it.

Every statement is derived from a finished practice's stored review. Nothing is
invented and no score is produced. What a practice says about an area is read from the
review's own labels (`dashboard_summary.review_dimensions`); the answers behind it are
the review's own quotes, each tied to the candidate turn it came from.

Rules this module keeps (one place, so the tile, the overview, the timeline and the
drill-down can never disagree):

- Scope. A role is one of the person's role profiles. A practice belongs to it only when
  the session was bound to that profile (or to an earlier profile with the same role
  name, which `RoleAnalysisService.families` folds together). Sessions with no bound
  role are never guessed at.
- Practice. A finished practice whose review exists. Anything else (unfinished, review
  still being prepared) is not a practice here.
- Window. The newest `WINDOW` practices are read and drawn as columns.
- Not explored is not weak. A practice that says nothing about an area gives that area
  NOT_EXPLORED; it is skipped when comparing, never treated as a decline. A focused
  practice or quick drill therefore cannot make the areas it did not touch look worse.
- Trend. For one area, the newest two practices that both explored it. Fewer than
  `MIN_COMPARABLE` such practices means no trend, only a state. Two data points are
  only ever described as "since your earlier practice", never as a long-term pattern.
  A practice that ended early (`shorter_conversation`) is shown but not compared.
- Retries. Try-again attempts are stored apart from the practice. They are shown next to
  the answer they retry and never change a practice's states or the counts here, so the
  same question is never counted twice.
- Answers. An answer is a candidate turn. Its state per area comes only from the
  review's evidence for that turn (see `answer_signals`); an answer the review did not
  speak to has no state and is not listed.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .aio import gather_in_order
from .attempt_models import AttemptView, attempt_view
from .claims_models import EvidenceDirection
from .dashboard_models import DashboardDiagnostic
from .dashboard_summary import (
    CLEAR,
    COULD_GO_FURTHER,
    DEVELOPING,
    NEEDS_ATTENTION,
    STRONG,
    review_dimensions,
)
from .interview_map import DEFAULT_MATCHER, MatchStrength, _themes, slug
from .report_models import ReportResponse
from .report_service import ReportAssessmentIncomplete, ReportNotFound, ReportUnavailable
from .role_models import RoleAnalysisResponse, RoleAnalysisStatus, RoleProfileRead
from .schemas import SessionStatus

WINDOW = 4
MIN_COMPARABLE = 2
MAX_INSIGHTS = 3
_READ_CONCURRENCY = 6

# The area each dimension is practised through. Same pairs the Progress pages used before.
DIMENSION_FOCUS = {
    "role_understanding": "role",
    "examples": "story",
    "depth": "decisions",
    "impact": "impact",
}
DIMENSIONS = tuple(DIMENSION_FOCUS)


class ProgressModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DevState(StrEnum):
    COMING_THROUGH = "COMING_THROUGH"
    DEVELOPING = "DEVELOPING"
    NEEDS_PRACTICE = "NEEDS_PRACTICE"
    NOT_EXPLORED = "NOT_EXPLORED"


class Trend(StrEnum):
    MORE = "MORE"
    SIMILAR = "SIMILAR"
    LESS = "LESS"


class AnswerState(StrEnum):
    STRONG = "STRONG"
    PRESENT = "PRESENT"
    NEEDS_PRACTICE = "NEEDS_PRACTICE"


class Stage(StrEnum):
    NONE = "NONE"
    BASELINE = "BASELINE"
    COMPARABLE = "COMPARABLE"


class Seen(StrEnum):
    REPEATEDLY = "REPEATEDLY"
    SOMETIMES = "SOMETIMES"
    NOT_EXPLORED = "NOT_EXPLORED"


class ConnectionState(StrEnum):
    READY = "READY"
    PREPARING = "PREPARING"
    UNAVAILABLE = "UNAVAILABLE"


_STATE_OF_LABEL = {
    STRONG: DevState.COMING_THROUGH,
    CLEAR: DevState.COMING_THROUGH,
    DEVELOPING: DevState.DEVELOPING,
    COULD_GO_FURTHER: DevState.DEVELOPING,
    NEEDS_ATTENTION: DevState.NEEDS_PRACTICE,
}
_RANK = {DevState.NEEDS_PRACTICE: 0, DevState.DEVELOPING: 1, DevState.COMING_THROUGH: 2}


# ----------------------------------------------------------------------------- contract


class PracticeItem(ProgressModel):
    session_id: UUID
    number: int
    completed_at: datetime
    practice_mode: str
    practice_focus: str | None = None
    practice_theme: str | None = None
    question_count: int | None = None
    shorter_conversation: bool | None = None  # known only for practices that were read


class Cell(ProgressModel):
    session_id: UUID
    number: int
    completed_at: datetime
    state: DevState
    answers_seen: int = 0
    answers_strong: int = 0


class Dimension(ProgressModel):
    key: str
    state: DevState  # the newest practice that explored it; NOT_EXPLORED if none did
    note: str | None = None
    trend: Trend | None = None
    compared_with: datetime | None = None  # the earlier practice the trend was measured against
    current: bool = False  # the trend includes the newest comparable practice
    practice_focus: str
    cells: list[Cell]


class Insight(ProgressModel):
    dimension: str
    trend: Trend
    compared_with: datetime


class AnswerSignal(ProgressModel):
    dimension: str
    state: AnswerState
    observation: str
    quote: str | None = None


class AnswerRef(ProgressModel):
    session_id: UUID
    answer_turn_id: UUID


class Answer(ProgressModel):
    session_id: UUID
    answer_turn_id: UUID
    question: str
    practice_number: int
    completed_at: datetime
    question_position: int
    question_total: int
    signals: list[AnswerSignal]


class ConnectionArea(ProgressModel):
    key: str
    name: str
    seen: Seen
    practices_seen: int
    answers: list[AnswerRef]


class Connection(ProgressModel):
    state: ConnectionState
    areas: list[ConnectionArea] = []


class RoleProgress(ProgressModel):
    role_profile_id: UUID
    target_role: str
    stage: Stage
    practice_count: int
    last_practised_at: datetime | None = None
    practices: list[PracticeItem]  # every practice, newest first
    dimensions: list[Dimension]
    insights: list[Insight]
    answers: list[Answer]
    connection: Connection


class TileSignal(ProgressModel):
    dimension: str
    kind: str  # IMPROVING, CLEAR, NEEDS_ATTENTION or LESS


class RoleTile(ProgressModel):
    role_profile_id: UUID
    target_role: str
    stage: Stage
    practice_count: int
    last_practised_at: datetime | None = None
    positive: TileSignal | None = None
    attention: TileSignal | None = None


class ProgressHub(ProgressModel):
    roles: list[RoleTile]


class AnswerDetail(ProgressModel):
    role_profile_id: UUID
    target_role: str
    session_id: UUID
    answer_turn_id: UUID
    question: str
    answer: str
    practice_number: int
    completed_at: datetime
    practice_mode: str
    question_position: int
    question_total: int
    signals: list[AnswerSignal]
    attempts: list[AttemptView]


# ----------------------------------------------------------------------------- answers


def _short(text: str, limit: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# Session moments that speak to one area, and which way. Same grouping the earlier
# Progress pages used for excerpts, now with a direction.
_MOMENT_SIGNAL = {
    "STRONG_EVIDENCE": ("examples", AnswerState.STRONG),
    "TECHNICAL_DEPTH": ("depth", AnswerState.STRONG),
    "OWNERSHIP_CLARIFICATION": ("impact", AnswerState.STRONG),
    "UNSUPPORTED_SCALE": ("impact", AnswerState.NEEDS_PRACTICE),
}
_SKILL_STATE = {"STRONG": AnswerState.STRONG, "WEAK": AnswerState.NEEDS_PRACTICE}
# The review reads role understanding and depth from the same skill assessments, so the
# answers behind those assessments are the answers behind both areas.
_SKILL_DIMENSIONS = ("role_understanding", "depth")

_Raw = tuple[str, UUID, AnswerState, str, str | None]


def _raw_signals(report: ReportResponse) -> list[_Raw]:
    raw: list[_Raw] = []
    audit = report.claims_audit
    for group in (audit.held, audit.partially_held, audit.walked_back, audit.contradicted, audit.insufficient_evidence):
        for claim in group:
            for evidence in claim.evidence:
                if evidence.turn_id is None:
                    continue
                if evidence.direction == EvidenceDirection.SUPPORTS:
                    state = AnswerState.STRONG
                elif evidence.direction == EvidenceDirection.WEAKENS:
                    state = AnswerState.NEEDS_PRACTICE
                else:
                    continue
                raw.append(("examples", evidence.turn_id, state, f"About “{_short(claim.claim_text)}”: {claim.explanation}", evidence.quote))
    for moment in report.session_moments:
        kind = moment.type.value if hasattr(moment.type, "value") else str(moment.type)
        mapped = _MOMENT_SIGNAL.get(kind)
        if mapped and moment.turn_id is not None:
            raw.append((mapped[0], moment.turn_id, mapped[1], moment.explanation, moment.quote))
    for skill in report.skill_assessments:
        if skill.status == "NOT_ENOUGH_SIGNAL":
            continue
        state = _SKILL_STATE.get(skill.signal_strength.upper(), AnswerState.PRESENT)
        for evidence in skill.evidence:
            if evidence.turn_id is None:
                continue
            for dimension in _SKILL_DIMENSIONS:
                raw.append((dimension, evidence.turn_id, state, f"{skill.skill}: {skill.explanation}", evidence.quote))
    return raw


def answer_signals(report: ReportResponse) -> dict[UUID, list[AnswerSignal]]:
    """What the review recorded about each candidate answer, one signal per area.

    Only supporting evidence: STRONG. Only gaps: NEEDS_PRACTICE. Both, or evidence that
    says an area came up without leaning either way: PRESENT. When both are present the
    gap is the observation shown, because that is the part worth acting on.
    """
    grouped: dict[tuple[str, UUID], list[_Raw]] = {}
    for item in _raw_signals(report):
        grouped.setdefault((item[0], item[1]), []).append(item)
    by_turn: dict[UUID, list[AnswerSignal]] = {}
    for (dimension, turn_id), items in grouped.items():
        states = {item[2] for item in items}
        state = next(iter(states)) if len(states) == 1 else AnswerState.PRESENT
        chosen = next((item for item in items if item[2] == AnswerState.NEEDS_PRACTICE), items[0])
        by_turn.setdefault(turn_id, []).append(
            AnswerSignal(dimension=dimension, state=state, observation=chosen[3], quote=chosen[4])
        )
    order = {key: index for index, key in enumerate(DIMENSIONS)}
    for signals in by_turn.values():
        signals.sort(key=lambda signal: order.get(signal.dimension, len(order)))
    return by_turn


class Question:
    __slots__ = ("text", "answer", "position", "total")

    def __init__(self, text: str, answer: str, position: int) -> None:
        self.text, self.answer, self.position, self.total = text, answer, position, 0


def question_index(turns: Sequence[Any]) -> dict[UUID, Question]:
    """Each answered question keyed by the candidate turn that answered it, in order."""
    found: dict[UUID, Question] = {}
    asked: str | None = None
    for turn in sorted(turns, key=lambda item: item.turn_index):
        speaker = str(getattr(turn.speaker, "value", turn.speaker)).upper()
        text = turn.text.strip()
        if speaker == "INTERVIEWER" and text:
            asked = text
        elif speaker == "CANDIDATE" and text and asked is not None:
            found[turn.id] = Question(asked, text, len(found) + 1)
            asked = None
    for question in found.values():
        question.total = len(found)
    return found


# ----------------------------------------------------------------------------- development


def _cells(practice: PracticeItem, report: ReportResponse, signals: dict[UUID, list[AnswerSignal]]) -> dict[str, Cell]:
    cells: dict[str, Cell] = {}
    for item in review_dimensions(report):
        state = _STATE_OF_LABEL.get(item.state, DevState.NOT_EXPLORED)
        seen = [s for group in signals.values() for s in group if s.dimension == item.key]
        cells[item.key] = Cell(
            session_id=practice.session_id,
            number=practice.number,
            completed_at=practice.completed_at,
            state=state,
            answers_seen=len(seen) if state != DevState.NOT_EXPLORED else 0,
            answers_strong=sum(1 for s in seen if s.state == AnswerState.STRONG) if state != DevState.NOT_EXPLORED else 0,
        )
    return cells


def _trend(cells: Sequence[Cell], compared: set[UUID], newest: UUID | None) -> tuple[Trend | None, datetime | None, bool]:
    explored = [cell for cell in cells if cell.state != DevState.NOT_EXPLORED and cell.session_id in compared]
    if len(explored) < MIN_COMPARABLE:
        return None, None, False
    latest, earlier = explored[-1], explored[-2]
    delta = _RANK[latest.state] - _RANK[earlier.state]
    trend = Trend.MORE if delta > 0 else Trend.LESS if delta < 0 else Trend.SIMILAR
    return trend, earlier.completed_at, latest.session_id == newest


def build_dimensions(
    window: Sequence[tuple[PracticeItem, ReportResponse]],
    signals: dict[UUID, dict[UUID, list[AnswerSignal]]],
) -> tuple[list[Dimension], Stage]:
    per_practice = [(practice, report, _cells(practice, report, signals.get(practice.session_id, {}))) for practice, report in window]
    compared = {practice.session_id for practice, report, _ in per_practice if not report.shorter_conversation}
    newest = next((practice.session_id for practice, _, _ in reversed(per_practice) if practice.session_id in compared), None)
    notes = {
        (practice.session_id, item.key): item.note
        for practice, report, _ in per_practice
        for item in review_dimensions(report)
    }
    dimensions: list[Dimension] = []
    for key in DIMENSIONS:
        cells = [cells_by_key[key] for _, _, cells_by_key in per_practice]
        trend, earlier, current = _trend(cells, compared, newest)
        # State comes only from practices that count. One that ended early is shown, not read from.
        latest = next((cell for cell in reversed(cells) if cell.state != DevState.NOT_EXPLORED and cell.session_id in compared), None)
        dimensions.append(
            Dimension(
                key=key,
                state=latest.state if latest else DevState.NOT_EXPLORED,
                note=notes.get((latest.session_id, key)) if latest else None,
                trend=trend,
                compared_with=earlier,
                current=current,
                practice_focus=DIMENSION_FOCUS[key],
                cells=cells,
            )
        )
    if not per_practice:
        stage = Stage.NONE
    else:
        stage = Stage.COMPARABLE if len(compared) >= MIN_COMPARABLE else Stage.BASELINE
    return dimensions, stage


def build_insights(dimensions: Sequence[Dimension]) -> list[Insight]:
    """What changed since the earlier practice, at most three, movement before sameness."""
    current = [d for d in dimensions if d.trend is not None and d.current and d.compared_with is not None]
    ordered = [d for trend in (Trend.MORE, Trend.LESS, Trend.SIMILAR) for d in current if d.trend == trend]
    return [Insight(dimension=d.key, trend=d.trend, compared_with=d.compared_with) for d in ordered[:MAX_INSIGHTS]]  # type: ignore[arg-type]


def tile_signals(dimensions: Sequence[Dimension]) -> tuple[TileSignal | None, TileSignal | None]:
    """One positive and one attention signal, from the same trends the overview shows."""
    positive = next((TileSignal(dimension=d.key, kind="IMPROVING") for d in dimensions if d.trend == Trend.MORE and d.current), None)
    if positive is None:
        positive = next((TileSignal(dimension=d.key, kind="CLEAR") for d in dimensions if d.state == DevState.COMING_THROUGH), None)
    attention = next((TileSignal(dimension=d.key, kind="NEEDS_ATTENTION") for d in dimensions if d.state == DevState.NEEDS_PRACTICE), None)
    if attention is None:
        attention = next((TileSignal(dimension=d.key, kind="LESS") for d in dimensions if d.trend == Trend.LESS and d.current), None)
    return positive, attention


# ----------------------------------------------------------------------------- role connection


def build_connection(
    role: RoleAnalysisResponse | None,
    window: Sequence[tuple[PracticeItem, ReportResponse]],
) -> Connection:
    """Each thing the role looks for, and how often the practices' skill evidence spoke to it."""
    if role is None:
        return Connection(state=ConnectionState.UNAVAILABLE)
    version = role.latest_analysis
    if version is None or version.status == RoleAnalysisStatus.PROCESSING:
        return Connection(state=ConnectionState.PREPARING)
    if version.status == RoleAnalysisStatus.FAILED or not role.competencies:
        return Connection(state=ConnectionState.UNAVAILABLE)
    areas: list[ConnectionArea] = []
    for competency in _themes(role):
        practices: set[UUID] = set()
        answers: dict[tuple[UUID, UUID], AnswerRef] = {}
        for practice, report in window:
            for skill in report.skill_assessments:
                if skill.status == "NOT_ENOUGH_SIGNAL":
                    continue
                if DEFAULT_MATCHER.strength(competency.name, skill.skill) != MatchStrength.USEFUL:
                    continue
                for evidence in skill.evidence:
                    if evidence.turn_id is None:
                        continue  # an assessment with no answer behind it is not "seen in an answer"
                    practices.add(practice.session_id)
                    answers[(practice.session_id, evidence.turn_id)] = AnswerRef(
                        session_id=practice.session_id, answer_turn_id=evidence.turn_id
                    )
        seen = Seen.REPEATEDLY if len(practices) >= 2 else Seen.SOMETIMES if practices else Seen.NOT_EXPLORED
        areas.append(
            ConnectionArea(key=slug(competency.name), name=competency.name, seen=seen, practices_seen=len(practices), answers=list(answers.values()))
        )
    return Connection(state=ConnectionState.READY, areas=areas)


# ----------------------------------------------------------------------------- assembly


def eligible_practices(sessions: Sequence[DashboardDiagnostic], family: frozenset[UUID]) -> list[DashboardDiagnostic]:
    """This role's finished practices, oldest first. The only place role membership is decided."""
    kept = [
        item for item in sessions
        if item.role_profile_id is not None
        and item.role_profile_id in family
        and item.interview_status == SessionStatus.COMPLETED
        and item.diagnostic_available
    ]
    return sorted(kept, key=lambda item: item.completed_at or item.updated_at)


def practice_items(sessions: Sequence[DashboardDiagnostic], counts: dict[UUID, int] | None = None) -> list[PracticeItem]:
    return [
        PracticeItem(
            session_id=item.id,
            number=number,
            completed_at=item.completed_at or item.updated_at,
            practice_mode=item.practice_mode,
            practice_focus=item.practice_focus,
            practice_theme=item.practice_theme,
            question_count=(counts or {}).get(item.id),
        )
        for number, item in enumerate(sessions, start=1)
    ]


def build_progress(
    profile: RoleProfileRead,
    practices: Sequence[PracticeItem],
    reports: dict[UUID, ReportResponse],
    *,
    questions: dict[UUID, dict[UUID, Question]] | None = None,
    role: RoleAnalysisResponse | None = None,
) -> RoleProgress:
    """Pure: the same inputs always give the same progress. No database, no model."""
    window = [(practice, reports[practice.session_id]) for practice in practices[-WINDOW:] if practice.session_id in reports]
    signals = {practice.session_id: answer_signals(report) for practice, report in window}
    dimensions, stage = build_dimensions(window, signals)
    if stage == Stage.NONE and practices:
        stage = Stage.BASELINE  # practices exist, but none could be read: a baseline with nothing to say yet
    known = {practice.session_id: practice.model_copy(update={"shorter_conversation": report.shorter_conversation}) for practice, report in window}
    history = [known.get(practice.session_id, practice) for practice in practices]

    answers: list[Answer] = []
    for practice, _ in window:
        asked = (questions or {}).get(practice.session_id, {})
        for turn_id, found in signals[practice.session_id].items():
            question = asked.get(turn_id)
            if question is None:
                continue  # without the question there is no honest row to show
            answers.append(
                Answer(
                    session_id=practice.session_id,
                    answer_turn_id=turn_id,
                    question=question.text,
                    practice_number=practice.number,
                    completed_at=practice.completed_at,
                    question_position=question.position,
                    question_total=question.total,
                    signals=found,
                )
            )
    answers.sort(key=lambda item: (-item.practice_number, item.question_position))

    return RoleProgress(
        role_profile_id=profile.id,
        target_role=profile.target_role,
        stage=stage,
        practice_count=len(practices),
        last_practised_at=practices[-1].completed_at if practices else None,
        practices=list(reversed(history)),
        dimensions=dimensions,
        insights=build_insights(dimensions),
        answers=answers,
        connection=build_connection(role, window),
    )


def tile_of(progress: RoleProgress) -> RoleTile:
    positive, attention = tile_signals(progress.dimensions)
    return RoleTile(
        role_profile_id=progress.role_profile_id,
        target_role=progress.target_role,
        stage=progress.stage,
        practice_count=progress.practice_count,
        last_practised_at=progress.last_practised_at,
        positive=positive,
        attention=attention,
    )


# ----------------------------------------------------------------------------- service


class AnswerNotFound(Exception):
    """No such answer in a finished practice of this role."""


class RolesReader(Protocol):
    async def families(self, user_id: UUID) -> list[tuple[RoleProfileRead, frozenset[UUID]]]: ...
    async def get(self, profile_id: UUID, user_id: UUID) -> RoleAnalysisResponse: ...


class RoleProgressService:
    """Owner-scoped throughout: every read below takes the signed-in user's id."""

    def __init__(self, roles: RolesReader, dashboard: Any, reports: Any, transcript: Any, attempts: Any, counts: Any = None) -> None:
        self._roles = roles
        self._dashboard = dashboard
        self._reports = reports
        self._transcript = transcript
        self._attempts = attempts
        self._counts = counts

    async def _family(self, role_profile_id: UUID, user_id: UUID) -> tuple[RoleProfileRead, frozenset[UUID]]:
        from .role_service import RoleProfileNotFoundForUser

        for profile, family in await self._roles.families(user_id):
            if role_profile_id in family:
                return profile, family
        raise RoleProfileNotFoundForUser

    async def _reports_for(self, practices: Sequence[PracticeItem], user_id: UUID) -> dict[UUID, ReportResponse]:
        gate = asyncio.Semaphore(_READ_CONCURRENCY)

        async def read(item: PracticeItem) -> tuple[UUID, ReportResponse | None]:
            async with gate:
                try:
                    return item.session_id, await self._reports.get_report(item.session_id, user_id)
                except (ReportNotFound, ReportAssessmentIncomplete, ReportUnavailable):
                    return item.session_id, None  # an unreadable review is simply not part of the picture

        return {sid: report for sid, report in await asyncio.gather(*(read(item) for item in practices)) if report is not None}

    async def _questions_for(self, practices: Sequence[PracticeItem], user_id: UUID) -> dict[UUID, dict[UUID, Question]]:
        gate = asyncio.Semaphore(_READ_CONCURRENCY)

        async def read(item: PracticeItem) -> tuple[UUID, dict[UUID, Question]]:
            async with gate:
                try:
                    return item.session_id, question_index(await self._transcript.list_public_turns(item.session_id, user_id))
                except Exception:  # noqa: BLE001 - a missing transcript only hides that practice's answer rows
                    return item.session_id, {}

        return dict(await asyncio.gather(*(read(item) for item in practices)))

    async def _family_and_practices(
        self, role_profile_id: UUID, user_id: UUID
    ) -> tuple[RoleProfileRead, frozenset[UUID], list[PracticeItem]]:
        """The role's family and its finished practices; the two first reads run together."""
        (profile, family), all_sessions = await gather_in_order(
            self._family(role_profile_id, user_id), self._dashboard.sessions(user_id)
        )
        return profile, family, await self._practices(family, user_id, all_sessions)

    async def _practices(
        self, family: frozenset[UUID], user_id: UUID, all_sessions: Sequence[DashboardDiagnostic]
    ) -> list[PracticeItem]:
        sessions = eligible_practices(all_sessions, family)
        counts = await self._counts(user_id, [item.id for item in sessions]) if self._counts and sessions else {}
        return practice_items(sessions, counts)

    async def summary_from(
        self, profile: RoleProfileRead, family: frozenset[UUID], sessions: Sequence[DashboardDiagnostic], user_id: UUID
    ) -> RoleProgress:
        """One role's progress without transcripts or role analysis: what the hub and Home need.

        The caller passes sessions it already read for this user, so several roles cost one read.
        """
        practices = practice_items(eligible_practices(sessions, family))
        reports = await self._reports_for(practices[-WINDOW:], user_id)
        return build_progress(profile, practices, reports)

    async def hub(self, user_id: UUID) -> ProgressHub:
        families, sessions = await gather_in_order(self._roles.families(user_id), self._dashboard.sessions(user_id))

        async def tile(profile: RoleProfileRead, family: frozenset[UUID]) -> RoleTile:
            return tile_of(await self.summary_from(profile, family, sessions, user_id))

        tiles = list(await asyncio.gather(*(tile(profile, family) for profile, family in families)))
        tiles.sort(key=lambda tile: (tile.last_practised_at is None, -(tile.last_practised_at.timestamp() if tile.last_practised_at else 0)))
        return ProgressHub(roles=tiles)

    async def detail(self, role_profile_id: UUID, user_id: UUID) -> RoleProgress:
        profile, family, practices = await self._family_and_practices(role_profile_id, user_id)
        window = practices[-WINDOW:]
        reports, questions, role = await asyncio.gather(
            self._reports_for(window, user_id),
            self._questions_for(window, user_id),
            self._roles.get(profile.id, user_id),
        )
        return build_progress(profile, practices, reports, questions=questions, role=role)

    async def target_detail(self, role_profile_id: UUID, user_id: UUID, session_ids: frozenset[UUID]) -> RoleProgress:
        """Progress over only the given sessions of this role (a target's linked practices).

        Same rules as ``detail``: finished practices of the role family only, the same window and
        the same build; ``detail`` itself is unchanged and still counts every practice of the role.
        """
        (profile, family), all_sessions = await gather_in_order(
            self._family(role_profile_id, user_id), self._dashboard.sessions(user_id)
        )
        linked = [item for item in all_sessions if item.id in session_ids]
        practices = await self._practices(family, user_id, linked)
        window = practices[-WINDOW:]
        reports, questions, role = await asyncio.gather(
            self._reports_for(window, user_id),
            self._questions_for(window, user_id),
            self._roles.get(profile.id, user_id),
        )
        return build_progress(profile, practices, reports, questions=questions, role=role)

    async def answer(self, role_profile_id: UUID, session_id: UUID, answer_turn_id: UUID, user_id: UUID) -> AnswerDetail:
        profile, family, practices = await self._family_and_practices(role_profile_id, user_id)
        practice = next((item for item in practices if item.session_id == session_id), None)
        if practice is None:
            raise AnswerNotFound  # not a finished practice of this role, whoever owns it
        # All three reads run together; failures surface in the order they were read before.
        report, turns, records = await asyncio.gather(
            self._reports.get_report(session_id, user_id),
            self._transcript.list_public_turns(session_id, user_id),
            self._attempts.list_for_session(session_id, user_id),
            return_exceptions=True,
        )
        try:
            for result in (report, turns):
                if isinstance(result, BaseException):
                    raise result
        except (ReportNotFound, ReportAssessmentIncomplete, ReportUnavailable) as exc:
            raise AnswerNotFound from exc
        question = question_index(turns).get(answer_turn_id)
        if question is None:
            raise AnswerNotFound
        if isinstance(records, BaseException):
            raise records
        attempts = [attempt_view(record) for record in records if record.original_turn_id == answer_turn_id]
        return AnswerDetail(
            role_profile_id=profile.id,
            target_role=profile.target_role,
            session_id=session_id,
            answer_turn_id=answer_turn_id,
            question=question.text,
            answer=question.answer,
            practice_number=practice.number,
            completed_at=practice.completed_at,
            practice_mode=practice.practice_mode,
            question_position=question.position,
            question_total=question.total,
            signals=answer_signals(report).get(answer_turn_id, []),
            attempts=attempts,
        )
