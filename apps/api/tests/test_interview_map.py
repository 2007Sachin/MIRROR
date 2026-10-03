"""Interview Map: derived from real role and resume data, never invented, never scored."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.copy_guard import find_banned
from app.dashboard_summary import LatestReview, ReviewDimension, ReviewNextStep
from app.interview_map import (
    AreaAction,
    Coverage,
    ExperienceState,
    MapState,
    StoryEvidence,
    build_interview_map,
    coverage_for,
)
from app.resume_models import (
    ResumeAchievement,
    ResumeAgentOutput,
    ResumeAnalysisResponse,
    ResumeClaimReview,
    ResumeProject,
    ResumeSkill,
    ResumeWorkExperience,
)
from app.role_models import RoleAgentOutput, RoleAnalysisResponse, RoleAnalysisVersion, StoredRoleCompetency

USER = uuid4()
NOW = datetime.now(UTC)


def competency(name, category="ANALYTICAL", weight=0.8, source="JOB_DESCRIPTION_EXPLICIT", role_id=None, version_id=None):
    return StoredRoleCompetency(
        id=uuid4(), role_profile_id=role_id or uuid4(), analysis_version_id=version_id or uuid4(),
        name=name, category=category, importance_weight=weight, expected_level="INTERMEDIATE",
        source_type=source, source_reference=f"Requirements mention {name.lower()}", confidence=0.8,
    )


def role(competencies, status="COMPLETED", source_type="JOB_DESCRIPTION"):
    role_id, version_id = uuid4(), uuid4()
    comps = [c.model_copy(update={"role_profile_id": role_id, "analysis_version_id": version_id}) for c in competencies]
    output = None
    if status == "COMPLETED":
        output = RoleAgentOutput(
            canonical_role="Analyst", seniority="JUNIOR", source_type=source_type,
            competencies=[
                {k: v for k, v in c.model_dump().items() if k not in ("id", "role_profile_id", "analysis_version_id")}
                for c in comps
            ] or [competency("Placeholder").model_dump(exclude={"id", "role_profile_id", "analysis_version_id"})],
            behavioural_expectations=["Works well with product and sales teams"],
        )
    version = RoleAnalysisVersion(
        id=version_id, role_profile_id=role_id, user_id=USER, version=1, status=status,
        source_type=source_type, model="m", prompt_version="p", analysis_version="a",
        output=output, created_at=NOW, completed_at=NOW if status != "PROCESSING" else None,
    )
    return RoleAnalysisResponse(
        id=role_id, user_id=USER, target_role="AR Analyst", source_type=source_type,
        created_at=NOW, updated_at=NOW, latest_analysis=version, competencies=comps,
    )


def claim(text, claim_type="OUTCOME", metric=None, ownership=None, outcome=None):
    return ResumeClaimReview(
        id=uuid4(), claim_text=text, claim_type=claim_type, source="RESUME", source_reference="experience",
        confidence=0.8, verification_priority="HIGH", metric_value=metric, ownership_language=ownership, outcome=outcome,
    )


def resume(output=None, claims=(), status="COMPLETED"):
    return ResumeAnalysisResponse(
        id=uuid4(), document_id=uuid4(), user_id=USER, version=1, status=status,
        output=output if status == "COMPLETED" else None, model="m", prompt_version="p", analysis_version="a",
        created_at=NOW, completed_at=NOW, claims=list(claims),
    )


OUTPUT = ResumeAgentOutput(
    skills=[ResumeSkill(name="SQL", category="TECHNICAL", source_reference="skills", confidence=0.9),
            ResumeSkill(name="Stakeholder management", category="SOFT_SKILL", source_reference="skills", confidence=0.8)],
    work_experience=[ResumeWorkExperience(
        organization="Greaves", role="Product Planning Analyst",
        description="Built monthly market intelligence reports and data analysis for product planning",
        source_reference="work",
    )],
    projects=[ResumeProject(project_name="Pricing model", description="SQL pipeline for pricing data analysis", source_reference="projects")],
    achievements=[ResumeAchievement(title="Datathon rank 11", description="Analytics competition", source_reference="awards")],
)


# ------------------------------------------------------------------ coverage


def test_a_story_tagged_with_the_theme_counts_as_prepared() -> None:
    story = StoryEvidence(id=uuid4(), title="Pricing call", themes=("Experimentation",), text="We ran a test")
    coverage, matches = coverage_for("Experimentation", OUTPUT, [story])
    assert coverage == Coverage.PREPARED and matches[0].kind == "STORY"


def test_a_prepared_match_carries_the_exact_story_id_so_it_can_be_practised() -> None:
    """The frontend needs the exact story to link straight to practising it (never guessed)."""
    story = StoryEvidence(id=uuid4(), title="Pricing call", themes=("Experimentation",), text="We ran a test")
    _, matches = coverage_for("Experimentation", OUTPUT, [story])
    assert matches[0].story_id == story.id


def test_a_non_story_match_never_carries_a_story_id() -> None:
    coverage, matches = coverage_for("Data analysis", OUTPUT, [])
    assert coverage == Coverage.EXPERIENCE
    assert matches and all(match.story_id is None for match in matches)


def test_work_that_uses_the_theme_counts_as_experience_and_shows_where() -> None:
    coverage, matches = coverage_for("Data analysis", OUTPUT, [])
    assert coverage == Coverage.EXPERIENCE
    assert {match.kind for match in matches} <= {"WORK", "PROJECT", "ACHIEVEMENT"}
    assert matches and all(match.label for match in matches)


def test_a_skill_named_but_never_used_is_only_mentioned() -> None:
    coverage, _ = coverage_for("Stakeholder management", OUTPUT, [])
    assert coverage == Coverage.MENTIONED


def test_nothing_in_the_material_means_missing_not_a_guess() -> None:
    coverage, matches = coverage_for("Experimentation", OUTPUT, [])
    assert coverage == Coverage.MISSING and matches == []
    assert coverage_for("Data analysis", None, [])[0] == Coverage.MISSING


# ------------------------------------------------------------------ the map


def test_themes_come_only_from_the_role_ordered_by_importance_and_capped() -> None:
    names = [f"Theme {i}" for i in range(9)]
    built = build_interview_map(role([competency(n, weight=0.1 * i) for i, n in enumerate(names)]), resume(OUTPUT), has_resume_document=True)
    assert built.state == MapState.READY
    assert len(built.themes) == 6
    assert built.themes[0].name == "Theme 8"
    assert {theme.name for theme in built.themes} <= set(names)


def test_role_still_being_read_or_unreadable_says_so() -> None:
    assert build_interview_map(role([competency("SQL")], status="PROCESSING"), None, has_resume_document=False).state == MapState.ROLE_PREPARING
    assert build_interview_map(role([competency("SQL")], status="FAILED"), None, has_resume_document=False).state == MapState.ROLE_UNREADABLE
    assert build_interview_map(role([]), None, has_resume_document=False).state == MapState.ROLE_UNREADABLE


def test_missing_resume_shows_the_role_and_asks_for_experience_only() -> None:
    built = build_interview_map(role([competency("Data analysis")]), None, has_resume_document=False)
    assert built.experience_state == ExperienceState.MISSING
    assert all(theme.coverage == Coverage.MISSING for theme in built.themes)
    assert [area.action for area in built.preparation_areas] == [AreaAction.ADD_EXPERIENCE]


def test_uploaded_but_unread_resume_is_not_treated_as_empty_experience() -> None:
    built = build_interview_map(role([competency("Data analysis")]), None, has_resume_document=True)
    assert built.experience_state == ExperienceState.READING
    failed = build_interview_map(role([competency("Data analysis")]), resume(status="FAILED"), has_resume_document=True)
    assert failed.experience_state == ExperienceState.UNREADABLE


def test_preparation_areas_are_at_most_three_and_each_leads_to_an_action() -> None:
    comps = [competency(n) for n in ("Experimentation", "Forecasting", "Negotiation", "Data analysis", "Budgeting")]
    built = build_interview_map(role(comps), resume(OUTPUT), has_resume_document=True)
    assert 1 <= len(built.preparation_areas) <= 3
    assert all(area.action for area in built.preparation_areas)
    assert "data-analysis" not in {area.theme_key for area in built.preparation_areas}


def test_role_with_no_matching_experience_still_gets_a_useful_map() -> None:
    comps = [competency(n, category="DOMAIN") for n in ("Maritime law", "Ship chartering")]
    built = build_interview_map(role(comps), resume(OUTPUT), has_resume_document=True)
    assert all(theme.coverage == Coverage.MISSING for theme in built.themes)
    assert built.preparation_areas and built.questions


def test_unmeasured_resume_outcomes_become_an_impact_area() -> None:
    claims = [claim(f"Improved reporting {i}") for i in range(4)]
    built = build_interview_map(role([competency("Data analysis")]), resume(OUTPUT, claims), has_resume_document=True)
    assert built.preparation_areas[0].key == "impact-from-resume"
    measured = [claim(f"Cut costs by {i}0%", metric=float(i)) for i in range(4)]
    built = build_interview_map(role([competency("Data analysis")]), resume(OUTPUT, measured), has_resume_document=True)
    assert "impact-from-resume" not in {area.key for area in built.preparation_areas}


def test_a_review_that_asked_for_more_impact_takes_priority_over_the_resume() -> None:
    review = LatestReview(
        session_id=uuid4(), target_role="AR Analyst", completed_at=NOW, counts=None,
        dimensions=[ReviewDimension(key="impact", label="Showing your impact", state="Could go further", note="x")],
        improvements=[], next_step=ReviewNextStep(title="t", body="b"),
    )
    claims = [claim(f"Improved reporting {i}") for i in range(4)]
    built = build_interview_map(role([competency("Data analysis")]), resume(OUTPUT, claims), has_resume_document=True, latest_review=review)
    assert built.preparation_areas[0].key == "impact-from-practice"
    assert built.preparation_areas[0].focus == "impact"


def test_questions_are_capped_unique_and_least_prepared_first() -> None:
    comps = [competency("Data analysis", weight=0.9), competency("Experimentation", weight=0.5), competency("Forecasting", weight=0.4)]
    built = build_interview_map(role(comps), resume(OUTPUT), has_resume_document=True)
    texts = [question.text for question in built.questions]
    assert len(texts) == len(set(texts)) <= 5
    assert built.questions[0].theme_key != "data-analysis"


def test_inferred_role_themes_are_labelled_as_inferred() -> None:
    built = build_interview_map(
        role([competency("Data analysis", source="SYNTHETIC_CANONICAL")], source_type="SYNTHETIC_CANONICAL"),
        resume(OUTPUT), has_resume_document=True,
    )
    assert built.role_from_job_description is False
    assert built.themes[0].source_text is None


def test_nothing_the_map_says_contains_a_banned_word_or_a_number_score() -> None:
    comps = [competency(n) for n in ("Experimentation", "Stakeholder management", "Data analysis")]
    built = build_interview_map(role(comps), resume(OUTPUT, [claim(f"x {i}") for i in range(4)]), has_resume_document=True)
    texts = [area.title + area.body for area in built.preparation_areas] + [q.text + q.why for q in built.questions]
    for text in texts:
        assert not find_banned(text), text
        assert "%" not in text


# ------------------------------------------------------------------ service and routes


class FakeRoles:
    def __init__(self, analysis):
        self.analysis = analysis

    async def get(self, profile_id, user_id):
        from app.role_service import RoleProfileNotFoundForUser
        if profile_id != self.analysis.id or user_id != USER:
            raise RoleProfileNotFoundForUser
        return self.analysis


class FakeDocuments:
    def __init__(self, documents):
        self.documents = documents

    async def list_for_user(self, user_id, *, include_archived=False):
        return [doc for doc in self.documents if doc.user_id == user_id]


class FakeResumes:
    def __init__(self, analysis):
        self.analysis = analysis

    async def get(self, document_id, user_id):
        from app.resume_service import ResumeNotFound
        if self.analysis is None:
            raise ResumeNotFound
        return self.analysis


def _document(user=USER):
    from app.schemas import DocumentRead
    return DocumentRead(id=uuid4(), user_id=user, document_type="RESUME", status="PROCESSED", created_at=NOW, updated_at=NOW)


@pytest.mark.asyncio
async def test_service_reads_the_newest_resume_and_the_persons_stories() -> None:
    from app.readiness_service import ReadinessService
    from app.story_models import StoryCreate
    from app.story_repository import MemoryStoryRepository

    stories = MemoryStoryRepository()
    await stories.create(USER, StoryCreate(title="A test that changed pricing", themes=["Experimentation"], situation="s"))
    await stories.create(uuid4(), StoryCreate(title="Someone else's", themes=["Forecasting"]))
    analysis = role([competency("Experimentation"), competency("Forecasting")])
    service = ReadinessService(FakeRoles(analysis), FakeDocuments([_document()]), FakeResumes(resume(OUTPUT)), stories, None)

    built = await service.interview_map(analysis.id, USER)
    coverage = {theme.name: theme.coverage for theme in built.themes}
    assert coverage["Experimentation"] == Coverage.PREPARED
    assert coverage["Forecasting"] == Coverage.MISSING  # another person's story is never read


@pytest.mark.asyncio
async def test_an_archived_story_stops_counting_until_it_is_restored() -> None:
    from app.readiness_service import ReadinessService
    from app.story_models import StoryCreate
    from app.story_repository import MemoryStoryRepository

    stories = MemoryStoryRepository()
    story = await stories.create(USER, StoryCreate(title="A pricing experiment", themes=["Experimentation"], situation="s"))
    analysis = role([competency("Experimentation"), competency("Forecasting")])
    service = ReadinessService(FakeRoles(analysis), FakeDocuments([_document()]), FakeResumes(resume(OUTPUT)), stories, None)

    async def coverage():
        return {theme.name: theme.coverage for theme in (await service.interview_map(analysis.id, USER)).themes}

    before = await coverage()
    assert before["Experimentation"] == Coverage.PREPARED
    await stories.archive(story.id, USER)
    archived = await coverage()
    assert archived["Experimentation"] != Coverage.PREPARED
    assert archived["Forecasting"] == before["Forecasting"]  # nothing else moves
    await stories.restore(story.id, USER)
    assert await coverage() == before


@pytest.mark.asyncio
async def test_service_refuses_a_role_that_belongs_to_someone_else() -> None:
    from app.readiness_service import ReadinessService
    from app.role_service import RoleProfileNotFoundForUser
    from app.story_repository import MemoryStoryRepository

    analysis = role([competency("SQL")])
    service = ReadinessService(FakeRoles(analysis), FakeDocuments([]), FakeResumes(None), MemoryStoryRepository(), None)
    with pytest.raises(RoleProfileNotFoundForUser):
        await service.interview_map(uuid4(), USER)


# ------------------------------------------------------------------ stories framed for roles


class FakeRoleSet:
    """Several roles for one person, looked up by exact id only."""

    def __init__(self, *analyses):
        self.by_id = {analysis.id: analysis for analysis in analyses}

    async def get(self, profile_id, user_id):
        from app.role_service import RoleProfileNotFoundForUser
        if profile_id not in self.by_id or user_id != USER:
            raise RoleProfileNotFoundForUser
        return self.by_id[profile_id]


async def _framed_setup():
    from app.readiness_service import ReadinessService
    from app.story_repository import MemoryStoryRepository

    stories = MemoryStoryRepository()
    first = role([competency("Experimentation"), competency("Forecasting")])
    second = role([competency("Experimentation"), competency("Forecasting")])
    assert first.target_role == second.target_role and first.id != second.id  # same name, two roles
    service = ReadinessService(FakeRoleSet(first, second), FakeDocuments([_document()]), FakeResumes(resume(OUTPUT)), stories, None)

    async def coverage(analysis):
        return {theme.name: theme.coverage for theme in (await service.interview_map(analysis.id, USER)).themes}

    return stories, first, second, coverage


@pytest.mark.asyncio
async def test_a_story_with_no_role_counts_for_every_role() -> None:
    from app.story_models import StoryCreate

    stories, first, second, coverage = await _framed_setup()
    await stories.create(USER, StoryCreate(title="Forecast rebuild", themes=["Forecasting"], situation="s"))
    assert (await coverage(first))["Forecasting"] == Coverage.PREPARED
    assert (await coverage(second))["Forecasting"] == Coverage.PREPARED


@pytest.mark.asyncio
async def test_role_themes_count_only_for_that_exact_role() -> None:
    from app.story_models import StoryCreate, StoryRoleFramingInput

    stories, first, second, coverage = await _framed_setup()
    story = await stories.create(USER, StoryCreate(title="Pricing test", themes=["Forecasting"], situation="s"))
    await stories.set_framing(story.id, first.id, USER, StoryRoleFramingInput(themes=["Experimentation"]))

    one, two = await coverage(first), await coverage(second)
    assert one["Experimentation"] == Coverage.PREPARED
    assert two["Experimentation"] != Coverage.PREPARED  # same role name, different role: no leak
    assert one["Forecasting"] == two["Forecasting"] == Coverage.PREPARED  # its own themes still count everywhere


@pytest.mark.asyncio
async def test_one_story_framed_for_two_roles_counts_for_both_until_archived() -> None:
    from app.story_models import StoryCreate, StoryRoleFramingInput

    stories, first, second, coverage = await _framed_setup()
    story = await stories.create(USER, StoryCreate(title="Pricing test", situation="s", role_profile_id=first.id))
    await stories.set_framing(story.id, first.id, USER, StoryRoleFramingInput(themes=["Experimentation"]))
    await stories.set_framing(story.id, second.id, USER, StoryRoleFramingInput(themes=["Experimentation"]))
    before = (await coverage(first), await coverage(second))
    assert before[0]["Experimentation"] == before[1]["Experimentation"] == Coverage.PREPARED

    await stories.archive(story.id, USER)
    assert (await coverage(first))["Experimentation"] != Coverage.PREPARED
    assert (await coverage(second))["Experimentation"] != Coverage.PREPARED
    await stories.restore(story.id, USER)
    assert (await coverage(first), await coverage(second)) == before


@pytest.mark.asyncio
async def test_removing_a_role_from_a_story_only_affects_that_role() -> None:
    from app.story_models import StoryCreate, StoryRoleFramingInput

    stories, first, second, coverage = await _framed_setup()
    story = await stories.create(USER, StoryCreate(title="Pricing test", situation="s"))
    for analysis in (first, second):
        await stories.set_framing(story.id, analysis.id, USER, StoryRoleFramingInput(themes=["Experimentation"]))
    await stories.remove_framing(story.id, first.id, USER)
    assert (await coverage(first))["Experimentation"] != Coverage.PREPARED
    assert (await coverage(second))["Experimentation"] == Coverage.PREPARED


def test_role_themes_add_to_a_storys_own_themes_without_repeating_them() -> None:
    from app.readiness_service import story_evidence
    from app.story_models import StoryRead

    story = StoryRead(id=uuid4(), user_id=USER, title="t", themes=["Pricing"], origin="MANUAL", created_at=NOW, updated_at=NOW)
    assert story_evidence(story).themes == ("Pricing",)
    assert story_evidence(story, ["pricing", "Discovery"]).themes == ("Pricing", "Discovery")
