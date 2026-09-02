from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.flag_activation import EligibleFlagCandidate, FlagEligibilityService
from app.interviewer_models import InterviewerTurnType
from app.skeptic_models import ObservationType, SkepticSeverity


SESSION_ID = UUID("a1000000-0000-4000-8000-000000000001")
USER_ID = UUID("a2000000-0000-4000-8000-000000000002")
CLAIM_ID = UUID("a3000000-0000-4000-8000-000000000003")


def flag(**changes) -> EligibleFlagCandidate:
    values = {
        "id": uuid4(),
        "claim_id": CLAIM_ID,
        "flag_type": ObservationType.OWNERSHIP_DRIFT,
        "severity": SkepticSeverity.HIGH,
        "confidence": 0.91,
        "reason": "Personal ownership changed across two answers.",
        "suggested_probe": "What part did you personally implement?",
        "detected_at_turn": 3,
        "created_at": datetime.now(UTC) - timedelta(minutes=1),
        "claim_summary": "I built the analytics backend.",
        "claim_verification_priority": "HIGH",
    }
    values.update(changes)
    return EligibleFlagCandidate(**values)


class MemoryFlags:
    def __init__(self, *flags: EligibleFlagCandidate) -> None:
        self.flags = list(flags)
        self.consumptions: list[tuple] = []

    async def list_eligible(self, *args):
        return list(self.flags)

    async def consume(self, *args):
        flag_id, _, _, current_turn, interviewer_turn_id, min_confidence, allow_shadow = args
        current = next((item for item in self.flags if item.id == flag_id), None)
        if (
            current is None
            or current.consumed
            or not current.safe_to_surface
            or current.disputed
            or current.resolved_at is not None
            or current.detected_at_turn >= current_turn
            or current.confidence < min_confidence
            or (current.shadow_mode and not allow_shadow)
        ):
            return False
        self.flags[self.flags.index(current)] = current.model_copy(update={"consumed": True})
        self.consumptions.append((flag_id, current_turn, interviewer_turn_id))
        return True


def service(repository: MemoryFlags, *, live=True, shadow=False, threshold=0.8):
    return FlagEligibilityService(
        repository,
        live_probes=live,
        shadow_mode=shadow,
        min_confidence=threshold,
    )


def select(checker, *, turn=5, active=True, probes=0, relevant=None):
    return asyncio.run(
        checker.select(
            SESSION_ID,
            USER_ID,
            turn,
            session_active=active,
            probe_count=probes,
            relevant_claim_ids=relevant or [],
        )
    )


def test_same_turn_flag_never_appears_but_next_turn_can():
    repository = MemoryFlags(flag(detected_at_turn=5))
    checker = service(repository)
    assert select(checker, turn=5) is None
    assert select(checker, turn=6).flag_id == repository.flags[0].id


def test_late_async_flag_can_appear_on_a_later_turn_without_waiting():
    repository = MemoryFlags()
    checker = service(repository)
    assert select(checker, turn=6) is None
    repository.flags.append(flag(detected_at_turn=5))
    assert select(checker, turn=8) is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"confidence": 0.79},
        {"safe_to_surface": False},
        {"consumed": True},
        {"disputed": True},
        {"resolved_at": datetime.now(UTC)},
    ],
)
def test_ineligible_flags_are_blocked(changes):
    assert select(service(MemoryFlags(flag(**changes)))) is None


def test_shadow_only_inactive_session_and_probe_cap_block_activation():
    candidate = flag(shadow_mode=True)
    assert select(service(MemoryFlags(candidate), shadow=True)) is None
    assert select(service(MemoryFlags(candidate), live=False)) is None
    assert select(service(MemoryFlags(candidate)), active=False) is None
    assert select(service(MemoryFlags(candidate)), probes=2) is None


def test_multiple_flags_use_deterministic_business_priority():
    old_low = flag(
        severity=SkepticSeverity.LOW,
        confidence=0.99,
        created_at=datetime.now(UTC) - timedelta(days=1),
    )
    high_irrelevant = flag(claim_id=uuid4(), confidence=0.92)
    high_relevant = flag(confidence=0.92, claim_verification_priority="HIGH")
    chosen = select(
        service(MemoryFlags(old_low, high_irrelevant, high_relevant)),
        relevant=[CLAIM_ID],
    )
    assert chosen.flag_id == high_relevant.id
    assert chosen.recommended_turn_type == InterviewerTurnType.CONTRADICTION_PROBE


def test_unsupported_scale_uses_depth_probe():
    chosen = select(
        service(MemoryFlags(flag(flag_type=ObservationType.UNSUPPORTED_SCALE)))
    )
    assert chosen.recommended_turn_type == InterviewerTurnType.DEPTH_PROBE


def test_conditional_consumption_is_single_use_and_audited():
    repository = MemoryFlags(flag())
    checker = service(repository)
    chosen = select(checker)
    interviewer_turn_id = uuid4()
    assert asyncio.run(
        checker.consume(chosen.flag_id, SESSION_ID, USER_ID, 5, interviewer_turn_id)
    )
    assert not asyncio.run(
        checker.consume(chosen.flag_id, SESSION_ID, USER_ID, 5, uuid4())
    )
    assert repository.consumptions == [(chosen.flag_id, 5, interviewer_turn_id)]
    assert select(checker) is None


def test_p6_coasting_contributor_surfaces_neutral_ownership_probe():
    candidate = flag(
        flag_type=ObservationType.OWNERSHIP_DRIFT,
        reason=(
            "Resume says the candidate built the backend; later they said a teammate "
            "designed it and they integrated APIs."
        ),
        suggested_probe="What part of the backend did you personally implement?",
    )
    chosen = select(service(MemoryFlags(candidate)))
    assert chosen.flag_type == "OWNERSHIP_DRIFT"
    assert chosen.suggested_probe == "What part of the backend did you personally implement?"
    assert "lied" not in chosen.suggested_probe.casefold()
    assert "contradicted" not in chosen.suggested_probe.casefold()


def test_database_contract_enforces_one_turn_late_and_audited_consumption():
    sql = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "202609010013_skeptic_flag_activation.sql"
    ).read_text(encoding="utf-8").casefold()
    assert "f.detected_at_turn < p_current_candidate_turn_index" in sql
    assert "consumed_at_turn" in sql
    assert "interviewer_turn_id" in sql
    assert "update public.flags f" in sql
    assert "s.status::text = 'active'" in sql
    assert "to service_role" in sql

