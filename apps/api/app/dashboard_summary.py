"""Candidate-facing summary of the latest finished review for the Home page.

Everything here is derived from the existing report (`ReportResponse`): nothing is invented, and
no numeric score is shown. Ranges and ratios are only used to pick one of a few plain labels.
If a piece cannot be derived reliably it comes back as "Not enough to say yet" or is left out.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .claims_models import ClaimStatus
from .dashboard_service import DashboardService
from .report_models import ReportClaim, ReportResponse
from .report_service import (
    ReportAssessmentIncomplete,
    ReportNotFound,
    ReportService,
    ReportUnavailable,
)
from .schemas import SessionStatus

STRONG, CLEAR, DEVELOPING, COULD_GO_FURTHER, NEEDS_ATTENTION = (
    "Strong", "Clear", "Developing", "Could go further", "Needs attention",
)
NOT_ENOUGH = "Not enough to say yet"


class SummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewCounts(SummaryModel):
    clear: int
    could_be_stronger: int
    worth_revisiting: int


class ReviewDimension(SummaryModel):
    key: str
    label: str
    state: str
    note: str


class ReviewImprovement(SummaryModel):
    title: str
    note: str
    from_label: str | None = None


class ReviewNextStep(SummaryModel):
    title: str
    body: str


class LatestReview(SummaryModel):
    session_id: UUID
    target_role: str
    completed_at: datetime
    counts: ReviewCounts | None
    dimensions: list[ReviewDimension]
    improvements: list[ReviewImprovement]
    next_step: ReviewNextStep
    shorter_conversation: bool = False


class DashboardSummaryResponse(SummaryModel):
    latest_review: LatestReview | None = None


# ----------------------------------------------------------------------------- labels

def _label_from_share(share: float) -> str:
    if share >= 0.8:
        return STRONG
    if share >= 0.6:
        return CLEAR
    if share >= 0.4:
        return DEVELOPING
    if share >= 0.2:
        return COULD_GO_FURTHER
    return NEEDS_ATTENTION


NOTES: dict[str, dict[str, str]] = {
    "role_understanding": {
        STRONG: "You understood what the role is looking for.",
        CLEAR: "You understood what the role is looking for.",
        DEVELOPING: "You showed some of what the role looks for.",
        COULD_GO_FURTHER: "Some of what the role looks for didn't come up yet.",
        NEEDS_ATTENTION: "Much of what the role looks for didn't come through yet.",
    },
    "examples": {
        STRONG: "You had relevant situations to draw from.",
        CLEAR: "You had relevant situations to draw from.",
        DEVELOPING: "Some examples came through, and others need more detail.",
        COULD_GO_FURTHER: "Your examples could use a little more shape.",
        NEEDS_ATTENTION: "Your examples were hard to follow this time.",
    },
    "depth": {
        STRONG: "Your answers went into good detail.",
        CLEAR: "Your answers had the detail they needed.",
        DEVELOPING: "Some answers had detail, and others were brief.",
        COULD_GO_FURTHER: "Some answers needed more specifics.",
        NEEDS_ATTENTION: "Most answers stayed at a high level.",
    },
    "impact": {
        STRONG: "Your contribution was easy to separate from the team's.",
        CLEAR: "Your contribution was easy to separate from the team's.",
        DEVELOPING: "Your contribution came through in some answers.",
        COULD_GO_FURTHER: "The results of your work weren't always easy to see.",
        NEEDS_ATTENTION: "Your contribution wasn't always easy to separate from the team's.",
    },
}
NOT_ENOUGH_NOTE = "There wasn't enough in this conversation to say yet."

DIMENSION_LABELS = {
    "role_understanding": "Role understanding",
    "examples": "Your examples",
    "depth": "Depth of answers",
    "impact": "Showing your impact",
}

# Growth areas the report already picks (one root cause per conversation), in plain words.
ROOT_CAUSE_TEXT: dict[str, tuple[str, str]] = {
    "OWNERSHIP_SPECIFICITY": ("Make your impact easier to see", "Say what you did yourself, and what the team did."),
    "OUTCOME_EVIDENCE": ("Add the outcome", "Your examples had context. Add what changed because of your work."),
    "TECHNICAL_DEPTH": ("Go a little deeper", "Explain how it works, including one choice you made and why."),
    "ANSWER_STRUCTURE": ("Shape your answers", "Try the situation, what you did, and what happened."),
    "COMPOSURE_UNDER_PROBE": ("Stay comfortable when asked more", "A pause before a follow-up is always welcome."),
    "ROLE_SKILL_GAP": ("Build skills for this role", "Pick one skill from the role and practise it this week."),
}

# One plain title per kind of area that came through only partly.
CLAIM_TITLES = {
    ClaimStatus.CONTRADICTED: "Make this consistent",
    ClaimStatus.PARTIALLY_HELD: "Add more detail",
    ClaimStatus.INSUFFICIENT_EVIDENCE: "Say a little more",
}

_SIGNAL_VALUE = {"STRONG": 3.0, "MODERATE": 2.0, "WEAK": 1.0}


# ----------------------------------------------------------------------------- derivations

def review_counts(report: ReportResponse) -> ReviewCounts | None:
    audit = report.claims_audit
    counts = ReviewCounts(
        clear=len(audit.held) + len(audit.walked_back),
        could_be_stronger=len(audit.partially_held) + len(audit.insufficient_evidence),
        worth_revisiting=len(audit.contradicted),
    )
    if counts.clear + counts.could_be_stronger + counts.worth_revisiting == 0:
        return None  # nothing was explored, so there is nothing honest to count
    return counts


def _dimension(key: str, state: str | None) -> ReviewDimension:
    if state is None:
        return ReviewDimension(key=key, label=DIMENSION_LABELS[key], state=NOT_ENOUGH, note=NOT_ENOUGH_NOTE)
    return ReviewDimension(key=key, label=DIMENSION_LABELS[key], state=state, note=NOTES[key][state])


def _role_state(report: ReportResponse) -> str | None:
    readiness = report.role_readiness
    if readiness.low is None or readiness.high is None:
        return None
    return _label_from_share(((readiness.low + readiness.high) / 2) / 100)


def _examples_state(report: ReportResponse) -> str | None:
    audit = report.claims_audit
    judged = len(audit.held) + len(audit.partially_held) + len(audit.walked_back) + len(audit.contradicted)
    if judged == 0:
        return None
    return _label_from_share((len(audit.held) + 0.5 * len(audit.partially_held) + 0.5 * len(audit.walked_back)) / judged)


def _depth_state(report: ReportResponse) -> str | None:
    values = [
        _SIGNAL_VALUE[skill.signal_strength.upper()]
        for skill in report.skill_assessments
        if skill.status != "NOT_ENOUGH_SIGNAL" and skill.signal_strength.upper() in _SIGNAL_VALUE
    ]
    if not values:
        return None
    return _label_from_share((sum(values) / len(values) - 1) / 2)  # 1..3 mapped onto 0..1


def _impact_state(report: ReportResponse) -> str | None:
    moments = {moment.type.value if hasattr(moment.type, "value") else str(moment.type) for moment in report.session_moments}
    if report.root_cause == "OWNERSHIP_SPECIFICITY":
        return NEEDS_ATTENTION
    if report.root_cause == "OUTCOME_EVIDENCE" or "UNSUPPORTED_SCALE" in moments:
        return COULD_GO_FURTHER
    if "OWNERSHIP_CLARIFICATION" in moments:
        return CLEAR
    return None


def review_dimensions(report: ReportResponse) -> list[ReviewDimension]:
    return [
        _dimension("role_understanding", _role_state(report)),
        _dimension("examples", _examples_state(report)),
        _dimension("depth", _depth_state(report)),
        _dimension("impact", _impact_state(report)),
    ]


def _short(text: str, limit: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def review_improvements(report: ReportResponse, limit: int = 3) -> list[ReviewImprovement]:
    items: list[ReviewImprovement] = []
    root = ROOT_CAUSE_TEXT.get(report.root_cause)
    if root:
        items.append(ReviewImprovement(title=root[0], note=root[1]))
    audit = report.claims_audit
    ordered: list[ReportClaim] = [*audit.contradicted, *audit.partially_held, *audit.insufficient_evidence]
    for claim in ordered:
        if len(items) >= limit:
            break
        items.append(ReviewImprovement(title=CLAIM_TITLES[claim.status], note=claim.explanation, from_label=_short(claim.claim_text)))
    return items[:limit]


def review_next_step(improvements: list[ReviewImprovement]) -> ReviewNextStep:
    if improvements:
        first = improvements[0]
        return ReviewNextStep(title=first.title, body=first.note)
    return ReviewNextStep(title="Keep practising", body="Another conversation will show a little more about how you explain your work.")


def build_latest_review(session_id: UUID, report: ReportResponse) -> LatestReview:
    improvements = review_improvements(report)
    return LatestReview(
        session_id=session_id,
        target_role=report.session.target_role,
        completed_at=report.session.completed_at,
        counts=review_counts(report),
        dimensions=review_dimensions(report),
        improvements=improvements,
        next_step=review_next_step(improvements),
        shorter_conversation=bool(getattr(report, "shorter_conversation", False)),
    )


class DashboardSummaryService:
    def __init__(self, dashboard: DashboardService, reports: ReportService) -> None:
        self._dashboard = dashboard
        self._reports = reports

    async def summary(self, user_id: UUID) -> DashboardSummaryResponse:
        workspace = await self._dashboard.workspace(user_id)
        sessions = [item for item in [workspace.current, *workspace.previous] if item is not None]
        latest = next(
            (item for item in sessions if item.interview_status == SessionStatus.COMPLETED and item.diagnostic_available),
            None,
        )
        if latest is None:
            return DashboardSummaryResponse()
        try:
            report = await self._reports.get_report(latest.id, user_id)
        except (ReportNotFound, ReportAssessmentIncomplete, ReportUnavailable):
            # A review that is not readable right now is not an error for the Home page.
            return DashboardSummaryResponse()
        return DashboardSummaryResponse(latest_review=build_latest_review(latest.id, report))
