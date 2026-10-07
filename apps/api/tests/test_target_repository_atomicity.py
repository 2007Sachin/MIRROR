"""The in-memory target repository is atomic like the database it stands in for.

PostgreSQL rejects the losing writer of a racing batch insert or link insert through unique
constraints inside one transaction. The memory double must behave the same, or concurrent
route tests see states the real database can never produce (two copies of one prompt set).
"""
from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from uuid import uuid4

from app.target_repository import (
    BlueprintPin,
    LinkAlreadyExists,
    MemoryTargetRepository,
    QuestionCreate,
    TargetConflict,
    TargetSessionLinkCreate,
    TargetValues,
)


def _world():
    repo = MemoryTargetRepository()
    user = uuid4()
    target = asyncio.run(repo.create_target(user, TargetValues(
        role_profile_id=uuid4(), company_label="QA Consulting Co (synthetic)", company_key="qa_consulting",
        role_family_key="business_analysis", level_key="consultant", level_label=None,
        geography_key="qa_land", geography_label="QA Fictional Country", interview_date=None,
    )))
    blueprint = asyncio.run(repo.create_blueprint(user, target.id, BlueprintPin(
        catalog_version=1, catalog_sha256="0" * 64, match_state="NOT_RESEARCHED", rules_version="blueprint-1",
    )))
    set_id = uuid4()
    rows = tuple(QuestionCreate(
        candidate_target_id=target.id, blueprint_id=blueprint.id, prompt_set_id=set_id, position=i,
        round_key="business_problem_solving", competency_key="structured_problem_solving", family_key="profit_diagnosis",
        template_id=f"case.qa_{i}", generator_version="round-pack-1", originality_rules_version="originality-1",
        question_text=f"Synthetic case prompt number {i} about a fictional bakery chain.", rationale_code="MIRROR_SUGGESTED",
        derived_from={}, novelty_sha256=f"{i:x}" * 64,
    ) for i in range(1, 5))
    link = TargetSessionLinkCreate(
        session_id=uuid4(), candidate_target_id=target.id, blueprint_id=blueprint.id, round_key="business_problem_solving",
        competency_key=None, prompt_set_id=set_id, prompt_set_state="PENDING", expected_prompt_count=4, prompt_manifest=rows,
    )
    return repo, user, link, rows


def _race(repo, call):
    """Run ``call`` in two threads (each with its own event loop) that both pass every await first."""
    rendezvous = threading.Barrier(2)
    original = repo._owned_target

    async def owned_then_wait(*args, **kwargs):
        result = await original(*args, **kwargs)
        rendezvous.wait(timeout=10)
        return result

    repo._owned_target = owned_then_wait
    outcomes: list[object] = [None, None]

    def worker(index):
        try:
            outcomes[index] = asyncio.run(call())
        except Exception as exc:  # noqa: BLE001 - the outcome is what the test inspects
            outcomes[index] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    repo._owned_target = original
    return outcomes


class _MeetAtInsert(list):
    """A question list whose batch insert waits briefly for the other writer to arrive too.

    Without atomic insert both writers meet here and both write; with it, the second writer is
    held outside the critical section, the wait times out and only one batch is written.
    """

    def __init__(self, items):
        super().__init__(items)
        self.meet = threading.Barrier(2)

    def extend(self, items):
        try:
            self.meet.wait(timeout=1)
        except threading.BrokenBarrierError:
            pass
        super().extend(items)


def test_racing_batch_inserts_store_one_prompt_set_and_the_loser_gets_a_conflict():
    repo, user, link, rows = _world()
    asyncio.run(repo.create_link(user, link))
    repo.questions = _MeetAtInsert(repo.questions)
    outcomes = _race(repo, lambda: repo.record_questions(user, rows))
    assert link.prompt_set_id is not None
    stored = asyncio.run(repo.questions_for_set(link.prompt_set_id, user))
    assert [q.position for q in stored] == [1, 2, 3, 4]
    assert sum(isinstance(o, TargetConflict) for o in outcomes) == 1
    assert sum(isinstance(o, list) for o in outcomes) == 1


def test_racing_link_inserts_keep_one_link_and_the_loser_sees_it():
    repo, user, link, _rows = _world()
    outcomes = _race(repo, lambda: repo.create_link(user, link))
    assert len(repo.links) == 1
    losers = [o for o in outcomes if isinstance(o, Exception)]
    assert len(losers) == 1 and isinstance(losers[0], LinkAlreadyExists) and losers[0].link is not None
    assert datetime.now(UTC) >= next(iter(repo.links.values())).created_at
