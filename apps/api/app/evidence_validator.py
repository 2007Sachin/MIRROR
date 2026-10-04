"""B5 evidence integrity validator.

Enforces the invariant that assessment evidence references must resolve to actual
candidate-authored content from the relevant session. Model-generated identifiers
or paraphrases do not establish evidence validity.

This validator is called:
1. Before storing fresh specialist assessment outputs
2. Before reusing cached specialist assessments
3. Before including specialist results in reports
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


MIN_QUOTE_CHARS = 3


class EvidenceValidationError(Exception):
    """Raised when evidence validation fails."""
    pass


class EvidenceValidationResult(StrEnum):
    VALID = "VALID"
    INVALID_TURN_ID = "INVALID_TURN_ID"
    INTERVIEWER_TURN = "INTERVIEWER_TURN"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"
    EMPTY_QUOTE = "EMPTY_QUOTE"
    TURN_NOT_IN_CONTEXT = "TURN_NOT_IN_CONTEXT"


@dataclass(frozen=True)
class CandidateTurn:
    """A candidate-authored turn from the assessment context."""
    id: UUID
    speaker: str
    text: str
    turn_index: int


@dataclass
class EvidenceResolution:
    """Result of resolving evidence references against context."""
    valid_turn_ids: list[UUID]
    invalid_turn_ids: list[UUID]
    interviewer_turn_ids: list[UUID]
    quote_mismatches: list[tuple[UUID, str]]  # (turn_id, quote)
    missing_turn_ids: list[UUID]
    
    @property
    def is_valid(self) -> bool:
        """True if all evidence references are valid."""
        return (
            not self.invalid_turn_ids
            and not self.interviewer_turn_ids
            and not self.quote_mismatches
            and not self.missing_turn_ids
        )


class EvidenceValidator:
    """Validates that assessment evidence resolves to actual candidate content.
    
    B5 invariant: Mirror must never treat an assessment claim as transcript-supported
    unless the referenced evidence can be resolved to actual candidate content from
    the relevant interview/session.
    """
    
    CANDIDATE_SPEAKER_VALUES = frozenset({"CANDIDATE", "candidate", "Candidate"})
    TURN_HORIZON_DEFAULT = 100
    MAX_NESTING_DEPTH = 10  # Prevent stack exhaustion on deeply nested assessments
    
    def __init__(self, turn_horizon: int | None = None):
        self.turn_horizon = turn_horizon or self.TURN_HORIZON_DEFAULT
        self._nesting_depth = 0
    
    def validate_evidence_turn_ids(
        self,
        evidence_turn_ids: list[UUID],
        candidate_turns: list[CandidateTurn],
    ) -> EvidenceResolution:
        """Validate that all evidence turn IDs resolve to candidate turns.
        
        Args:
            evidence_turn_ids: Turn IDs referenced in assessment output
            candidate_turns: Available candidate turns from context (already filtered)
            
        Returns:
            EvidenceResolution with valid/invalid classifications
        """
        valid_ids = []
        invalid_ids = []
        interviewer_ids = []
        missing_ids = []
        
        candidate_turn_map = {turn.id: turn for turn in candidate_turns}
        
        for turn_id in evidence_turn_ids:
            turn = candidate_turn_map.get(turn_id)
            if turn is None:
                # Not found in candidate turns - could be missing or interviewer
                missing_ids.append(turn_id)
            elif turn.speaker not in self.CANDIDATE_SPEAKER_VALUES:
                interviewer_ids.append(turn_id)
            else:
                valid_ids.append(turn_id)
        
        return EvidenceResolution(
            valid_turn_ids=valid_ids,
            invalid_turn_ids=invalid_ids,
            interviewer_turn_ids=interviewer_ids,
            quote_mismatches=[],
            missing_turn_ids=missing_ids,
        )
    
    def validate_evidence_quotes(
        self,
        evidence_quotes: list[dict],  # {"turn_id": UUID, "quote": str}
        candidate_turns: list[CandidateTurn],
    ) -> EvidenceResolution:
        """Validate that all evidence quotes match actual candidate turn text.
        
        Args:
            evidence_quotes: Quote references from assessment output
            candidate_turns: Available candidate turns from context
            
        Returns:
            EvidenceResolution with validation results
        """
        valid_ids = []
        invalid_ids = []
        interviewer_ids = []
        mismatches = []
        missing_ids = []
        
        candidate_turn_map = {turn.id: turn for turn in candidate_turns}
        
        for quote_ref in evidence_quotes:
            turn_id = quote_ref.get("turn_id") if isinstance(quote_ref, dict) else getattr(quote_ref, "turn_id", None)
            quote_text = quote_ref.get("quote", "") if isinstance(quote_ref, dict) else getattr(quote_ref, "quote", "")
            
            if turn_id is None:
                missing_ids.append(UUID(int=0))  # unattributable quote is unresolvable evidence
                continue

            turn = candidate_turn_map.get(turn_id)
            if turn is None:
                missing_ids.append(turn_id)
            elif turn.speaker not in self.CANDIDATE_SPEAKER_VALUES:
                interviewer_ids.append(turn_id)
            elif not quote_text or not quote_text.strip():
                # Empty or whitespace-only quote
                mismatches.append((turn_id, quote_text or ""))
            elif not self._quote_matches(quote_text, turn.text):
                mismatches.append((turn_id, quote_text))
            else:
                valid_ids.append(turn_id)
        
        return EvidenceResolution(
            valid_turn_ids=list(set(valid_ids)),
            invalid_turn_ids=invalid_ids,
            interviewer_turn_ids=interviewer_ids,
            quote_mismatches=mismatches,
            missing_turn_ids=list(set(missing_ids)),
        )
    
    def validate_assessment_output(
        self,
        evidence_turn_ids: list[UUID],
        evidence_quotes: list[dict],
        candidate_turns: list[CandidateTurn],
        nested_assessments: list[dict] | None = None,
    ) -> EvidenceResolution:
        """Validate all evidence references in a specialist assessment output.
        
        This is the main entry point for B5 validation. It validates:
        - Root-level evidence_turn_ids
        - Root-level evidence_quotes  
        - Nested assessment evidence (dimensions, competency_or_domain_assessments)
        
        Args:
            evidence_turn_ids: Root-level turn IDs from output
            evidence_quotes: Root-level quotes from output
            candidate_turns: Available candidate turns from context
            nested_assessments: Nested domain assessments with their own evidence
            
        Returns:
            Combined EvidenceResolution for all references
            
        Raises:
            EvidenceValidationError: If any evidence is invalid
        """
        # Reset nesting depth for fresh validation
        self._nesting_depth = 0
        
        # Validate root-level evidence
        turn_resolution = self.validate_evidence_turn_ids(evidence_turn_ids, candidate_turns)
        quote_resolution = self.validate_evidence_quotes(evidence_quotes, candidate_turns)
        
        # Collect all issues
        all_invalid = set(turn_resolution.invalid_turn_ids) | set(quote_resolution.invalid_turn_ids)
        all_interviewer = set(turn_resolution.interviewer_turn_ids) | set(quote_resolution.interviewer_turn_ids)
        all_missing = set(turn_resolution.missing_turn_ids) | set(quote_resolution.missing_turn_ids)
        all_mismatches = list(quote_resolution.quote_mismatches)
        all_valid = set(turn_resolution.valid_turn_ids) | set(quote_resolution.valid_turn_ids)
        
        # Validate nested assessments recursively; depth-limited, fail closed.
        def _walk(items: list[dict], depth: int) -> None:
            if depth > self.MAX_NESTING_DEPTH:
                raise EvidenceValidationError(
                    f"Nesting depth {depth} exceeds maximum {self.MAX_NESTING_DEPTH}"
                )
            for nested in items:
                if not isinstance(nested, dict):
                    raise EvidenceValidationError("malformed nested evidence")
                nt = self.validate_evidence_turn_ids(nested.get("evidence_turn_ids", []), candidate_turns)
                nq = self.validate_evidence_quotes(nested.get("evidence_quotes", []), candidate_turns)
                all_invalid.update(nt.invalid_turn_ids)
                all_interviewer.update(nt.interviewer_turn_ids)
                all_missing.update(nt.missing_turn_ids)
                all_mismatches.extend(nq.quote_mismatches)
                all_valid.update(nt.valid_turn_ids)
                all_valid.update(nq.valid_turn_ids)
                children = nested.get("nested")
                if children:
                    _walk(children, depth + 1)

        if nested_assessments:
            _walk(nested_assessments, 1)

        resolution = EvidenceResolution(
            valid_turn_ids=list(all_valid),
            invalid_turn_ids=list(all_invalid),
            interviewer_turn_ids=list(all_interviewer),
            quote_mismatches=all_mismatches,
            missing_turn_ids=list(all_missing),
        )
        
        if not resolution.is_valid:
            issues = []
            if resolution.missing_turn_ids:
                issues.append(f"missing_turn_ids={[str(t) for t in resolution.missing_turn_ids[:5]]}")
            if resolution.interviewer_turn_ids:
                issues.append(f"interviewer_turn_ids={[str(t) for t in resolution.interviewer_turn_ids[:5]]}")
            if resolution.quote_mismatches:
                issues.append(f"quote_mismatches={len(resolution.quote_mismatches)}")
            
            raise EvidenceValidationError(
                f"Evidence validation failed: {'; '.join(issues)}"
            )
        
        return resolution
    
    @staticmethod
    def _quote_matches(quote: str, source: str) -> bool:
        """Check if quote text appears in source text."""
        if not quote or not source:
            return False
        if len(" ".join(quote.split())) < MIN_QUOTE_CHARS:  # trivial fragments prove nothing
            return False
        # Direct match
        if quote in source:
            return True
        # Normalized match (handle whitespace differences)
        normalized_quote = " ".join(quote.split())
        normalized_source = " ".join(source.split())
        return normalized_quote in normalized_source
    
    @staticmethod
    def extract_candidate_turns(
        transcript_turns: list,
        turn_horizon: int | None = None,
    ) -> list[CandidateTurn]:
        """Extract candidate-authored turns from transcript context.
        
        Args:
            transcript_turns: Turns from SpecialistAssessmentContext.transcript_turns
            turn_horizon: Maximum turns to consider (default: 100)
            
        Returns:
            List of CandidateTurn objects for candidate-authored content
        """
        horizon = turn_horizon or EvidenceValidator.TURN_HORIZON_DEFAULT
        candidate_turns = []
        
        for idx, turn in enumerate(transcript_turns[:horizon]):
            # Handle both dict and object forms
            if isinstance(turn, dict):
                speaker = turn.get("speaker", "")
                turn_id = turn.get("id")
                text = turn.get("text", "")
            else:
                speaker = getattr(turn, "speaker", "")
                turn_id = getattr(turn, "id", None)
                text = getattr(turn, "text", "")
            
            try:
                turn_id = turn_id if isinstance(turn_id, UUID) else UUID(str(turn_id))
            except (TypeError, ValueError):
                continue
            if isinstance(speaker, str) and speaker.upper() == "CANDIDATE" and isinstance(text, str):
                candidate_turns.append(CandidateTurn(
                    id=turn_id,
                    speaker="CANDIDATE",
                    text=text,
                    turn_index=idx,
                ))
        
        return candidate_turns


def candidate_turns_from_rows(rows: list[dict] | None) -> list[CandidateTurn] | None:
    """Candidate turns from persisted turn rows; None means provenance cannot be established."""
    if rows is None:
        return None
    return EvidenceValidator.extract_candidate_turns(list(rows))


def assessment_evidence_is_verifiable(parsed, candidate_turns: list[CandidateTurn]) -> bool:
    """Deterministic B5 check for an already-stored specialist output (report/legacy path)."""
    nested = [
        {
            "evidence_turn_ids": item.evidence_turn_ids,
            "evidence_quotes": [{"turn_id": q.turn_id, "quote": q.quote} for q in item.evidence_quotes],
        }
        for item in [*parsed.dimensions, *parsed.competency_or_domain_assessments]
    ]
    try:
        EvidenceValidator().validate_assessment_output(
            evidence_turn_ids=list(parsed.evidence_turn_ids),
            evidence_quotes=[{"turn_id": q.turn_id, "quote": q.quote} for q in parsed.evidence_quotes],
            candidate_turns=candidate_turns,
            nested_assessments=nested,
        )
    except EvidenceValidationError:
        return False
    return True


def quote_is_verifiable(turn_id, quote: str, candidate_turns: list[CandidateTurn] | None) -> bool:
    """True only when `quote` appears in the candidate-authored turn `turn_id`."""
    if candidate_turns is None or turn_id is None:
        return False
    try:
        res = EvidenceValidator().validate_evidence_quotes([{"turn_id": turn_id, "quote": quote}], candidate_turns)
    except Exception:
        return False
    return res.is_valid and bool(res.valid_turn_ids)
