"""Role progress: scoped to one role and one person, never guessed, never a score."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.attempt_models import AttemptRecord
from app.claims_models import ClaimSource, ClaimStatus, EvidenceDirection
from app.copy_guard import find_banned
from app.dashboard_models import DashboardDiagnostic
from app.report_models import (
    ReportClaim,
    ReportClaimsAudit,
    ReportEvidence,
    ReportReadiness,
    ReportResponse,
    ReportSession,
    ReportSessionMoment,
    ReportSkillAssessment,
    ReportVerdict,
    SessionMomentType,
    TrustAndLimitations,
)
from app.report_service import ReportNotFound
from app.role_models import RoleProfileRead
from app.role_progress import (
    WINDOW,
    AnswerNotFound,
    AnswerState,
    ConnectionState,
    DevState,
    RoleProgressService,
    Seen,
    Stage,
    Trend,
    answer_signals,
    build_progress,
    eligible_practices,
    practice_items,
    question_index,
    tile_of,
)
from app.role_service import RoleProfileNotFoundForUser
from app.verdict_models import VerdictCode
from tests.test_interview_map import competency
from tests.test_interview_map import role as role_response

NOW = datetime.now(UTC)
USER, OTHER = uuid4(), uuid4()


def profile(user, name="Data Analyst"):
    return RoleProfileRead(id=uuid4(), user_id=user, target_role=name, source_type="JOB_DESCRIPTION", created_at=NOW, updated_at=NOW)


def session(role_id, *, days_ago, mode="FULL_INTERVIEW", focus=None, status="COMPLETED", available=True):
    moment = NOW - timedelta(days=days_ago)
    return DashboardDiagnostic(
        id=uuid4(), target_role="anything", role_profile_id=role_id, interview_status=status, phase="COMPLETE",
        created_at=moment, updated_at=moment, completed_at=moment, diagnostic_available=available,
        practice_mode=mode, practice_focus=focus,
    )


def evidence(turn, direction=EvidenceDirection.SUPPORTS, quote="I did it"):
    return ReportEvidence(turn_id=turn, quote=quote, direction=direction)


def claim(status, *turns, direction=EvidenceDirection.SUPPORTS):
    return ReportClaim(
        id=uuid4(), claim_text="Cut reporting time by half", source=ClaimSource.RESUME, status=status,
        explanation="An explanation.", evidence=[evidence(turn, direction) for turn in turns], confidence=0.8,
    )


def skill(name, signal, *turns, status="ASSESSED"):
    return ReportSkillAssessment(
        skill=name, status=status, signal_strength=signal, explanation="Reason.",
        evidence=[evidence(turn, EvidenceDirection.CONTEXT_ONLY) for turn in turns],
    )


def report(*, role=(70, 80), audit=None, skills=(), moments=(), root="ROLE_SKILL_GAP", shorter=False, days_ago=0):
    low, high = role if role else (None, None)
    readiness = ReportReadiness(low=low, high=high, label="Available" if role else "Not enough to say yet", signal_strength="MODERATE", confidence_note="note")
    return ReportResponse(
        session=ReportSession(target_role="Data Analyst", completed_at=NOW - timedelta(days=days_ago), duration_seconds=600, assessment_confidence=0.7),
        verdict=ReportVerdict(code=VerdictCode.DEVELOPING, label="Developing", summary="summary"),
        role_readiness=readiness, interview_readiness=readiness,
        claims_audit=audit or ReportClaimsAudit(),
        skill_assessments=list(skills), session_moments=list(moments), root_cause=root,
        trust_and_limitations=TrustAndLimitations(outcome_validation_status="NOT_VALIDATED"),
        shorter_conversation=shorter,
    )


def moment(kind, turn, quote="q"):
    return ReportSessionMoment(type=kind, turn_id=turn, quote=quote, explanation="From your conversation.")


def series(*reports_):
    """Practices oldest first, each with its report."""
    role = profile(USER)
    sessions = [session(role.id, days_ago=(len(reports_) - i) * 3) for i in range(len(reports_))]
    practices = practice_items(eligible_practices(sessions, frozenset({role.id})))
    return role, practices, {p.session_id: r for p, r in zip(practices, reports_)}


def dimension(result, key):
    return next(d for d in result.dimensions if d.key == key)


# ----------------------------------------------------------------- which practices count


def test_a_practice_belongs_to_its_bound_role_only() -> None:
    mine, other = profile(USER), profile(USER, "Product Manager")
    sessions = [session(mine.id, days_ago=2), session(other.id, days_ago=1), session(None, days_ago=1)]
    kept = eligible_practices(sessions, frozenset({mine.id}))
    assert [s.role_profile_id for s in kept] == [mine.id]


def test_unfinished_and_unreviewed_sessions_are_not_practices() -> None:
    role = profile(USER)
    sessions = [
        session(role.id, days_ago=3),
        session(role.id, days_ago=2, status="ACTIVE"),
        session(role.id, days_ago=1, available=False),
    ]
    assert len(eligible_practices(sessions, frozenset({role.id}))) == 1


def test_practices_are_numbered_oldest_first() -> None:
    role = profile(USER)
    kept = practice_items(eligible_practices([session(role.id, days_ago=1), session(role.id, days_ago=9)], frozenset({role.id})))
    assert [p.number for p in kept] == [1, 2] and kept[0].completed_at < kept[1].completed_at


def test_practice_modes_are_carried_through_for_history() -> None:
    role = profile(USER)
    drill = session(role.id, days_ago=1, mode="QUICK_DRILL", focus="impact")
    (item,) = practice_items(eligible_practices([drill], frozenset({role.id})), {drill.id: 4})
    assert (item.practice_mode, item.practice_focus, item.question_count) == ("QUICK_DRILL", "impact", 4)


# ----------------------------------------------------------------- stages


def test_zero_practices_is_an_empty_baseline_with_no_analytics() -> None:
    result = build_progress(profile(USER), [], {})
    assert result.stage == Stage.NONE and result.practice_count == 0 and result.last_practised_at is None
    assert all(d.state == DevState.NOT_EXPLORED and d.trend is None for d in result.dimensions)
    tile = tile_of(result)
    assert tile.positive is None and tile.attention is None


def test_one_practice_is_a_baseline_and_never_claims_a_trend() -> None:
    role, practices, reports = series(report(role=(90, 95)))
    result = build_progress(role, practices, reports)
    assert result.stage == Stage.BASELINE
    assert all(d.trend is None for d in result.dimensions)
    assert result.insights == []
    assert tile_of(result).positive.kind == "CLEAR"  # a state, never "improving"


def test_two_comparable_practices_can_show_movement() -> None:
    role, practices, reports = series(report(role=(10, 20)), report(role=(90, 95)))
    result = build_progress(role, practices, reports)
    assert result.stage == Stage.COMPARABLE
    understanding = dimension(result, "role_understanding")
    assert understanding.trend == Trend.MORE and understanding.current
    assert [i.dimension for i in result.insights] == ["role_understanding"]
    assert tile_of(result).positive.kind == "IMPROVING"


def test_a_decline_and_a_steady_area_are_reported_honestly() -> None:
    role, practices, reports = series(report(role=(90, 95)), report(role=(10, 15)))
    assert dimension(build_progress(role, practices, reports), "role_understanding").trend == Trend.LESS
    role, practices, reports = series(report(role=(90, 95)), report(role=(85, 95)))
    assert dimension(build_progress(role, practices, reports), "role_understanding").trend == Trend.SIMILAR


def test_tile_and_overview_read_the_same_trend() -> None:
    role, practices, reports = series(report(role=(90, 95)), report(role=(40, 45)))
    result = build_progress(role, practices, reports)
    assert dimension(result, "role_understanding").trend == Trend.LESS
    assert tile_of(result).attention.kind == "LESS"
    assert result.insights[0].trend == Trend.LESS


def test_a_short_conversation_is_shown_but_not_compared() -> None:
    role, practices, reports = series(report(role=(10, 20)), report(role=(90, 95), shorter=True))
    result = build_progress(role, practices, reports)
    assert result.stage == Stage.BASELINE  # only one comparable practice
    assert all(d.trend is None for d in result.dimensions)
    assert len(result.dimensions[0].cells) == 2  # still drawn in the timeline
    assert next(p for p in result.practices if p.number == 2).shorter_conversation is True


def test_an_early_ended_practice_never_drives_an_area_state() -> None:
    role, practices, reports = series(report(role=(10, 15), shorter=True))
    result = build_progress(role, practices, reports)
    assert dimension(result, "role_understanding").state == DevState.NOT_EXPLORED
    tile = tile_of(result)
    assert tile.attention is None and tile.positive is None


def test_practices_that_cannot_be_read_are_a_baseline_not_no_practice() -> None:
    role, practices, _ = series(report())
    result = build_progress(role, practices, {})
    assert result.stage == Stage.BASELINE and result.practice_count == 1


def test_only_the_newest_window_is_read() -> None:
    role, practices, reports = series(*[report() for _ in range(WINDOW + 2)])
    result = build_progress(role, practices, reports)
    assert result.practice_count == WINDOW + 2
    assert len(result.dimensions[0].cells) == WINDOW
    assert len(result.practices) == WINDOW + 2  # history still lists every practice


# ----------------------------------------------------------------- not explored is not weak


def test_an_area_a_practice_did_not_touch_is_never_a_decline() -> None:
    """A quick drill on one thing: no evidence for impact must not read as impact getting worse."""
    strong_impact = report(moments=[moment(SessionMomentType.OWNERSHIP_CLARIFICATION, uuid4())])
    drill = report()  # says nothing about impact
    role, practices, reports = series(strong_impact, drill)
    impact = dimension(build_progress(role, practices, reports), "impact")
    assert impact.cells[1].state == DevState.NOT_EXPLORED
    assert impact.trend is None  # only one explored practice, so nothing to compare
    assert impact.state == DevState.COMING_THROUGH  # the newest evidence there is


def test_not_explored_has_no_counts_and_never_becomes_attention() -> None:
    role, practices, reports = series(report(role=None))
    result = build_progress(role, practices, reports)
    understanding = dimension(result, "role_understanding")
    assert understanding.state == DevState.NOT_EXPLORED and understanding.cells[0].answers_seen == 0
    attention = tile_of(result).attention
    assert attention is None or attention.dimension != "role_understanding"


def test_comparison_skips_a_practice_that_did_not_explore_the_area() -> None:
    role, practices, reports = series(report(role=(10, 15)), report(role=None), report(role=(90, 95)))
    understanding = dimension(build_progress(role, practices, reports), "role_understanding")
    assert understanding.trend == Trend.MORE
    assert understanding.compared_with == practices[0].completed_at  # compared with practice 1, not the drill


def test_a_trend_that_ended_before_the_newest_practice_is_not_a_since_last_insight() -> None:
    role, practices, reports = series(report(role=(10, 15)), report(role=(90, 95)), report(role=None))
    result = build_progress(role, practices, reports)
    understanding = dimension(result, "role_understanding")
    assert understanding.trend == Trend.MORE and not understanding.current
    assert result.insights == []


def test_at_most_three_insights() -> None:
    def full(role_range, root):
        return report(role=role_range, root=root, moments=[moment(SessionMomentType.OWNERSHIP_CLARIFICATION, uuid4())])

    role, practices, reports = series(full((10, 15), "ROLE_SKILL_GAP"), full((90, 95), "ROLE_SKILL_GAP"))
    assert len(build_progress(role, practices, reports).insights) <= 3


# ----------------------------------------------------------------- answers behind the areas


def test_claim_evidence_becomes_answer_signals_in_the_right_direction() -> None:
    good, gap = uuid4(), uuid4()
    audit = ReportClaimsAudit(
        held=[claim(ClaimStatus.CORROBORATED, good)],
        partially_held=[claim(ClaimStatus.PARTIALLY_HELD, gap, direction=EvidenceDirection.WEAKENS)],
    )
    signals = answer_signals(report(audit=audit))
    assert signals[good][0].dimension == "examples" and signals[good][0].state == AnswerState.STRONG
    assert signals[gap][0].state == AnswerState.NEEDS_PRACTICE


def test_context_only_evidence_says_nothing() -> None:
    audit = ReportClaimsAudit(held=[claim(ClaimStatus.CORROBORATED, uuid4(), direction=EvidenceDirection.CONTEXT_ONLY)])
    assert answer_signals(report(audit=audit)) == {}


def test_moments_map_to_impact_and_depth() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    signals = answer_signals(report(moments=[
        moment(SessionMomentType.OWNERSHIP_CLARIFICATION, a),
        moment(SessionMomentType.UNSUPPORTED_SCALE, b),
        moment(SessionMomentType.TECHNICAL_DEPTH, c),
    ]))
    assert (signals[a][0].dimension, signals[a][0].state) == ("impact", AnswerState.STRONG)
    assert (signals[b][0].dimension, signals[b][0].state) == ("impact", AnswerState.NEEDS_PRACTICE)
    assert (signals[c][0].dimension, signals[c][0].state) == ("depth", AnswerState.STRONG)


def test_skill_evidence_needs_a_real_assessment_and_a_real_turn() -> None:
    turn = uuid4()
    signals = answer_signals(report(skills=[
        skill("SQL", "WEAK", turn),
        skill("Python", "STRONG", uuid4(), status="NOT_ENOUGH_SIGNAL"),
    ]))
    assert set(signals) == {turn}
    assert {s.dimension for s in signals[turn]} == {"role_understanding", "depth"}
    assert all(s.state == AnswerState.NEEDS_PRACTICE for s in signals[turn])


def test_mixed_evidence_is_present_and_shows_the_gap() -> None:
    turn = uuid4()
    audit = ReportClaimsAudit(
        held=[claim(ClaimStatus.CORROBORATED, turn)],
        contradicted=[claim(ClaimStatus.CONTRADICTED, turn, direction=EvidenceDirection.WEAKENS)],
    )
    (signal,) = answer_signals(report(audit=audit))[turn]
    assert signal.state == AnswerState.PRESENT


def test_counts_only_count_answers_the_review_spoke_to() -> None:
    turns = [uuid4() for _ in range(3)]
    audit = ReportClaimsAudit(
        held=[claim(ClaimStatus.CORROBORATED, turns[0], turns[1])],
        partially_held=[claim(ClaimStatus.PARTIALLY_HELD, turns[2], direction=EvidenceDirection.WEAKENS)],
    )
    role, practices, reports = series(report(audit=audit))
    cell = dimension(build_progress(role, practices, reports), "examples").cells[0]
    assert cell.state != DevState.NOT_EXPLORED
    assert (cell.answers_seen, cell.answers_strong) == (3, 2)


def turn(idx, speaker, text, turn_id=None):
    return SimpleNamespace(id=turn_id or uuid4(), turn_index=idx, speaker=speaker, text=text)


def test_questions_pair_with_the_answer_that_followed_and_are_numbered() -> None:
    a1, a2 = uuid4(), uuid4()
    turns = [
        turn(0, "INTERVIEWER", "Tell me about yourself"), turn(1, "CANDIDATE", "I analyse data", a1),
        turn(2, "INTERVIEWER", "Why that metric?"), turn(3, "CANDIDATE", "Because retention", a2),
        turn(4, "INTERVIEWER", "Any last thing?"),
    ]
    found = question_index(turns)
    assert found[a2].text == "Why that metric?" and (found[a2].position, found[a2].total) == (2, 2)
    assert found[a1].answer == "I analyse data"


def test_answer_rows_need_the_question_and_come_newest_first() -> None:
    a, b = uuid4(), uuid4()
    first = report(moments=[moment(SessionMomentType.OWNERSHIP_CLARIFICATION, a)])
    second = report(moments=[moment(SessionMomentType.UNSUPPORTED_SCALE, b)])
    role, practices, reports = series(first, second)
    questions = {
        practices[0].session_id: question_index([turn(0, "INTERVIEWER", "Q1"), turn(1, "CANDIDATE", "A1", a)]),
        practices[1].session_id: question_index([turn(0, "INTERVIEWER", "Q2"), turn(1, "CANDIDATE", "A2", b)]),
    }
    result = build_progress(role, practices, reports, questions=questions)
    assert [(x.question, x.practice_number) for x in result.answers] == [("Q2", 2), ("Q1", 1)]
    assert build_progress(role, practices, reports, questions={}).answers == []  # no question, no row


# ----------------------------------------------------------------- role connection


def test_role_connection_counts_practices_that_spoke_to_each_area() -> None:
    one, two = uuid4(), uuid4()
    role_read = role_response([competency("Data analysis"), competency("Experimentation")])
    role, practices, reports = series(
        report(skills=[skill("Data analysis", "STRONG", one)]),
        report(skills=[skill("Data analysis", "MODERATE", two)]),
    )
    connection = build_progress(role, practices, reports, role=role_read).connection
    assert connection.state == ConnectionState.READY
    by_name = {area.name: area for area in connection.areas}
    assert by_name["Data analysis"].seen == Seen.REPEATEDLY and len(by_name["Data analysis"].answers) == 2
    assert by_name["Experimentation"].seen == Seen.NOT_EXPLORED and by_name["Experimentation"].answers == []


def test_role_connection_ignores_assessments_with_no_answer_behind_them() -> None:
    role_read = role_response([competency("Data analysis")])
    role, practices, reports = series(report(skills=[skill("Data analysis", "STRONG")]))
    assert build_progress(role, practices, reports, role=role_read).connection.areas[0].seen == Seen.NOT_EXPLORED


def test_role_connection_states_when_the_role_is_still_being_read() -> None:
    role, practices, reports = series(report())
    preparing = build_progress(role, practices, reports, role=role_response([], status="PROCESSING"))
    assert preparing.connection.state == ConnectionState.PREPARING
    assert build_progress(role, practices, reports).connection.state == ConnectionState.UNAVAILABLE


# ----------------------------------------------------------------- no numbers, no banned words


def test_nothing_shown_to_the_candidate_is_a_score() -> None:
    role, practices, reports = series(report(role=(10, 20)), report(role=(90, 95)))
    result = build_progress(role, practices, reports)
    payload = result.model_dump_json()
    assert "readiness" not in payload and "score" not in payload
    for note in [d.note or "" for d in result.dimensions]:
        assert not find_banned(note)


# ----------------------------------------------------------------- the service: ownership


class FakeRoles:
    def __init__(self, by_user):
        self.by_user = by_user  # user -> list[(profile, ids)]

    async def families(self, user_id):
        return self.by_user.get(user_id, [])

    async def get(self, profile_id, user_id):
        for known, _ in self.by_user.get(user_id, []):
            if known.id == profile_id:
                base = role_response([competency("Data analysis")])
                return base.model_copy(update={"id": known.id, "user_id": user_id, "target_role": known.target_role})
        raise RoleProfileNotFoundForUser


class FakeDashboard:
    def __init__(self, by_user):
        self.by_user = by_user

    async def sessions(self, user_id, limit=100):
        return self.by_user.get(user_id, [])


class FakeReports:
    def __init__(self, reports):
        self.reports = reports

    async def get_report(self, session_id, user_id):
        if session_id not in self.reports:
            raise ReportNotFound
        return self.reports[session_id]


class FakeTranscript:
    def __init__(self, turns_by_session, owner):
        self.turns, self.owner = turns_by_session, owner

    async def list_public_turns(self, session_id, user_id):
        if user_id != self.owner.get(session_id):
            raise ReportNotFound
        return self.turns.get(session_id, [])


class FakeAttempts:
    def __init__(self, rows=()):
        self.rows = list(rows)

    async def list_for_session(self, session_id, user_id):
        return [row for row in self.rows if row.session_id == session_id and row.user_id == user_id]


def world():
    """Two people; one has Data Analyst (with an older duplicate profile) and Product Manager."""
    analyst_old, analyst, manager = profile(USER), profile(USER), profile(USER, "Product Manager")
    theirs = profile(OTHER)
    answer_a, answer_b = uuid4(), uuid4()
    s_old = session(analyst_old.id, days_ago=6)
    s_new = session(analyst.id, days_ago=3)
    s_manager = session(manager.id, days_ago=1)
    s_other = session(theirs.id, days_ago=2)
    reports = {
        s_old.id: report(moments=[moment(SessionMomentType.OWNERSHIP_CLARIFICATION, answer_a)]),
        s_new.id: report(moments=[moment(SessionMomentType.UNSUPPORTED_SCALE, answer_b)]),
        s_manager.id: report(role=(10, 15)),
        s_other.id: report(role=(10, 15)),
    }
    turns = {
        s_old.id: [turn(0, "INTERVIEWER", "Old question"), turn(1, "CANDIDATE", "Old answer", answer_a)],
        s_new.id: [turn(0, "INTERVIEWER", "Why those metrics?"), turn(1, "CANDIDATE", "Because retention", answer_b)],
    }
    owner = {s_old.id: USER, s_new.id: USER, s_manager.id: USER, s_other.id: OTHER}
    roles = FakeRoles({
        USER: [(analyst, frozenset({analyst.id, analyst_old.id})), (manager, frozenset({manager.id}))],
        OTHER: [(theirs, frozenset({theirs.id}))],
    })
    attempt = AttemptRecord(
        id=uuid4(), user_id=USER, session_id=s_new.id, question_turn_id=uuid4(), original_turn_id=answer_b, sequence=1,
        question_text="Why those metrics?", original_answer="Because retention", answer_text="Because retention, and here is why",
        created_at=NOW,
    )
    service = RoleProgressService(
        roles,
        FakeDashboard({USER: [s_manager, s_new, s_old], OTHER: [s_other]}),
        FakeReports(reports),
        FakeTranscript(turns, owner),
        FakeAttempts([attempt]),
    )
    return SimpleNamespace(
        service=service, analyst=analyst, analyst_old=analyst_old, manager=manager, theirs=theirs,
        s_old=s_old, s_new=s_new, s_manager=s_manager, s_other=s_other, answer_a=answer_a, answer_b=answer_b,
    )


@pytest.mark.asyncio
async def test_hub_gives_one_tile_per_role_and_keeps_roles_apart() -> None:
    w = world()
    hub = await w.service.hub(USER)
    tiles = {tile.target_role: tile for tile in hub.roles}
    assert set(tiles) == {"Data Analyst", "Product Manager"}
    assert tiles["Data Analyst"].practice_count == 2  # includes the older duplicate profile, nothing from other roles
    assert tiles["Product Manager"].practice_count == 1
    assert all(tile.role_profile_id != w.theirs.id for tile in hub.roles)


@pytest.mark.asyncio
async def test_hub_lists_a_role_with_no_practice_as_empty_and_last() -> None:
    w = world()
    fresh = profile(USER, "Designer")
    w.service._roles.by_user[USER].append((fresh, frozenset({fresh.id})))
    hub = await w.service.hub(USER)
    tile = next(t for t in hub.roles if t.target_role == "Designer")
    assert tile.stage == Stage.NONE and tile.practice_count == 0 and tile.last_practised_at is None
    assert hub.roles[-1].target_role == "Designer"  # roles with practice come first


@pytest.mark.asyncio
async def test_role_detail_only_contains_that_roles_practices_and_answers() -> None:
    w = world()
    detail = await w.service.detail(w.analyst.id, USER)
    assert detail.practice_count == 2 and detail.stage == Stage.COMPARABLE
    assert {p.session_id for p in detail.practices} == {w.s_old.id, w.s_new.id}
    assert {a.answer_turn_id for a in detail.answers} == {w.answer_a, w.answer_b}
    assert w.s_manager.id not in {p.session_id for p in detail.practices}


@pytest.mark.asyncio
async def test_an_older_duplicate_profile_opens_the_same_role() -> None:
    w = world()
    detail = await w.service.detail(w.analyst_old.id, USER)
    assert detail.role_profile_id == w.analyst.id and detail.practice_count == 2


@pytest.mark.asyncio
async def test_another_users_role_is_not_found() -> None:
    w = world()
    with pytest.raises(RoleProfileNotFoundForUser):
        await w.service.detail(w.theirs.id, USER)
    with pytest.raises(RoleProfileNotFoundForUser):
        await w.service.detail(w.analyst.id, OTHER)
    with pytest.raises(RoleProfileNotFoundForUser):
        await w.service.detail(uuid4(), USER)  # a role that does not exist


@pytest.mark.asyncio
async def test_hub_never_includes_another_users_roles() -> None:
    w = world()
    assert {t.role_profile_id for t in (await w.service.hub(OTHER)).roles} == {w.theirs.id}


@pytest.mark.asyncio
async def test_answer_detail_returns_the_question_answer_signals_and_retries() -> None:
    w = world()
    detail = await w.service.answer(w.analyst.id, w.s_new.id, w.answer_b, USER)
    assert (detail.question, detail.answer) == ("Why those metrics?", "Because retention")
    assert (detail.question_position, detail.question_total, detail.practice_number) == (1, 1, 2)
    assert detail.signals[0].dimension == "impact" and detail.signals[0].state == AnswerState.NEEDS_PRACTICE
    assert len(detail.attempts) == 1 and detail.attempts[0].answer_text.endswith("here is why")


@pytest.mark.asyncio
async def test_answer_detail_refuses_another_roles_practice_and_another_users_answer() -> None:
    w = world()
    with pytest.raises(AnswerNotFound):
        await w.service.answer(w.analyst.id, w.s_manager.id, w.answer_b, USER)  # a different role's practice
    with pytest.raises(RoleProfileNotFoundForUser):
        await w.service.answer(w.analyst.id, w.s_new.id, w.answer_b, OTHER)  # someone else's role
    with pytest.raises(AnswerNotFound):
        await w.service.answer(w.theirs.id, w.s_new.id, w.answer_b, OTHER)  # their role, my session
    with pytest.raises(AnswerNotFound):
        await w.service.answer(w.analyst.id, w.s_new.id, uuid4(), USER)  # not an answer in that practice


@pytest.mark.asyncio
async def test_an_unreadable_review_is_left_out_not_guessed() -> None:
    w = world()
    del w.service._reports.reports[w.s_old.id]
    detail = await w.service.detail(w.analyst.id, USER)
    assert detail.practice_count == 2  # the practice still exists in history
    assert len(detail.dimensions[0].cells) == 1  # but contributes no evidence
    assert detail.stage == Stage.BASELINE
