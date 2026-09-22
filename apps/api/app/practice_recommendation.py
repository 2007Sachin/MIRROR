"""What to practise next: one recommendation, or honestly none.

Deterministic. The recommendation is always a quick drill on one area, and its reason
is text Mirror already produced elsewhere (a preparation area on the Interview Map, or
the latest review's growth area). A weakness is never invented: with nothing to go on,
there is no recommendation and the candidate chooses.

Order:
1. a role preparation area that names a practice focus (Interview Map)
2. the latest review's growth area for this role
3. an Interview Map theme with no example yet
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .dashboard_summary import ROOT_CAUSE_TEXT, LatestReview
from .interview_map import AreaAction, Coverage, InterviewMap, MapState
from .practice_modes import PracticeFocus, PracticeMode

# The review's own growth-area codes, and the practice that works on each.
FOCUS_FOR_ROOT_CAUSE: dict[str, PracticeFocus] = {
    "OWNERSHIP_SPECIFICITY": PracticeFocus.IMPACT,
    "OUTCOME_EVIDENCE": PracticeFocus.IMPACT,
    "TECHNICAL_DEPTH": PracticeFocus.DECISIONS,
    "ANSWER_STRUCTURE": PracticeFocus.STORY,
    "COMPOSURE_UNDER_PROBE": PracticeFocus.DECISIONS,
    "ROLE_SKILL_GAP": PracticeFocus.ROLE,
}


class RecommendationSource(StrEnum):
    ROLE_AREA = "ROLE_AREA"
    REVIEW = "REVIEW"
    MAP_GAP = "MAP_GAP"


class PracticeRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_profile_id: UUID
    target_role: str
    mode: PracticeMode
    focus: PracticeFocus
    theme: str | None = None
    reason: str
    source: RecommendationSource


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: PracticeRecommendation | None = None


def recommend_practice(map_: InterviewMap, latest_review: LatestReview | None) -> PracticeRecommendation | None:
    if map_.state != MapState.READY:
        return None
    base = {"role_profile_id": map_.role_profile_id, "target_role": map_.target_role, "mode": PracticeMode.QUICK_DRILL}

    for area in map_.preparation_areas:
        if area.focus and area.action in (AreaAction.PRACTICE, AreaAction.PRESSURE_TEST):
            return PracticeRecommendation(
                **base, focus=PracticeFocus(area.focus), reason=area.body, source=RecommendationSource.ROLE_AREA
            )

    if latest_review and latest_review.root_cause in FOCUS_FOR_ROOT_CAUSE:
        reason = ROOT_CAUSE_TEXT[latest_review.root_cause][1]
        return PracticeRecommendation(
            **base, focus=FOCUS_FOR_ROOT_CAUSE[latest_review.root_cause], reason=reason, source=RecommendationSource.REVIEW
        )

    for area in map_.preparation_areas:
        theme = next((item for item in map_.themes if item.key == area.theme_key), None)
        if theme and theme.coverage in (Coverage.MISSING, Coverage.MENTIONED):
            return PracticeRecommendation(
                **base, focus=PracticeFocus.ROLE, theme=theme.name, reason=area.body, source=RecommendationSource.MAP_GAP
            )
    return None
