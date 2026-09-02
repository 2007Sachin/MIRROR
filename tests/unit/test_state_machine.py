from app.schemas import Phase, TurnType
from app.state_machine import InterviewState, PendingFlag


def test_flag_is_one_turn_late() -> None:
    state = InterviewState(current_turn=4)
    flag = PendingFlag(
        id="f1",
        detected_at_turn=4,
        consumed=False,
        severity=3,
        suggested_probe="Clarify ownership",
    )
    assert state.eligible_flags([flag], skeptic_mode="active") == []
    state.current_turn = 5
    assert state.eligible_flags([flag], skeptic_mode="active") == [flag]


def test_shadow_mode_never_exposes_flags() -> None:
    state = InterviewState(current_turn=5)
    flag = PendingFlag(
        id="f1",
        detected_at_turn=2,
        consumed=False,
        severity=3,
        suggested_probe="Clarify ownership",
    )
    assert state.eligible_flags([flag], skeptic_mode="shadow") == []


def test_probe_cap_recovers_after_two_probes() -> None:
    state = InterviewState(probes_in_thread=2)
    result = state.next_turn_type(
        flags=[],
        depth_probe_required=True,
        strong_answer=False,
        planned_questions_remaining=True,
    )
    assert result == TurnType.RECOVERY
    assert state.probes_in_thread == 0


def test_phase_progression_is_deterministic() -> None:
    state = InterviewState(phase=Phase.INTRO)
    assert state.advance_phase() == Phase.BACKGROUND

