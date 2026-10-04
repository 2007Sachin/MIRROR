"""Pure, versioned priority scorer for a person's interview target.

Ranks competencies of the matched process by integer points with stable reason codes and a
deterministic tie-break (points desc, first round ordinal asc, key asc). Points never leave the
backend. Inputs are research-derived round coverage, the person's own plan coverage and their
practice history; Loop 1 report grades are deliberately not an input.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PRIORITY_RULES_VERSION = "priority-1"

Band = Literal["LOW", "MEDIUM", "HIGH"]
Coverage = Literal["STRONG", "GOOD", "BUILD"]  # app.plan_service.PlanStatus values
Mode = Literal["QUICK_DRILL", "FOCUSED_PRACTICE"]

# Internal rules (never serialised).
_ROUNDS_MANY, _ROUNDS_ONE = 30, 15
_BAND = {"HIGH": 10, "MEDIUM": 5, "LOW": 0, None: 0}
_COVERAGE = {"BUILD": 30, "GOOD": 15, "STRONG": 0, None: 10}
_COVERAGE_CODE = {"BUILD": "NO_CONFIRMED_EXAMPLE", "GOOD": "SOME_EXAMPLES", "STRONG": None, None: "NOT_LINKED_TO_YOUR_PLAN"}
_NOT_PRACTISED = 20
_RECENT_PENALTY, _RECENT_DAYS = -15, 2
_SOON_BONUS, _SOON_DAYS = 10, 7


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CompetencyInProcess(_Frozen):
    key: str = Field(min_length=1, max_length=80)
    round_count: int = Field(ge=0)  # non-container rounds of the pinned process that cover it
    first_round_ordinal: int | None = Field(default=None, ge=1)
    band: Band | None = None  # band of its supporting research claims


class PracticeFact(_Frozen):
    count: int = Field(ge=0)
    last_practised_on: date | None = None


class PriorityItem(_Frozen):
    rank: int
    competency_key: str
    reason_codes: tuple[str, ...]
    suggested_mode: Mode
    points: int = Field(exclude=True)


def _score(
    competency: CompetencyInProcess,
    coverage: Coverage | None,
    fact: PracticeFact | None,
    today: date,
    interview_date: date | None,
) -> tuple[int, list[str]]:
    points, codes = 0, []
    if competency.round_count >= 2:
        points += _ROUNDS_MANY
        codes.append("IN_MANY_ROUNDS")
    elif competency.round_count == 1:
        points += _ROUNDS_ONE
        codes.append("IN_ONE_ROUND")
    points += _BAND[competency.band]
    points += _COVERAGE[coverage]
    if _COVERAGE_CODE[coverage]:
        codes.append(_COVERAGE_CODE[coverage])
    if fact is None or fact.count == 0:
        points += _NOT_PRACTISED
        codes.append("NOT_PRACTISED_YET")
    elif fact.last_practised_on is not None and 0 <= (today - fact.last_practised_on).days <= _RECENT_DAYS:
        points += _RECENT_PENALTY
        codes.append("PRACTISED_RECENTLY")
    if (
        interview_date is not None
        and 0 <= (interview_date - today).days <= _SOON_DAYS
        and competency.band in ("MEDIUM", "HIGH")
    ):
        points += _SOON_BONUS
        codes.append("INTERVIEW_SOON")
    return points, codes


def prioritise(
    competencies: Sequence[CompetencyInProcess],
    coverage: Mapping[str, Coverage | None],
    practice: Mapping[str, PracticeFact],
    today: date,
    interview_date: date | None = None,
) -> list[PriorityItem]:
    keys = [competency.key for competency in competencies]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate competency keys")
    scored = []
    for competency in competencies:
        cover = coverage.get(competency.key)
        points, codes = _score(competency, cover, practice.get(competency.key), today, interview_date)
        mode: Mode = "FOCUSED_PRACTICE" if cover in ("BUILD", None) else "QUICK_DRILL"
        ordinal = competency.first_round_ordinal if competency.first_round_ordinal is not None else 10**6
        scored.append(((-points, ordinal, competency.key), points, competency.key, tuple(codes), mode))
    scored.sort(key=lambda row: row[0])
    return [
        PriorityItem(rank=index, competency_key=key, reason_codes=codes, suggested_mode=mode, points=points)
        for index, (_, points, key, codes, mode) in enumerate(scored, start=1)
    ]
