from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import get_settings
from .research_catalog import content_sha256
from .specialist_assessor_models import (
    AssessorType,
    AssessmentQuestionContext,
    AssessmentScope,
)
from .target_repository import CandidateTarget, InterviewBlueprint, SupabaseTargetRepository, TargetRepository, TargetSessionLink, TargetsUnavailable
from .target_taxonomy import Taxonomy, TaxonomyError, load_taxonomy

CONTENT_DIR = Path(__file__).parent / "assessment_content"
CATALOG_SCHEMA = "mirror.assessment_rubric_catalog/1"
ASSESSMENT_RUBRIC_CATALOG_VERSION = 1
_KEY = re.compile(r"^[a-z][a-z0-9_]{1,79}$")


class AssessmentContractUnavailable(ValueError):
    """Pinned target-round assessment scope or rubric cannot be resolved safely."""


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BlueprintRulesPin(_FrozenModel):
    blueprint_version: int = Field(ge=1)
    taxonomy_version: int = Field(ge=1)
    assessment_catalog_version: int | None = Field(default=None, ge=1)


def parse_blueprint_rules_version(rules_version: str) -> BlueprintRulesPin:
    """Parse the immutable taxonomy/rubric pins while retaining legacy blueprint formats."""
    if rules_version == "blueprint-1":
        return BlueprintRulesPin(
            blueprint_version=1,
            taxonomy_version=1,
            assessment_catalog_version=None,
        )
    match = re.fullmatch(
        r"blueprint-(?P<blueprint>[1-9][0-9]*)-taxonomy-(?P<taxonomy>[1-9][0-9]*)(?:-assessment-(?P<assessment>[1-9][0-9]*))?",
        rules_version,
    )
    if match is None:
        raise AssessmentContractUnavailable("blueprint rules pin is malformed")
    blueprint_version = int(match.group("blueprint"))
    assessment_text = match.group("assessment")
    if blueprint_version < 2 or (blueprint_version == 2 and assessment_text is not None):
        raise AssessmentContractUnavailable("blueprint rules pin has an unsupported version combination")
    if blueprint_version >= 3 and assessment_text is None:
        raise AssessmentContractUnavailable("assessment catalog pin is required for this blueprint version")
    return BlueprintRulesPin(
        blueprint_version=blueprint_version,
        taxonomy_version=int(match.group("taxonomy")),
        assessment_catalog_version=int(assessment_text) if assessment_text is not None else None,
    )


class AssessmentRubricDimension(_FrozenModel):
    competency_key: str = Field(pattern=_KEY.pattern)
    title: str = Field(min_length=3, max_length=100)
    criteria: str = Field(min_length=20, max_length=1000)
    insufficient_signal: str = Field(min_length=20, max_length=500)


class AssessmentRubricDefinition(_FrozenModel):
    rubric_key: str = Field(pattern=_KEY.pattern)
    role_family_key: str = Field(pattern=_KEY.pattern)
    round_key: str = Field(pattern=_KEY.pattern)
    question_family: str = Field(pattern=_KEY.pattern)
    competency_keys: tuple[str, ...] = Field(min_length=1, max_length=20)
    assessor_types: tuple[AssessorType, ...] = Field(min_length=1, max_length=3)
    provenance_class: Literal["MIRROR_GENERATED"]
    dimensions: tuple[AssessmentRubricDimension, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def exact_unique_dimension_mapping(self) -> AssessmentRubricDefinition:
        if len(set(self.competency_keys)) != len(self.competency_keys):
            raise ValueError("rubric competency keys must be unique")
        if tuple(d.competency_key for d in self.dimensions) != self.competency_keys:
            raise ValueError("rubric dimensions must map one-to-one, in order, to competency keys")
        if len(set(self.assessor_types)) != len(self.assessor_types):
            raise ValueError("rubric assessor types must be unique")
        return self


class AssessmentRubricCatalog(_FrozenModel):
    schema_: Literal["mirror.assessment_rubric_catalog/1"] = Field(alias="schema")
    version: int = Field(ge=1)
    rubrics: tuple[AssessmentRubricDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_round_entries(self) -> AssessmentRubricCatalog:
        keys = [(row.role_family_key, row.round_key) for row in self.rubrics]
        if len(set(keys)) != len(keys):
            raise ValueError("assessment catalog contains duplicate role-family/round entries")
        return self


class ResolvedAssessmentContract(_FrozenModel):
    taxonomy_version: int = Field(ge=1)
    catalog_version: int = Field(ge=1)
    rubric_key: str
    rubric_version: str
    role_family_key: str
    round_key: str
    question_family: str
    competency_keys: tuple[str, ...]
    assessor_types: tuple[AssessorType, ...]
    provenance_class: Literal["MIRROR_GENERATED"]
    dimensions: tuple[AssessmentRubricDimension, ...]


def assessment_catalog_from_dict(raw: dict[str, Any]) -> AssessmentRubricCatalog:
    try:
        return AssessmentRubricCatalog.model_validate(raw)
    except ValueError as exc:
        raise AssessmentContractUnavailable("assessment rubric catalog is invalid") from exc


@lru_cache(maxsize=8)
def load_assessment_rubric_catalog(version: int) -> AssessmentRubricCatalog:
    """Read only a locked, explicitly versioned catalog; prior versions are append-only."""
    try:
        lock = json.loads((CONTENT_DIR / "LOCK.json").read_text(encoding="utf-8"))
        entries = lock["catalogs"]
        matches = [(name, entry) for name, entry in entries.items() if int(entry["version"]) == version]
        if len(matches) != 1:
            raise AssessmentContractUnavailable("assessment catalog version is missing or duplicated")
        filename, entry = matches[0]
        if filename != f"assessment_rubrics_v{version}.json":
            raise AssessmentContractUnavailable("assessment catalog lock filename is invalid")
        path = (CONTENT_DIR / filename).resolve()
        if path.parent != CONTENT_DIR.resolve():
            raise AssessmentContractUnavailable("assessment catalog lock path is unsafe")
        raw_bytes = path.read_bytes()
        if content_sha256(raw_bytes) != entry.get("sha256"):
            raise AssessmentContractUnavailable("assessment catalog bytes do not match their lock")
        raw = json.loads(raw_bytes.decode("utf-8"))
        catalog = assessment_catalog_from_dict(raw)
    except AssessmentContractUnavailable:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AssessmentContractUnavailable("assessment catalog or lock is unreadable") from exc
    if catalog.version != version or entry.get("version") != version:
        raise AssessmentContractUnavailable("assessment catalog version does not match its lock")
    return catalog


class AssessmentRubricResolver:
    """Resolve a pinned round rubric from taxonomy + locked, company-independent data."""

    def __init__(self, catalogs: Mapping[int, AssessmentRubricCatalog] | None = None) -> None:
        self._catalogs = dict(catalogs or {})

    def resolve(
        self,
        *,
        taxonomy: Taxonomy,
        role_family_key: str,
        round_key: str,
        catalog_version: int,
    ) -> ResolvedAssessmentContract:
        try:
            role_family = taxonomy.document.role_families[role_family_key]
            round_data = next(row for row in role_family.rounds if row.key == round_key)
        except (KeyError, StopIteration) as exc:
            raise AssessmentContractUnavailable("target role family or round is absent from pinned taxonomy") from exc
        catalog = self._catalogs.get(catalog_version) or load_assessment_rubric_catalog(catalog_version)
        if catalog.version != catalog_version:
            raise AssessmentContractUnavailable("injected assessment catalog does not match requested pin")
        matches = [
            row for row in catalog.rubrics
            if row.role_family_key == role_family_key and row.round_key == round_key
        ]
        if len(matches) != 1:
            raise AssessmentContractUnavailable("target round has no unique assessment rubric")
        rubric = matches[0]
        if rubric.question_family != round_data.question_family:
            raise AssessmentContractUnavailable("rubric question family does not match pinned taxonomy")
        if rubric.competency_keys != round_data.competency_keys:
            raise AssessmentContractUnavailable("rubric competencies do not exactly match pinned round")
        if any(key not in taxonomy.document.competencies for key in rubric.competency_keys):
            raise AssessmentContractUnavailable("rubric references a competency absent from pinned taxonomy")
        return ResolvedAssessmentContract(
            taxonomy_version=taxonomy.document.version,
            catalog_version=catalog.version,
            rubric_key=rubric.rubric_key,
            rubric_version=(
                f"assessment-rubrics-{catalog.version}:taxonomy-{taxonomy.document.version}:"
                f"{role_family_key}:{round_key}:{rubric.rubric_key}"
            ),
            role_family_key=role_family_key,
            round_key=round_key,
            question_family=rubric.question_family,
            competency_keys=rubric.competency_keys,
            assessor_types=rubric.assessor_types,
            provenance_class=rubric.provenance_class,
            dimensions=rubric.dimensions,
        )


def resolve_target_assessment_scope(
    *,
    link: TargetSessionLink,
    target: CandidateTarget,
    blueprint: InterviewBlueprint,
    user_id,
    session_id,
    session_role_profile_id,
    taxonomy_loader=load_taxonomy,
    rubric_resolver: AssessmentRubricResolver | None = None,
) -> AssessmentScope:
    """Bind a target-linked practice to its immutable round, prompts, and pinned rubric."""
    if (
        link.user_id != user_id
        or target.user_id != user_id
        or blueprint.user_id != user_id
        or link.session_id != session_id
        or link.candidate_target_id != target.id
        or blueprint.candidate_target_id != target.id
        or link.blueprint_id is None
        or link.blueprint_id != blueprint.id
        or session_role_profile_id is None
        or target.role_profile_id != session_role_profile_id
    ):
        raise AssessmentContractUnavailable("target assessment ownership or attribution does not match")
    if not link.round_key:
        raise AssessmentContractUnavailable("target assessment round is missing")
    if (
        link.prompt_set_state != "COMPLETE"
        or link.prompt_set_id is None
        or link.expected_prompt_count not in (3, 4)
        or link.prompt_manifest is None
        or len(link.prompt_manifest) != link.expected_prompt_count
    ):
        raise AssessmentContractUnavailable("target assessment prompt manifest is incomplete")
    try:
        pin = parse_blueprint_rules_version(blueprint.rules_version)
    except AssessmentContractUnavailable:
        raise
    if pin.assessment_catalog_version is None:
        raise AssessmentContractUnavailable("blueprint has no pinned assessment catalog")
    try:
        taxonomy = taxonomy_loader(pin.taxonomy_version)
    except (TaxonomyError, OSError, ValueError) as exc:
        raise AssessmentContractUnavailable("pinned taxonomy is unavailable") from exc
    resolver = rubric_resolver or AssessmentRubricResolver()
    contract = resolver.resolve(
        taxonomy=taxonomy,
        role_family_key=target.role_family_key,
        round_key=link.round_key,
        catalog_version=pin.assessment_catalog_version,
    )
    if link.competency_key is not None and contract.competency_keys != (link.competency_key,):
        raise AssessmentContractUnavailable("single-competency link does not have a matching rubric")
    try:
        round_data = next(
            row for row in taxonomy.document.role_families[target.role_family_key].rounds
            if row.key == link.round_key
        )
    except (KeyError, StopIteration) as exc:
        raise AssessmentContractUnavailable("target round is absent from pinned taxonomy") from exc
    templates = {template.id: template for template in round_data.templates}
    questions: list[AssessmentQuestionContext] = []
    for position, row in enumerate(link.prompt_manifest, start=1):
        template = templates.get(row.template_id)
        if (
            row.position != position
            or row.candidate_target_id != target.id
            or row.blueprint_id != blueprint.id
            or row.prompt_set_id != link.prompt_set_id
            or row.round_key != link.round_key
            or template is None
            or row.family_key != template.family_key
            or row.competency_key != template.competency_key
            or row.competency_key not in contract.competency_keys
        ):
            raise AssessmentContractUnavailable("target prompt manifest does not match its pinned round")
        questions.append(AssessmentQuestionContext(
            position=row.position,
            template_id=row.template_id,
            family_key=row.family_key,
            competency_key=row.competency_key,
            question_family=contract.question_family,
            text=row.question_text,
        ))
    return AssessmentScope(
        target_id=target.id,
        role_profile_id=target.role_profile_id,
        role_family_key=contract.role_family_key,
        round_key=contract.round_key,
        round_label=round_data.theme,
        question_family=contract.question_family,
        taxonomy_version=contract.taxonomy_version,
        catalog_version=contract.catalog_version,
        rubric_key=contract.rubric_key,
        rubric_version=contract.rubric_version,
        competency_keys=contract.competency_keys,
        assessor_types=contract.assessor_types,
        provenance_class=contract.provenance_class,
        dimensions=tuple(dimension.model_dump() for dimension in contract.dimensions),
        questions=tuple(questions),
    )


class TargetAssessmentScopeResolver:
    """Owner-scoped adapter from existing target metadata to an assessment contract."""

    def __init__(self, repository: TargetRepository | None = None) -> None:
        self._repository_instance = repository

    def _target_repository(self) -> TargetRepository:
        if self._repository_instance is None:
            self._repository_instance = SupabaseTargetRepository(get_settings())
        return self._repository_instance

    async def load_scope(
        self,
        session_id: UUID,
        user_id: UUID,
        session_role_profile_id: UUID | None,
    ) -> AssessmentScope | None:
        try:
            repository = self._target_repository()
            link = await repository.link_for_session(session_id, user_id)
            if link is None:
                return None
            if link.blueprint_id is None:
                raise AssessmentContractUnavailable("target-linked practice has no blueprint pin")
            target = await repository.get_target(link.candidate_target_id, user_id)
            if target is None:
                raise AssessmentContractUnavailable("target-linked practice has no owner-scoped target")
            if session_role_profile_id is None or target.role_profile_id != session_role_profile_id:
                raise AssessmentContractUnavailable("target role profile does not match the session")
            blueprints = await repository.blueprints(target.id, user_id)
            blueprint = next((row for row in blueprints if row.id == link.blueprint_id), None)
            if blueprint is None:
                raise AssessmentContractUnavailable("target-linked practice has no owner-scoped blueprint")
            return resolve_target_assessment_scope(
                link=link,
                target=target,
                blueprint=blueprint,
                user_id=user_id,
                session_id=session_id,
                session_role_profile_id=session_role_profile_id,
            )
        except TargetsUnavailable as exc:
            raise AssessmentContractUnavailable("target assessment scope is unavailable") from exc

