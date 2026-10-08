from __future__ import annotations

import pytest

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from app.target_assessment_contract import (
    AssessmentContractUnavailable,
    AssessmentRubricResolver,
    parse_blueprint_rules_version,
    resolve_target_assessment_scope,
)
from app.specialist_assessor_models import AssessorType
from app.target_taxonomy import load_taxonomy


def test_ba_case_resolves_exact_taxonomy_competencies_and_mirror_provenance() -> None:
    taxonomy = load_taxonomy(1)
    contract = AssessmentRubricResolver().resolve(
        taxonomy=taxonomy,
        role_family_key="business_analysis",
        round_key="business_problem_solving",
        catalog_version=1,
    )

    assert contract.question_family == "case_discussion"
    assert contract.competency_keys == (
        "structured_problem_solving",
        "quantitative_reasoning",
        "business_judgement",
    )
    assert tuple(dimension.competency_key for dimension in contract.dimensions) == contract.competency_keys
    assert tuple(dimension.title for dimension in contract.dimensions) == (
        "Structured problem solving",
        "Quantitative reasoning",
        "Business judgment",
    )
    assert contract.assessor_types == (AssessorType.TECHNICAL,)
    assert contract.provenance_class == "MIRROR_GENERATED"
    assert contract.rubric_version == "assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1"


def test_assessment_rubric_catalog_v1_digest_is_append_only() -> None:
    import json
    from pathlib import Path

    from app.research_catalog import content_sha256

    content_dir = Path(__file__).parents[1] / "app" / "assessment_content"
    catalog_bytes = (content_dir / "assessment_rubrics_v1.json").read_bytes()
    lock = json.loads((content_dir / "LOCK.json").read_text(encoding="utf-8"))
    pinned = lock["catalogs"]["assessment_rubrics_v1.json"]

    assert pinned == {
        "version": 1,
        "sha256": "e5e62340c21a035180fd757ce9decec1a1022101e5ad5d6bf985175f407df0d1",
    }
    assert content_sha256(catalog_bytes) == pinned["sha256"]


def test_unknown_round_does_not_fall_back_to_an_unrelated_rubric() -> None:
    taxonomy = load_taxonomy(1)

    with pytest.raises(AssessmentContractUnavailable):
        AssessmentRubricResolver().resolve(
            taxonomy=taxonomy,
            role_family_key="business_analysis",
            round_key="coding_reasoning",
            catalog_version=1,
        )


def test_unconfigured_business_round_fails_closed_instead_of_using_the_case_or_behavior_rubric() -> None:
    taxonomy = load_taxonomy(1)

    with pytest.raises(AssessmentContractUnavailable):
        AssessmentRubricResolver().resolve(
            taxonomy=taxonomy,
            role_family_key="business_analysis",
            round_key="requirements_and_stakeholders",
            catalog_version=1,
        )


def test_synthetic_third_role_family_uses_the_same_data_driven_resolver() -> None:
    import json
    from pathlib import Path

    from app.target_assessment_contract import assessment_catalog_from_dict
    from app.target_taxonomy import taxonomy_from_dict

    taxonomy_path = Path(__file__).parents[1] / "app" / "research_content" / "taxonomy_v1.json"
    raw_taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    raw_taxonomy["competencies"]["stakeholder_alignment"] = {"evidence_terms": ["stakeholder alignment"]}
    raw_taxonomy["role_families"]["fictional_energy_analytics"] = {
        "levels": ["analyst", "not_sure"],
        "rounds": [{
            "key": "impact_scenario",
            "ordinal": 1,
            "theme": "Working through an impact scenario",
            "question_family": "workplace_scenario",
            "competency_keys": ["stakeholder_alignment"],
            "claim_subjects": [],
            "templates": [{
                "id": "fictional.impact_scenario",
                "family_key": "impact_tradeoff",
                "competency_key": "stakeholder_alignment",
                "fallback": "A community project has limited funding. How would you align stakeholders on what to do first?",
            }],
        }],
    }
    taxonomy = taxonomy_from_dict(raw_taxonomy)
    catalog = assessment_catalog_from_dict({
        "schema": "mirror.assessment_rubric_catalog/1",
        "version": 1,
        "rubrics": [{
            "rubric_key": "impact_scenario_v1",
            "role_family_key": "fictional_energy_analytics",
            "round_key": "impact_scenario",
            "question_family": "workplace_scenario",
            "competency_keys": ["stakeholder_alignment"],
            "assessor_types": ["TECHNICAL"],
            "provenance_class": "MIRROR_GENERATED",
            "dimensions": [{
                "competency_key": "stakeholder_alignment",
                "title": "Stakeholder alignment",
                "criteria": "Explains how the different stakeholder needs would be understood and brought into a workable decision.",
                "insufficient_signal": "If the response gives no signal about stakeholder needs or alignment, mark NOT_ENOUGH_SIGNAL.",
            }],
        }],
    })

    contract = AssessmentRubricResolver(catalogs={1: catalog}).resolve(
        taxonomy=taxonomy,
        role_family_key="fictional_energy_analytics",
        round_key="impact_scenario",
        catalog_version=1,
    )

    assert contract.role_family_key == "fictional_energy_analytics"
    assert contract.round_key == "impact_scenario"
    assert contract.competency_keys == ("stakeholder_alignment",)
    assert contract.provenance_class == "MIRROR_GENERATED"


def test_injected_catalog_version_must_match_the_blueprint_pin() -> None:
    from app.target_assessment_contract import assessment_catalog_from_dict

    taxonomy = load_taxonomy(1)
    catalog = assessment_catalog_from_dict({
        "schema": "mirror.assessment_rubric_catalog/1",
        "version": 2,
        "rubrics": [{
            "rubric_key": "business_case_v2",
            "role_family_key": "business_analysis",
            "round_key": "business_problem_solving",
            "question_family": "case_discussion",
            "competency_keys": ["structured_problem_solving", "quantitative_reasoning", "business_judgement"],
            "assessor_types": ["TECHNICAL"],
            "provenance_class": "MIRROR_GENERATED",
            "dimensions": [
                {"competency_key": "structured_problem_solving", "title": "Structured problem solving", "criteria": "Frames and breaks down the business question before selecting a response.", "insufficient_signal": "If no problem framing is shown, mark NOT_ENOUGH_SIGNAL."},
                {"competency_key": "quantitative_reasoning", "title": "Quantitative reasoning", "criteria": "Explains assumptions, quantitative logic, and interpretation.", "insufficient_signal": "If no quantitative signal appears, mark NOT_ENOUGH_SIGNAL."},
                {"competency_key": "business_judgement", "title": "Business judgment", "criteria": "Connects a recommendation to priorities, trade-offs, risks, or uncertainty.", "insufficient_signal": "If no decision signal appears, mark NOT_ENOUGH_SIGNAL."},
            ],
        }],
    })

    with pytest.raises(AssessmentContractUnavailable):
        AssessmentRubricResolver(catalogs={1: catalog}).resolve(
            taxonomy=taxonomy,
            role_family_key="business_analysis",
            round_key="business_problem_solving",
            catalog_version=1,
        )


def target_scope_inputs(rules_version: str = "blueprint-3-taxonomy-1-assessment-1"):
    from app.target_repository import CandidateTarget, InterviewBlueprint, QuestionCreate, TargetSessionLink

    user_id, session_id, target_id, role_profile_id, blueprint_id, prompt_set_id = (uuid4() for _ in range(6))
    now = datetime.now(UTC)
    target = CandidateTarget(
        id=target_id,
        user_id=user_id,
        role_profile_id=role_profile_id,
        company_label="Synthetic Consulting Co",
        company_key="synthetic_consulting",
        role_family_key="business_analysis",
        level_key="consultant",
        level_label="Consultant",
        geography_key="qa_land",
        geography_label="Synthetic market",
        interview_date=None,
        status="ACTIVE",
        archived_at=None,
        created_at=now,
        updated_at=now,
    )
    blueprint = InterviewBlueprint(
        id=blueprint_id,
        user_id=user_id,
        candidate_target_id=target_id,
        version=1,
        catalog_version=1,
        catalog_sha256="b" * 64,
        match_state="GENERAL_ONLY",
        rules_version=rules_version,
        created_at=now,
    )
    round_data = load_taxonomy(1).document.role_families["business_analysis"].rounds[0]
    manifest = tuple(
        QuestionCreate(
            candidate_target_id=target_id,
            blueprint_id=blueprint_id,
            prompt_set_id=prompt_set_id,
            position=position,
            round_key=round_data.key,
            competency_key=template.competency_key,
            family_key=template.family_key,
            template_id=template.id,
            generator_version="round-pack-1",
            originality_rules_version="originality-1",
            question_text=template.fallback,
            rationale_code="MIRROR_SUGGESTED",
            derived_from={"round_key": round_data.key, "story_titles": []},
            novelty_sha256=("a" * 63) + str(position),
        )
        for position, template in enumerate(round_data.templates[:4], start=1)
    )
    link = TargetSessionLink(
        session_id=session_id,
        candidate_target_id=target_id,
        blueprint_id=blueprint_id,
        round_key=round_data.key,
        competency_key=None,
        prompt_set_id=prompt_set_id,
        prompt_set_state="COMPLETE",
        expected_prompt_count=len(manifest),
        prompt_manifest=manifest,
        user_id=user_id,
        created_at=now,
    )
    return user_id, session_id, role_profile_id, target, blueprint, link


def resolve_scope(inputs):
    user_id, session_id, role_profile_id, target, blueprint, link = inputs
    return resolve_target_assessment_scope(
        link=link,
        target=target,
        blueprint=blueprint,
        user_id=user_id,
        session_id=session_id,
        session_role_profile_id=role_profile_id,
    )


def test_target_case_scope_uses_complete_pinned_round_and_manifest() -> None:
    inputs = target_scope_inputs()
    scope = resolve_scope(inputs)

    assert scope.target_id == inputs[3].id
    assert scope.role_profile_id == inputs[2]
    assert scope.role_family_key == "business_analysis"
    assert scope.round_key == "business_problem_solving"
    assert scope.round_label == load_taxonomy(1).document.role_families["business_analysis"].rounds[0].theme
    assert scope.question_family == "case_discussion"
    assert scope.taxonomy_version == 1
    assert scope.catalog_version == 1
    assert scope.competency_keys == (
        "structured_problem_solving",
        "quantitative_reasoning",
        "business_judgement",
    )
    assert scope.assessor_types == (AssessorType.TECHNICAL,)
    assert scope.provenance_class == "MIRROR_GENERATED"
    assert inputs[5].prompt_manifest is not None
    assert len(scope.questions) == len(inputs[5].prompt_manifest) == 4
    assert tuple(question.text for question in scope.questions) == tuple(
        row.question_text for row in inputs[5].prompt_manifest
    )
    assert all(question.question_family == "case_discussion" for question in scope.questions)
    assert all(question.competency_key in scope.competency_keys for question in scope.questions)


def test_company_identity_does_not_select_a_different_round_rubric() -> None:
    inputs = target_scope_inputs()
    baseline = resolve_scope(inputs)
    altered_target = inputs[3].model_copy(update={"company_label": "Another Employer", "company_key": "amazon"})
    altered_inputs = (*inputs[:3], altered_target, *inputs[4:])

    assert resolve_scope(altered_inputs).rubric_key == baseline.rubric_key
    assert resolve_scope(altered_inputs).competency_keys == baseline.competency_keys


def test_target_scope_rejects_an_incomplete_or_mismatched_manifest() -> None:
    inputs = target_scope_inputs()
    link = inputs[5]
    assert link.prompt_manifest is not None
    bad_question = link.prompt_manifest[0].model_copy(update={"competency_key": "coding_quality"})
    bad_link = link.model_copy(update={"prompt_manifest": (bad_question, *link.prompt_manifest[1:])})
    bad_inputs = (*inputs[:5], bad_link)

    with pytest.raises(AssessmentContractUnavailable):
        resolve_scope(bad_inputs)

    pending_link = link.model_copy(update={"prompt_set_state": "PENDING"})
    with pytest.raises(AssessmentContractUnavailable):
        resolve_scope((*inputs[:5], pending_link))


def test_target_scope_fails_closed_for_legacy_or_wrong_session_attribution() -> None:
    old_pin_inputs = target_scope_inputs("blueprint-2-taxonomy-1")
    with pytest.raises(AssessmentContractUnavailable):
        resolve_scope(old_pin_inputs)

    inputs = target_scope_inputs()
    with pytest.raises(AssessmentContractUnavailable):
        resolve_target_assessment_scope(
            link=inputs[5],
            target=inputs[3],
            blueprint=inputs[4],
            user_id=inputs[0],
            session_id=uuid4(),
            session_role_profile_id=inputs[2],
        )

    with pytest.raises(AssessmentContractUnavailable):
        resolve_target_assessment_scope(
            link=inputs[5],
            target=inputs[3],
            blueprint=inputs[4],
            user_id=inputs[0],
            session_id=inputs[1],
            session_role_profile_id=uuid4(),
        )


def test_repository_uses_target_round_contract_and_skips_unselected_specialists() -> None:
    import asyncio

    from app.specialist_assessment_repository import SupabaseSpecialistAssessmentRepository
    from app.target_assessment_contract import TargetAssessmentScopeResolver

    inputs = target_scope_inputs()
    user_id, session_id, role_profile_id, target, blueprint, link = inputs

    class TargetLookup:
        async def link_for_session(self, current_session_id, current_user_id):
            assert current_session_id == session_id and current_user_id == user_id
            return link

        async def get_target(self, target_id, current_user_id):
            assert target_id == target.id and current_user_id == user_id
            return target

        async def blueprints(self, target_id, current_user_id):
            assert target_id == target.id and current_user_id == user_id
            return [blueprint]

    class FakeRepository(SupabaseSpecialistAssessmentRepository):
        def __init__(self):
            self._scope_reader = TargetAssessmentScopeResolver(cast(Any, TargetLookup()))

        async def _get(self, resource, params):
            if resource == "sessions":
                return [{"id": str(session_id), "role_profile_id": str(role_profile_id)}]
            return []

    repository = FakeRepository()
    behaviour = asyncio.run(repository.load_context(session_id, user_id, AssessorType.BEHAVIOUR))
    assert behaviour is None

    context = asyncio.run(repository.load_context(session_id, user_id, AssessorType.TECHNICAL))
    assert context is not None
    assert context.assessment_scope is not None
    assert context.assessment_scope.round_key == "business_problem_solving"
    assert context.assessment_scope.competency_keys == (
        "structured_problem_solving",
        "quantitative_reasoning",
        "business_judgement",
    )
    assert context.rubric_version == "assessment-rubrics-1:taxonomy-1:business_analysis:business_problem_solving:business_case_v1"
    assert {anchor["competency_key"] for anchor in context.rubric_anchors} == set(context.assessment_scope.competency_keys)
    serialized_scope = context.model_dump()["assessment_scope"]
    assert "target_id" not in serialized_scope and "role_profile_id" not in serialized_scope

