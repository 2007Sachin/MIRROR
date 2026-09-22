"""Pressure test: questions traceable to the statement, readiness owner-scoped, checks never graded."""

from uuid import uuid4

import pytest

from app.copy_guard import find_banned
from app.pressure_test import (
    AnswerCheckRequest,
    QuestionKind,
    Readiness,
    build_pressure_test,
    check_answer,
    questions_for,
)
from app.readiness_service import ClaimNotFoundForUser, ReadinessService
from app.story_models import StoryCreate
from app.story_repository import MemoryPressureResponseRepository, MemoryStoryRepository
from tests.test_interview_map import (
    OUTPUT,
    USER,
    FakeDocuments,
    FakeResumes,
    FakeRoles,
    _document,
    claim,
    competency,
    resume,
    role,
)


def kinds(item_claim):
    return [question.kind for question in questions_for(item_claim)]


def test_soft_ownership_words_invite_an_ownership_question_that_quotes_them() -> None:
    questions = questions_for(claim("Supported the pricing team with weekly reports", claim_type="RESPONSIBILITY"))
    assert questions[0].kind == QuestionKind.OWNERSHIP
    assert "Supported" in questions[0].why


def test_a_result_without_a_number_invites_a_measure_question() -> None:
    assert QuestionKind.MEASURE in kinds(claim("Improved reporting accuracy"))
    assert QuestionKind.MEASURE not in kinds(claim("Cut costs by 20%", metric=20.0))


def test_a_number_invites_a_question_about_where_it_came_from() -> None:
    assert QuestionKind.SOURCE_OF_NUMBER in kinds(claim("Cut costs by 20%", metric=20.0))


def test_skills_are_asked_for_a_real_example() -> None:
    assert QuestionKind.USAGE in kinds(claim("Advanced SQL", claim_type="SKILL"))


def test_questions_are_capped_unique_and_always_include_a_choice() -> None:
    for item in (claim("Supported a launch", claim_type="PROJECT"), claim("SQL", claim_type="TOOL")):
        found = kinds(item)
        assert len(found) == len(set(found)) <= 5
        assert QuestionKind.ALTERNATIVE in found


def test_questions_never_say_prove_and_never_use_a_banned_word() -> None:
    for item in (claim("Supported the team", claim_type="OWNERSHIP"), claim("Cut costs 20%", metric=20.0), claim("SQL", claim_type="SKILL")):
        for question in questions_for(item):
            assert "prove" not in (question.text + question.why).lower()
            assert not find_banned(question.text + question.why)


def test_the_corrected_wording_is_used_when_the_person_fixed_it() -> None:
    fixed = claim("Led pricing").model_copy(update={"review_status": "NEEDS_CORRECTION", "corrected_claim_text": "Helped with pricing"})
    built = build_pressure_test(role([competency("Pricing")]), resume(OUTPUT, [fixed]), has_resume_document=True)
    assert built.items[0].statement == "Helped with pricing"


def test_role_relevant_statements_come_first_and_duplicates_are_folded() -> None:
    items = [claim("Organised the office party"), claim("Built pricing models in SQL"), claim("Built pricing models in SQL")]
    built = build_pressure_test(role([competency("Pricing")]), resume(OUTPUT, items), has_resume_document=True)
    assert built.items[0].statement == "Built pricing models in SQL"
    assert built.items[0].related_theme == "Pricing"
    assert len(built.items) == 2


def test_long_resume_is_capped() -> None:
    items = [claim(f"Delivered project {i}") for i in range(40)]
    built = build_pressure_test(role([competency("Pricing")]), resume(OUTPUT, items), has_resume_document=True)
    assert len(built.items) == 12


def test_missing_unread_or_failed_resume_each_say_so() -> None:
    analysis = role([competency("Pricing")])
    assert build_pressure_test(analysis, None, has_resume_document=False).state == "NO_RESUME"
    assert build_pressure_test(analysis, None, has_resume_document=True).state == "READING"
    assert build_pressure_test(analysis, resume(status="FAILED"), has_resume_document=True).state == "UNREADABLE"


# ------------------------------------------------------------------ answer checks


def test_checks_describe_what_is_in_the_answer_without_a_grade() -> None:
    result = check_answer(AnswerCheckRequest(kind=QuestionKind.MEASURE, answer="We improved the report and people liked it."))
    assert {check.key: check.present for check in result.checks} == {"number": False, "result": True}
    assert result.follow_up and "big" in result.follow_up
    assert all("%" not in check.text and not find_banned(check.text) for check in result.checks)


def test_an_answer_with_everything_gets_no_follow_up() -> None:
    answer = "I rebuilt the model myself, which reduced forecast error from 18 to 9 percent in two months."
    assert check_answer(AnswerCheckRequest(kind=QuestionKind.MEASURE, answer=answer)).follow_up is None


def test_we_heavy_answers_are_noticed_for_ownership_questions() -> None:
    result = check_answer(AnswerCheckRequest(kind=QuestionKind.OWNERSHIP, answer="We did the work and our team shipped it."))
    assert not next(check for check in result.checks if check.key == "own_part").present


# ------------------------------------------------------------------ service


@pytest.mark.asyncio
async def test_readiness_is_saved_only_for_statements_on_the_persons_resume() -> None:
    mine = claim("Built pricing models")
    analysis = role([competency("Pricing")])
    responses = MemoryPressureResponseRepository()
    service = ReadinessService(
        FakeRoles(analysis), FakeDocuments([_document()]), FakeResumes(resume(OUTPUT, [mine])),
        MemoryStoryRepository(), None, responses,
    )
    await service.set_readiness(mine.id, USER, Readiness.NEEDS_PREPARATION)
    built = await service.pressure_test(analysis.id, USER)
    assert built.items[0].readiness == Readiness.NEEDS_PREPARATION

    with pytest.raises(ClaimNotFoundForUser):
        await service.set_readiness(uuid4(), USER, Readiness.CAN_EXPLAIN)


@pytest.mark.asyncio
async def test_a_story_made_from_a_statement_is_linked_back_to_it() -> None:
    mine = claim("Built pricing models")
    analysis = role([competency("Pricing")])
    stories = MemoryStoryRepository()
    story = await stories.create(USER, StoryCreate(title="Pricing models", source_claim_id=mine.id, origin="PRESSURE_TEST"))
    service = ReadinessService(
        FakeRoles(analysis), FakeDocuments([_document()]), FakeResumes(resume(OUTPUT, [mine])),
        stories, None, MemoryPressureResponseRepository(),
    )
    assert (await service.pressure_test(analysis.id, USER)).items[0].story_id == story.id
