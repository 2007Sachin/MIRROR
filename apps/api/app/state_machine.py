from __future__ import annotations

from dataclasses import dataclass

from .schemas import Phase, TurnType


PHASE_ORDER = (
    Phase.INTRO,
    Phase.BACKGROUND,
    Phase.PROJECTS,
    Phase.ROLE_CORE,
    Phase.DEEP_DIVE,
    Phase.BEHAVIOURAL,
    Phase.CLOSING,
    Phase.COMPLETE,
)


@dataclass(frozen=True)
class PendingFlag:
    id: str
    detected_at_turn: int
    consumed: bool
    severity: int
    suggested_probe: str


@dataclass
class InterviewState:
    phase: Phase = Phase.INTRO
    current_turn: int = 0
    planned_question_index: int = 0
    probes_in_thread: int = 0
    elapsed_seconds: int = 0
    duration_seconds: int = 1_200

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.duration_seconds - self.elapsed_seconds)

    def eligible_flags(
        self, flags: list[PendingFlag], *, skeptic_mode: str
    ) -> list[PendingFlag]:
        if skeptic_mode != "active":
            return []
        return sorted(
            (
                flag
                for flag in flags
                if not flag.consumed and flag.detected_at_turn < self.current_turn
            ),
            key=lambda flag: (-flag.severity, flag.detected_at_turn),
        )

    def next_turn_type(
        self,
        *,
        flags: list[PendingFlag],
        depth_probe_required: bool,
        strong_answer: bool,
        planned_questions_remaining: bool,
        skeptic_mode: str = "shadow",
    ) -> TurnType:
        if (
            self.eligible_flags(flags, skeptic_mode=skeptic_mode)
            and self.probes_in_thread < 2
        ):
            self.probes_in_thread += 1
            return TurnType.CONTRADICTION_PROBE
        if depth_probe_required and self.probes_in_thread < 2:
            self.probes_in_thread += 1
            return TurnType.DEPTH_PROBE
        if strong_answer and self.probes_in_thread < 2:
            self.probes_in_thread += 1
            return TurnType.LADDER_UP
        if self.probes_in_thread >= 2 and (
            depth_probe_required
            or self.eligible_flags(flags, skeptic_mode=skeptic_mode)
        ):
            self.probes_in_thread = 0
            return TurnType.RECOVERY
        if planned_questions_remaining:
            self.planned_question_index += 1
            self.probes_in_thread = 0
            return TurnType.PLANNED
        if self.phase not in (Phase.CLOSING, Phase.COMPLETE):
            self.advance_phase()
            return TurnType.TRANSITION
        return TurnType.CLOSING

    def advance_phase(self) -> Phase:
        current_index = PHASE_ORDER.index(self.phase)
        if current_index < len(PHASE_ORDER) - 1:
            self.phase = PHASE_ORDER[current_index + 1]
        return self.phase

    def should_complete(self) -> bool:
        return self.phase == Phase.COMPLETE or self.remaining_seconds == 0

