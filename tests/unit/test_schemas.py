from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import EvidenceScore


def test_scored_row_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        EvidenceScore(
            question_index=1,
            skill="SQL",
            status="scored",
            clarity=70,
            depth=70,
            relevance=70,
            communication=70,
            composite=70,
            signal_strength=0.8,
        )


def test_not_enough_signal_has_no_numeric_score() -> None:
    row = EvidenceScore(
        question_index=1, skill="SQL", status="not_enough_signal", signal_strength=0.2
    )
    assert row.composite is None


def test_scored_row_accepts_candidate_evidence() -> None:
    row = EvidenceScore(
        question_index=1,
        skill="SQL",
        status="scored",
        clarity=70,
        depth=68,
        relevance=77,
        communication=71,
        composite=72,
        evidence_quotes=[
            "I used a window function because the grouping had to retain row-level detail."
        ],
        evidence_turn_ids=[uuid4()],
        signal_strength=0.8,
    )
    assert row.status == "scored"

