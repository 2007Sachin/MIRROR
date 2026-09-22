"""Continue-later: pausing freezes the interview clock and resuming continues from it."""

import asyncio

from app.interviewer_models import InterviewerDecision
from app.schemas import SessionStatus
from tests.test_interview_engine import USER_A, active_session, make_engine


def test_pause_freezes_the_timer_and_resume_continues_from_it() -> None:
    engine, _, clock = make_engine(duration=1200)

    async def go():
        session = await active_session(engine)
        clock.advance(120)
        paused = await engine.pause(session.id, USER_A)
        assert engine.is_paused(paused) and paused.status == SessionStatus.ACTIVE
        assert paused.elapsed_seconds == 120
        clock.advance(3600)  # a long time away must not count
        _, remaining_paused = engine.remaining_times(paused)
        resumed = await engine.resume(session.id, USER_A)
        _, remaining = engine.remaining_times(resumed)
        return remaining_paused, remaining, engine.is_paused(resumed)

    remaining_paused, remaining, still_paused = asyncio.run(go())
    assert remaining_paused == 1080 and remaining == 1080 and not still_paused


def test_phase_clock_also_resumes_where_it_stopped() -> None:
    engine, _, clock = make_engine()

    async def go():
        session = await active_session(engine)
        clock.advance(60)
        await engine.pause(session.id, USER_A)
        clock.advance(900)
        resumed = await engine.resume(session.id, USER_A)
        phase_remaining, _ = engine.remaining_times(resumed)
        return phase_remaining

    assert asyncio.run(go()) == 120  # 180 s phase budget minus the 60 s already spent


def test_pause_and_resume_are_safe_to_repeat() -> None:
    engine, _, clock = make_engine()

    async def go():
        session = await active_session(engine)
        clock.advance(30)
        first = await engine.pause(session.id, USER_A)
        second = await engine.pause(session.id, USER_A)
        await engine.resume(session.id, USER_A)
        again = await engine.resume(session.id, USER_A)
        return first.elapsed_seconds, second.elapsed_seconds, engine.is_paused(again)

    assert asyncio.run(go()) == (30, 30, False)


def test_phase_request_is_ignored_on_a_normal_question() -> None:
    decision = InterviewerDecision.model_validate({
        "action": "ASK", "question_text": "Could you tell me more about that?", "turn_type": "DEPTH_PROBE",
        "target_claim_ids": [], "target_competency_ids": [], "primary_thread_id": "obj-1",
        "reason_code": "OBJECTIVE_COMPLETE", "requested_phase_transition": "BACKGROUND", "used_flag_id": None,
    })
    assert decision.requested_phase_transition is None


def test_time_away_without_saving_is_not_counted_against_the_interview() -> None:
    engine, repo, clock = make_engine(duration=1200)

    async def go():
        session = await active_session(engine)
        clock.advance(60)
        event = await engine.record_event(session.id, USER_A, "TEXT_TURN_COMPLETED", {})
        repo.events[session.id] = [e.model_copy(update={"created_at": clock.now}) for e in repo.events[session.id]]
        clock.advance(4800)  # the tab was left open for 80 minutes
        back = await engine.credit_idle_time(session.id, USER_A, idle_seconds=300)
        _, remaining = engine.remaining_times(back)
        return remaining

    remaining = asyncio.run(go())
    assert remaining == 1200 - 60  # only the first minute counts; the 80 minutes away do not


def test_a_short_gap_is_left_alone() -> None:
    engine, repo, clock = make_engine(duration=1200)

    async def go():
        session = await active_session(engine)
        event = await engine.record_event(session.id, USER_A, "TEXT_TURN_COMPLETED", {})
        repo.events[session.id] = [e.model_copy(update={"created_at": clock.now}) for e in repo.events[session.id]]
        clock.advance(120)
        back = await engine.credit_idle_time(session.id, USER_A, idle_seconds=300)
        return back.started_at == session.started_at

    assert asyncio.run(go()) is True
