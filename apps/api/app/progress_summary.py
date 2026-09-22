"""How someone's answers are developing across more than one finished practice.

Everything here is derived from reports that already exist. Nothing is invented and
no number is produced. A direction (improving, steady, needs more practice) is only
ever reported when there are at least two finished practices for the same role that
both say something about the same area; otherwise the direction is left empty and
the interface says there is not enough to compare yet.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .dashboard_models import DashboardDiagnostic
from .dashboard_service import DashboardService
from .dashboard_summary import (
    CLEAR,
    COULD_GO_FURTHER,
    DEVELOPING,
    DIMENSION_LABELS,
    NEEDS_ATTENTION,
    STRONG,
    LatestReview,
    build_latest_review,
)
from .report_models import ReportResponse
from .report_service import (
    ReportAssessmentIncomplete,
    ReportNotFound,
    ReportService,
    ReportUnavailable,
)
from .schemas import SessionStatus

# How many finished practices are read for one view. Enough to show movement,
# small enough that the page stays a handful of reads.
MAX_PRACTICES = 5

# Two finished practices for the same role are the least that can show movement.
MIN_COMPARABLE = 2

IMPROVING, STEADY, NEEDS_MORE = "IMPROVING", "STEADY", "NEEDS_MORE_PRACTICE"

# Order of the report's own labels, weakest first. Only used to compare two
# labels with each other, never shown and never turned into a number.
_RANK = {NEEDS_ATTENTION: 0, COULD_GO_FURTHER: 1, DEVELOPING: 2, CLEAR: 3, STRONG: 4}

# Moments the report already recorded, grouped under the area they speak to.
_MOMENTS_FOR = {
    "examples": {"STRONG_EVIDENCE"},
    "depth": {"TECHNICAL_DEPTH"},
    "impact": {"OWNERSHIP_CLARIFICATION", "UNSUPPORTED_SCALE"},
}

_CHANGE_IMPROVED = {
    "role_understanding": "You're connecting your experience to the role more clearly",
    "examples": "You're giving more specific examples",
    "depth": "You're explaining your decisions in more detail",
    "impact": "You're showing more of what changed because of your work",
}
_CHANGE_WATCH = {
    "role_understanding": "Less of what the role looks for came through this time",
    "examples": "Your examples had less shape this time",
    "depth": "Your answers stayed at a higher level this time",
    "impact": "You often stop before explaining the result",
}


class ProgressModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProgressExcerpt(ProgressModel):
    quote: str
    note: str


class DimensionTrend(ProgressModel):
    key: str
    label: str
    state: str
    note: str
    direction: str | None = None
    excerpts: list[ProgressExcerpt] = []


class ProgressChange(ProgressModel):
    kind: str  # IMPROVED or WATCH
    text: str


class ProgressHeadline(ProgressModel):
    title: str
    body: str


class ProgressResponse(ProgressModel):
    roles: list[str] = []
    role: str | None = None
    practices: list[LatestReview] = []
    comparable_count: int = 0
    dimensions: list[DimensionTrend] = []
    changes: list[ProgressChange] = []
    headline: ProgressHeadline | None = None


# ----------------------------------------------------------------------------- derivations


def _direction(latest: str, earlier: str) -> str | None:
    """Movement between two labels, or nothing when either says too little."""
    if latest not in _RANK or earlier not in _RANK:
        return None
    if _RANK[latest] > _RANK[earlier]:
        return IMPROVING
    if _RANK[latest] < _RANK[earlier]:
        return NEEDS_MORE
    return STEADY


def _excerpts(report: ReportResponse, key: str) -> list[ProgressExcerpt]:
    wanted = _MOMENTS_FOR.get(key)
    if not wanted:
        return []
    found: list[ProgressExcerpt] = []
    for moment in report.session_moments:
        kind = moment.type.value if hasattr(moment.type, "value") else str(moment.type)
        if kind not in wanted or not moment.quote:
            continue
        found.append(ProgressExcerpt(quote=moment.quote, note=moment.explanation))
        if len(found) == 2:
            break
    return found


def build_dimensions(
    practices: list[LatestReview], latest_report: ReportResponse | None
) -> list[DimensionTrend]:
    if not practices:
        return []
    latest = {item.key: item for item in practices[0].dimensions}
    earlier = (
        {item.key: item for item in practices[1].dimensions}
        if len(practices) >= MIN_COMPARABLE
        else {}
    )
    trends: list[DimensionTrend] = []
    for key in DIMENSION_LABELS:
        current = latest.get(key)
        if current is None:
            continue
        previous = earlier.get(key)
        trends.append(
            DimensionTrend(
                key=key,
                label=current.label,
                state=current.state,
                note=current.note,
                direction=_direction(current.state, previous.state) if previous else None,
                excerpts=_excerpts(latest_report, key) if latest_report else [],
            )
        )
    return trends


def build_changes(trends: list[DimensionTrend], limit: int = 3) -> list[ProgressChange]:
    """Only movement that two finished practices actually show, newest first."""
    improved = [
        ProgressChange(kind="IMPROVED", text=_CHANGE_IMPROVED[trend.key])
        for trend in trends
        if trend.direction == IMPROVING and trend.key in _CHANGE_IMPROVED
    ]
    watch = [
        ProgressChange(kind="WATCH", text=_CHANGE_WATCH[trend.key])
        for trend in trends
        if trend.direction == NEEDS_MORE and trend.key in _CHANGE_WATCH
    ]
    return (improved + watch)[:limit]


def build_headline(
    practices: list[LatestReview], trends: list[DimensionTrend]
) -> ProgressHeadline:
    if len(practices) < MIN_COMPARABLE:
        return ProgressHeadline(
            title="One practice so far",
            body="Complete another practice to see how your answers are developing over time.",
        )
    moved = [trend for trend in trends if trend.direction in (IMPROVING, NEEDS_MORE)]
    ups = sum(1 for trend in moved if trend.direction == IMPROVING)
    downs = len(moved) - ups
    lowest = min(
        (trend for trend in trends if trend.state in _RANK),
        key=lambda trend: _RANK[trend.state],
        default=None,
    )
    opportunity = (
        f" The biggest opportunity is {lowest.label.lower()}." if lowest else ""
    )
    if ups > downs:
        return ProgressHeadline(
            title="You're getting clearer.",
            body="Across your recent practices, more of your work is coming through." + opportunity,
        )
    if downs > ups:
        return ProgressHeadline(
            title="Your answers are still finding their shape.",
            body="Your recent practices covered different ground, so some areas came through less." + opportunity,
        )
    return ProgressHeadline(
        title="You're holding steady.",
        body="Your recent practices came through in much the same way." + opportunity,
    )


class ProgressService:
    def __init__(self, dashboard: DashboardService, reports: ReportService) -> None:
        self._dashboard = dashboard
        self._reports = reports

    async def _finished(self, user_id: UUID) -> list[DashboardDiagnostic]:
        workspace = await self._dashboard.workspace(user_id)
        finished = [
            item
            for item in [workspace.current, *workspace.previous]
            if item is not None
            and item.interview_status == SessionStatus.COMPLETED
            and item.diagnostic_available
        ]
        finished.sort(key=_completed_key, reverse=True)
        return finished

    async def latest(self, user_id: UUID, role: str) -> LatestReview | None:
        """The newest readable review for one role, or nothing. Reads one report at most."""
        wanted = role.casefold().strip()
        for item in await self._finished(user_id):
            if item.target_role.casefold().strip() != wanted:
                continue
            try:
                return build_latest_review(item.id, await self._reports.get_report(item.id, user_id))
            except (ReportNotFound, ReportAssessmentIncomplete, ReportUnavailable):
                continue
        return None

    async def progress(self, user_id: UUID, role: str | None = None) -> ProgressResponse:
        finished = await self._finished(user_id)
        if not finished:
            return ProgressResponse()

        roles: list[str] = []
        for item in finished:
            if item.target_role not in roles:
                roles.append(item.target_role)

        wanted = role.casefold().strip() if role else finished[0].target_role.casefold()
        selected = [item for item in finished if item.target_role.casefold() == wanted]
        if not selected:
            return ProgressResponse(roles=roles, role=None)

        practices: list[LatestReview] = []
        latest_report: ReportResponse | None = None
        for item in selected[:MAX_PRACTICES]:
            try:
                report = await self._reports.get_report(item.id, user_id)
            except (ReportNotFound, ReportAssessmentIncomplete, ReportUnavailable):
                continue  # a review that cannot be read is simply not compared
            if latest_report is None:
                latest_report = report
            practices.append(build_latest_review(item.id, report))

        if not practices:
            return ProgressResponse(roles=roles, role=selected[0].target_role)

        trends = build_dimensions(practices, latest_report)
        return ProgressResponse(
            roles=roles,
            role=selected[0].target_role,
            practices=practices,
            comparable_count=len(practices),
            dimensions=trends,
            changes=build_changes(trends) if len(practices) >= MIN_COMPARABLE else [],
            headline=build_headline(practices, trends),
        )


def _completed_key(item: DashboardDiagnostic) -> datetime:
    return item.completed_at or item.updated_at
