"""Pure, versioned target priority scorer (Loop 2 P1).

Integer points stay internal; output is rank + reason codes + suggested mode with a
deterministic tie-break. Loop 1 report grades are not an input.
"""

from __future__ import annotations

import inspect
import itertools
import random
from datetime import date, timedelta

import pytest

import app.target_priority as target_priority
from app.target_priority import (
    PRIORITY_RULES_VERSION,
    CompetencyInProcess,
    PracticeFact,
    prioritise,
)

TODAY = date(2026, 10, 4)


def _comp(key: str, rounds: int = 1, ordinal: int | None = 1, band: str | None = "MEDIUM") -> CompetencyInProcess:
    return CompetencyInProcess(key=key, round_count=rounds, first_round_ordinal=ordinal, band=band)


def _keys(items) -> list[str]:
    return [item.competency_key for item in items]


def test_rules_are_versioned() -> None:
    assert PRIORITY_RULES_VERSION == "priority-2"


def test_more_rounds_and_less_coverage_rank_first_with_reason_codes() -> None:
    items = prioritise(
        [_comp("system_design", rounds=1, ordinal=2), _comp("coding_quality", rounds=2, ordinal=1)],
        coverage={"system_design": "STRONG", "coding_quality": "BUILD"},
        practice={},
        today=TODAY,
    )

    assert _keys(items) == ["coding_quality", "system_design"]
    assert [item.rank for item in items] == [1, 2]
    first, second = items
    assert first.reason_codes == ("IN_MANY_ROUNDS", "NO_CONFIRMED_EXAMPLE", "NOT_PRACTISED_YET")
    assert first.suggested_mode == "FOCUSED_PRACTICE"
    assert second.reason_codes == ("IN_ONE_ROUND", "NOT_PRACTISED_YET")
    assert second.suggested_mode == "QUICK_DRILL"


def test_unlinked_is_not_weak_and_ranks_below_build() -> None:
    items = prioritise([_comp("a"), _comp("b")], coverage={"a": None, "b": "BUILD"}, practice={}, today=TODAY)
    assert _keys(items) == ["b", "a"]
    assert "NOT_LINKED_TO_YOUR_PLAN" in items[1].reason_codes
    assert items[1].suggested_mode == "FOCUSED_PRACTICE"


def test_recent_practice_and_an_interview_soon_adjust_order() -> None:
    practice = {"a": PracticeFact(count=3, last_practised_on=TODAY - timedelta(days=1))}
    items = prioritise([_comp("a"), _comp("b")], coverage={"a": "GOOD", "b": "GOOD"}, practice=practice, today=TODAY)
    assert _keys(items) == ["b", "a"]
    assert "PRACTISED_RECENTLY" in items[1].reason_codes

    both = {
        "a": PracticeFact(count=2, last_practised_on=TODAY),
        "b": PracticeFact(count=2, last_practised_on=TODAY - timedelta(days=20)),
    }
    items = prioritise([_comp("a"), _comp("b")], coverage={"a": "GOOD", "b": "GOOD"}, practice=both, today=TODAY)
    assert _keys(items) == ["b", "a"]
    assert items[0].reason_codes == ("IN_ONE_ROUND", "SOME_EXAMPLES")
    soon = prioritise([_comp("a")], coverage={"a": "GOOD"}, practice={}, today=TODAY,
                      interview_date=TODAY + timedelta(days=7))
    assert "INTERVIEW_SOON" in soon[0].reason_codes
    low = prioritise([_comp("a", band="LOW")], coverage={"a": "GOOD"}, practice={}, today=TODAY,
                     interview_date=TODAY + timedelta(days=3))
    assert "INTERVIEW_SOON" not in low[0].reason_codes
    past = prioritise([_comp("a")], coverage={"a": "GOOD"}, practice={}, today=TODAY,
                      interview_date=TODAY - timedelta(days=1))
    assert "INTERVIEW_SOON" not in past[0].reason_codes


def test_tie_break_is_round_ordinal_then_key() -> None:
    items = prioritise(
        [_comp("zeta", ordinal=1), _comp("alpha", ordinal=2), _comp("beta", ordinal=None), _comp("aardvark", ordinal=None)],
        coverage={}, practice={}, today=TODAY,
    )
    assert _keys(items) == ["zeta", "alpha", "aardvark", "beta"]


def test_points_are_integers_and_never_serialised() -> None:
    (item,) = prioritise([_comp("a")], coverage={}, practice={}, today=TODAY)
    assert isinstance(item.points, int)
    dumped = item.model_dump()
    assert "points" not in dumped
    assert set(dumped) == {"rank", "competency_key", "reason_codes", "suggested_mode"}


def test_duplicate_competencies_are_rejected() -> None:
    with pytest.raises(ValueError):
        prioritise([_comp("a"), _comp("a")], coverage={}, practice={}, today=TODAY)


def test_loop1_report_grades_are_not_an_input() -> None:
    assert list(inspect.signature(prioritise).parameters) == [
        "competencies", "coverage", "practice", "today", "interview_date",
    ]
    assert set(PracticeFact.model_fields) == {"count", "last_practised_on"}
    # Every input is research-derived round coverage (conditional rounds: Loop 3), never a report grade.
    assert set(CompetencyInProcess.model_fields) == {"key", "round_count", "conditional_round_count", "first_round_ordinal", "band"}
    source = inspect.getsource(target_priority)
    for forbidden in ("report", "assessment", "verdict", "grade", "final_assessment"):
        assert f"import {forbidden}" not in source and f"app.{forbidden}" not in source


# ------------------------------------------------------------------ properties over a small exhaustive grid

BANDS = ("LOW", "MEDIUM", "HIGH", None)
COVERAGE = ("STRONG", "GOOD", "BUILD", None)
PRACTICE = (None, PracticeFact(count=2, last_practised_on=TODAY - timedelta(days=10)),
            PracticeFact(count=1, last_practised_on=TODAY))


def _grid():
    for rounds, band, cover, fact in itertools.product((0, 1, 2), BANDS, COVERAGE, PRACTICE):
        yield rounds, band, cover, fact


def _rank_of(target: str, competencies, coverage, practice, interview_date=None) -> int:
    items = prioritise(competencies, coverage=coverage, practice=practice, today=TODAY, interview_date=interview_date)
    return next(item.rank for item in items if item.competency_key == target)


REFERENCE = [_comp("r1", rounds=2, ordinal=1, band="MEDIUM"), _comp("r2", rounds=1, ordinal=3, band="LOW")]
REF_COVER = {"r1": "GOOD", "r2": "BUILD"}


def test_output_is_deterministic_under_input_order() -> None:
    rng = random.Random(7)
    comps = [_comp(f"k{i}", rounds=i % 3, ordinal=(i % 4) or None, band=BANDS[i % 4]) for i in range(12)]
    cover = {f"k{i}": COVERAGE[i % 4] for i in range(12)}
    expected = prioritise(comps, coverage=cover, practice={}, today=TODAY)
    for _ in range(20):
        shuffled = comps[:]
        rng.shuffle(shuffled)
        assert prioritise(shuffled, coverage=cover, practice={}, today=TODAY) == expected


def test_better_coverage_never_raises_rank() -> None:
    order = ("BUILD", "GOOD", "STRONG")  # unlinked (None) is not on this axis
    for rounds, band, _, fact in _grid():
        ranks = []
        for cover in order:
            comps = [*REFERENCE, _comp("x", rounds=rounds, ordinal=2, band=band)]
            practice = {"x": fact} if fact else {}
            ranks.append(_rank_of("x", comps, {**REF_COVER, "x": cover}, practice))
        assert ranks == sorted(ranks), (rounds, band, fact, ranks)


def test_a_fresh_practice_never_raises_rank() -> None:
    for rounds, band, cover, _ in _grid():
        comps = [*REFERENCE, _comp("x", rounds=rounds, ordinal=2, band=band)]
        before = _rank_of("x", comps, {**REF_COVER, "x": cover}, {})
        after = _rank_of("x", comps, {**REF_COVER, "x": cover}, {"x": PracticeFact(count=1, last_practised_on=TODAY)})
        assert after >= before


def test_a_lower_band_never_outranks_the_same_competency_at_a_higher_band() -> None:
    for rounds, _, cover, fact in _grid():
        ranks = []
        for band in ("HIGH", "MEDIUM", "LOW"):
            comps = [*REFERENCE, _comp("x", rounds=rounds, ordinal=2, band=band)]
            practice = {"x": fact} if fact else {}
            ranks.append(_rank_of("x", comps, {**REF_COVER, "x": cover}, practice, TODAY + timedelta(days=2)))
        assert ranks == sorted(ranks)
