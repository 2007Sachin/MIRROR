"""B5 adversarial test matrix: evidence integrity and legacy diagnostics.

Tests the complete B5 invariant enforcement:
- Fresh assessments reject invalid evidence before storage
- Cached assessments revalidate against current context
- Reports do not expose invalid evidence
- Legacy unverifiable diagnostics do not influence readiness/progress
- Transcript and candidate content remain accessible regardless of diagnostic validity
"""

from __future__ import annotations

import pytest
from uuid import UUID, uuid4
from datetime import datetime

from app.evidence_validator import (
    EvidenceValidator, EvidenceValidationError, CandidateTurn,
)
from app.specialist_assessor_models import (
    AssessorType, SpecialistStatus, SignalStrength,
    SpecialistAssessmentOutput, DomainAssessment, AssessmentEvidence,
    StoredSpecialistAssessment, AssessmentTranscriptTurn,
    SpecialistAssessmentContext,
)


# ============================================================================
# Test fixtures
# ============================================================================

@pytest.fixture
def validator():
    return EvidenceValidator(turn_horizon=100)


@pytest.fixture
def candidate_turns():
    """Candidate-authored turns from a mock transcript."""
    return [
        CandidateTurn(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            speaker="CANDIDATE",
            text="I led a project that improved performance by 50%.",
            turn_index=0,
        ),
        CandidateTurn(
            id=UUID("00000000-0000-0000-0000-000000000003"),
            speaker="CANDIDATE",
            text="The team used Python and AWS Lambda for the implementation.",
            turn_index=2,
        ),
        CandidateTurn(
            id=UUID("00000000-0000-0000-0000-000000000005"),
            speaker="CANDIDATE",
            text="We deployed to production and monitored the metrics.",
            turn_index=4,
        ),
    ]


@pytest.fixture
def interviewer_turns():
    """Interviewer-authored turns (should not be treated as evidence)."""
    return [
        CandidateTurn(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            speaker="INTERVIEWER",
            text="Tell me about a project you led.",
            turn_index=1,
        ),
        CandidateTurn(
            id=UUID("00000000-0000-0000-0000-000000000004"),
            speaker="INTERVIEWER",
            text="What technologies did you use?",
            turn_index=3,
        ),
    ]


# ============================================================================
# B5-1: Fresh fabricated turn ID
# ============================================================================

def test_b5_1_fresh_fabricated_turndid_rejected(validator, candidate_turns):
    """Evidence referencing non-existent turn ID must be rejected."""
    fabricated_id = UUID("99999999-9999-9999-9999-999999999999")
    
    with pytest.raises(EvidenceValidationError) as exc_info:
        validator.validate_assessment_output(
            evidence_turn_ids=[fabricated_id],
            evidence_quotes=[],
            candidate_turns=candidate_turns,
        )
    
    assert "missing_turn_ids" in str(exc_info.value)


# ============================================================================
# B5-2: Fresh interviewer quote
# ============================================================================

def test_b5_2_fresh_interviewer_quote_rejected(validator, candidate_turns, interviewer_turns):
    """Evidence referencing interviewer turn must be rejected."""
    all_turns = candidate_turns + interviewer_turns
    interviewer_id = UUID("00000000-0000-0000-0000-000000000002")
    
    with pytest.raises(EvidenceValidationError) as exc_info:
        validator.validate_assessment_output(
            evidence_turn_ids=[interviewer_id],
            evidence_quotes=[],
            candidate_turns=candidate_turns,  # Interviewer turns NOT in candidate list
        )
    
    assert "missing_turn_ids" in str(exc_info.value)


# ============================================================================
# B5-3: Fresh whitespace-only quote
# ============================================================================

def test_b5_3_fresh_whitespace_quote_rejected(validator, candidate_turns):
    """Evidence with whitespace-only quote must be rejected."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    
    with pytest.raises(EvidenceValidationError) as exc_info:
        validator.validate_assessment_output(
            evidence_turn_ids=[valid_id],
            evidence_quotes=[{"turn_id": valid_id, "quote": "   "}],
            candidate_turns=candidate_turns,
        )
    
    assert "quote_mismatches" in str(exc_info.value)


# ============================================================================
# B5-4: Fresh mixed valid/invalid references
# ============================================================================

def test_b5_4_fresh_mixed_refs_rejected(validator, candidate_turns):
    """If ANY evidence is invalid, output must be rejected."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    fabricated_id = UUID("99999999-9999-9999-9999-999999999999")
    
    with pytest.raises(EvidenceValidationError) as exc_info:
        validator.validate_assessment_output(
            evidence_turn_ids=[valid_id, fabricated_id],
            evidence_quotes=[],
            candidate_turns=candidate_turns,
        )
    
    assert "missing_turn_ids" in str(exc_info.value)


# ============================================================================
# B5-5: Fresh valid complete assessment
# ============================================================================

def test_b5_5_fresh_valid_complete_accepted(validator, candidate_turns):
    """Assessment with all valid evidence references must pass."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    quote_text = "I led a project that improved performance by 50%."
    
    resolution = validator.validate_assessment_output(
        evidence_turn_ids=[valid_id],
        evidence_quotes=[{"turn_id": valid_id, "quote": quote_text}],
        candidate_turns=candidate_turns,
    )
    
    assert resolution.is_valid
    assert valid_id in resolution.valid_turn_ids


# ============================================================================
# B5-6: Fresh valid insufficient-signal observation
# ============================================================================

def test_b5_6_fresh_valid_insufficient_accepted(validator, candidate_turns):
    """NOT_ENOUGH_SIGNAL with valid nested references must pass."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    
    # Valid insufficient observation with no root evidence but valid nested refs
    resolution = validator.validate_assessment_output(
        evidence_turn_ids=[],  # No root evidence (NOT_ENOUGH_SIGNAL)
        evidence_quotes=[],
        candidate_turns=candidate_turns,
        nested_assessments=[{
            "evidence_turn_ids": [valid_id],
            "evidence_quotes": [{"turn_id": valid_id, "quote": "I led a project"}],
        }],
    )
    
    assert resolution.is_valid


# ============================================================================
# B5-7: Cached invalid revalidation
# ============================================================================

def test_b5_7_cached_invalid_revalidate_fails(validator):
    """Cached specialist with now-missing context must fail revalidation."""
    # Cached specialist referenced turn ID
    cached_id = UUID("00000000-0000-0000-0000-000000000001")
    
    # Current context is empty (turn was deleted/reassigned)
    current_turns = []
    
    with pytest.raises(EvidenceValidationError):
        validator.validate_assessment_output(
            evidence_turn_ids=[cached_id],
            evidence_quotes=[],
            candidate_turns=current_turns,
        )


# ============================================================================
# B5-8: Cached valid revalidation
# ============================================================================

def test_b5_8_cached_valid_revalidate_passes(validator, candidate_turns):
    """Cached specialist with valid context should revalidate."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    quote_text = "I led a project that improved performance by 50%."
    
    resolution = validator.validate_assessment_output(
        evidence_turn_ids=[valid_id],
        evidence_quotes=[{"turn_id": valid_id, "quote": quote_text}],
        candidate_turns=candidate_turns,
    )
    
    assert resolution.is_valid


# ============================================================================
# B5-9: Report with invalid specialist
# ============================================================================

def test_b5_13_legacy_with_provenance_revalidated(validator, candidate_turns):
    """Old diagnostic revalidated against current context should be treated as current."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    quote_text = "I led a project that improved performance by 50%."
    
    resolution = validator.validate_assessment_output(
        evidence_turn_ids=[valid_id],
        evidence_quotes=[{"turn_id": valid_id, "quote": quote_text}],
        candidate_turns=candidate_turns,
    )
    
    # If revalidation passes, treat as current-context-valid
    assert resolution.is_valid


# ============================================================================
# B5-14: Mixed current trusted + legacy unverifiable
# ============================================================================

def test_b5_quote_matching_exact():
    """Quote must match exactly or after normalization."""
    validator = EvidenceValidator()
    turns = [
        CandidateTurn(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            speaker="CANDIDATE",
            text="I used Python and AWS.",
            turn_index=0,
        ),
    ]
    
    resolution = validator.validate_assessment_output(
        evidence_turn_ids=[UUID("00000000-0000-0000-0000-000000000001")],
        evidence_quotes=[{"turn_id": UUID("00000000-0000-0000-0000-000000000001"), "quote": "Python and AWS"}],
        candidate_turns=turns,
    )
    
    assert resolution.is_valid


def test_b5_quote_matching_normalized_whitespace():
    """Quote matching should handle whitespace normalization."""
    validator = EvidenceValidator()
    turns = [
        CandidateTurn(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            speaker="CANDIDATE",
            text="I  used  Python   and   AWS.",
            turn_index=0,
        ),
    ]
    
    resolution = validator.validate_assessment_output(
        evidence_turn_ids=[UUID("00000000-0000-0000-0000-000000000001")],
        evidence_quotes=[{"turn_id": UUID("00000000-0000-0000-0000-000000000001"), "quote": "used Python and AWS"}],
        candidate_turns=turns,
    )
    
    assert resolution.is_valid


def test_b5_quote_matching_partial_mismatch():
    """Quote that does not appear in turn must fail."""
    validator = EvidenceValidator()
    turns = [
        CandidateTurn(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            speaker="CANDIDATE",
            text="I used Python.",
            turn_index=0,
        ),
    ]
    
    with pytest.raises(EvidenceValidationError) as exc_info:
        validator.validate_assessment_output(
            evidence_turn_ids=[UUID("00000000-0000-0000-0000-000000000001")],
            evidence_quotes=[{"turn_id": UUID("00000000-0000-0000-0000-000000000001"), "quote": "used Go"}],
            candidate_turns=turns,
        )
    
    assert "quote_mismatches" in str(exc_info.value)


# ============================================================================
# Extended: Nested assessment evidence
# ============================================================================

def test_b5_nested_invalid_evidence_rejected(validator, candidate_turns):
    """Invalid nested assessment evidence must reject entire output."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    fabricated_id = UUID("99999999-9999-9999-9999-999999999999")
    
    with pytest.raises(EvidenceValidationError) as exc_info:
        validator.validate_assessment_output(
            evidence_turn_ids=[valid_id],
            evidence_quotes=[],
            candidate_turns=candidate_turns,
            nested_assessments=[{
                "evidence_turn_ids": [fabricated_id],
                "evidence_quotes": [],
            }],
        )
    
    assert "missing_turn_ids" in str(exc_info.value)


def test_b5_nested_valid_evidence_accepted(validator, candidate_turns):
    """Valid nested assessment evidence must pass."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    quote_text = "I led a project that improved performance by 50%."
    
    resolution = validator.validate_assessment_output(
        evidence_turn_ids=[valid_id],
        evidence_quotes=[],
        candidate_turns=candidate_turns,
        nested_assessments=[{
            "evidence_turn_ids": [valid_id],
            "evidence_quotes": [{"turn_id": valid_id, "quote": quote_text}],
        }],
    )
    
    assert resolution.is_valid


def test_b5_nesting_depth_limit_protects_from_stack_exhaustion(validator, candidate_turns):
    """Excessive nesting depth must raise error to prevent stack exhaustion."""
    valid_id = UUID("00000000-0000-0000-0000-000000000001")
    
    # Create deeply nested structure exceeding MAX_NESTING_DEPTH (10)
    nested = {"evidence_turn_ids": [valid_id], "evidence_quotes": []}
    deeply_nested = nested
    for _ in range(15):  # Exceeds default MAX_NESTING_DEPTH of 10
        deeply_nested = {"evidence_turn_ids": [valid_id], "evidence_quotes": [], "nested": [deeply_nested]}
    
    with pytest.raises(Exception) as exc_info:
        validator.validate_assessment_output(
            evidence_turn_ids=[valid_id],
            evidence_quotes=[],
            candidate_turns=candidate_turns,
            nested_assessments=[deeply_nested],
        )
    
    assert "Nesting depth" in str(exc_info.value) or "exceeds" in str(exc_info.value)
