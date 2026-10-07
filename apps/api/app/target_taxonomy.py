"""Interview-target taxonomy: role families, their practice rounds, competencies, companies (pure data).

Everything that differs between companies or role families lives in the locked data file
``research_content/taxonomy_v1.json``; this module only loads and validates it. Adding a role
family, a practice round, a competency or a company alias is a data change reviewed with the
file's LOCK hash, never a code branch.

* A role family owns its level vocabulary and its practice rounds (Mirror practice coverage,
  not a claim about any company's hiring stages).
* A practice round names one question family (the format a prompt takes), the competencies it
  practises and its original Mirror prompt templates.
* A competency is shared across role families when it is genuinely the same skill; its
  ``evidence_terms`` are plain words matched against the person's own plan themes.
* A company entry holds alias names (exact match only) and process words that Mirror's own
  prompts must never use for that company.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .research_catalog import KEY_PATTERN, content_sha256

TAXONOMY_SCHEMA = "mirror.target_taxonomy/1"
CONTENT_DIR = Path(__file__).parent / "research_content"
TAXONOMY_FILE = "taxonomy_v1.json"
NOT_SURE = "not_sure"
_KEY = re.compile(KEY_PATTERN)


class TaxonomyError(ValueError):
    """The taxonomy data is missing, altered or inconsistent; nothing is served from it."""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PromptTemplateData(_Frozen):
    id: str = Field(min_length=3, max_length=80)
    family_key: str = Field(pattern=KEY_PATTERN)
    competency_key: str = Field(pattern=KEY_PATTERN)
    fallback: str = Field(min_length=20, max_length=400)
    story_text: str | None = Field(default=None, min_length=20, max_length=400)

    @model_validator(mode="after")
    def _one_slot(self) -> PromptTemplateData:
        if self.story_text is not None and self.story_text.count("{story}") != 1:
            raise ValueError(f"template {self.id}: story_text needs exactly one {{story}} slot")
        if "{" in self.fallback:
            raise ValueError(f"template {self.id}: fallback cannot contain a slot")
        return self


class RoundData(_Frozen):
    key: str = Field(pattern=KEY_PATTERN)
    ordinal: int = Field(ge=1, le=20)
    theme: str = Field(min_length=3, max_length=120)
    question_family: str = Field(pattern=KEY_PATTERN)
    competency_keys: tuple[str, ...] = Field(min_length=1)
    claim_subjects: tuple[str, ...] = ()
    templates: tuple[PromptTemplateData, ...] = Field(min_length=1)


class RoleFamilyData(_Frozen):
    levels: tuple[str, ...] = Field(min_length=1)
    rounds: tuple[RoundData, ...] = Field(min_length=1)


class CompetencyData(_Frozen):
    evidence_terms: tuple[str, ...] = Field(min_length=1)


class QuestionFamilyData(_Frozen):
    description: str = Field(min_length=3, max_length=200)


class CompanyData(_Frozen):
    aliases: tuple[str, ...] = Field(min_length=1)
    process_terms: tuple[str, ...] = ()


class TaxonomyDocument(_Frozen):
    schema_: str = Field(alias="schema")
    version: int = Field(ge=1)
    question_families: dict[str, QuestionFamilyData]
    competencies: dict[str, CompetencyData]
    companies: dict[str, CompanyData]
    role_families: dict[str, RoleFamilyData]

    @model_validator(mode="after")
    def _consistent(self) -> TaxonomyDocument:
        if self.schema_ != TAXONOMY_SCHEMA:
            raise ValueError("unknown taxonomy schema")
        for group in (self.question_families, self.competencies, self.companies, self.role_families):
            for key in group:
                if not _KEY.fullmatch(key):
                    raise ValueError(f"bad key {key!r}")
        aliases: dict[str, str] = {}
        for company, data in self.companies.items():
            for alias in (company, *data.aliases):
                folded = alias.strip().casefold()
                if aliases.setdefault(folded, company) != company:
                    raise ValueError(f"alias {alias!r} names two companies")
        template_ids: set[str] = set()
        for family, data in self.role_families.items():
            if NOT_SURE not in data.levels or len(set(data.levels)) != len(data.levels):
                raise ValueError(f"{family}: levels must be unique and include {NOT_SURE!r}")
            if any(not _KEY.fullmatch(level) for level in data.levels):
                raise ValueError(f"{family}: bad level key")
            keys = [r.key for r in data.rounds]
            ordinals = [r.ordinal for r in data.rounds]
            if len(set(keys)) != len(keys) or len(set(ordinals)) != len(ordinals):
                raise ValueError(f"{family}: round keys and ordinals must be unique")
            for round_ in data.rounds:
                if round_.question_family not in self.question_families:
                    raise ValueError(f"{family}.{round_.key}: unknown question family")
                for key in round_.competency_keys:
                    if key not in self.competencies:
                        raise ValueError(f"{family}.{round_.key}: unknown competency {key!r}")
                for template in round_.templates:
                    if template.competency_key not in round_.competency_keys:
                        raise ValueError(f"{template.id}: competency is not one this round practises")
                    if template.id in template_ids:
                        raise ValueError(f"duplicate template id {template.id}")
                    template_ids.add(template.id)
        return self


class Taxonomy:
    """Validated, hash-checked taxonomy with lookups. Instances are immutable in practice."""

    def __init__(self, document: TaxonomyDocument, sha256: str) -> None:
        self.document = document
        self.sha256 = sha256
        self._aliases = {
            alias.strip().casefold(): company
            for company, data in document.companies.items()
            for alias in (company, *data.aliases)
        }

    @property
    def version(self) -> int:
        return self.document.version

    def company_key(self, label: str) -> str | None:
        """Exact, case-insensitive alias match only; never a fuzzy guess."""
        return self._aliases.get(label.strip().casefold())

    def process_terms(self, company_key: str | None) -> tuple[str, ...]:
        data = self.document.companies.get(company_key or "")
        return data.process_terms if data else ()

    def has_role_family(self, role_family: str) -> bool:
        return role_family in self.document.role_families

    def levels(self, role_family: str) -> tuple[str, ...]:
        data = self.document.role_families.get(role_family)
        return data.levels if data else ()

    def rounds(self, role_family: str) -> tuple[Any, ...]:
        """Practice rounds for a role family, in ordinal order (empty for an unknown family)."""
        from .target_rounds import practice_rounds_for  # local import: target_rounds builds the models

        return practice_rounds_for(self, role_family)

    def competency_terms(self, key: str) -> tuple[str, ...]:
        data = self.document.competencies.get(key)
        return data.evidence_terms if data else ()


def taxonomy_from_dict(raw: dict[str, Any]) -> Taxonomy:
    """An unlocked taxonomy built from data (tests and dry runs); validated the same way."""
    try:
        document = TaxonomyDocument.model_validate(raw)
    except ValueError as exc:
        raise TaxonomyError(str(exc)) from exc
    return Taxonomy(document, content_sha256(json.dumps(raw, sort_keys=True).encode("utf-8")))


@lru_cache(maxsize=1)
def load_taxonomy() -> Taxonomy:
    """The repository taxonomy, refused unless its bytes match LOCK.json."""
    path = CONTENT_DIR / TAXONOMY_FILE
    try:
        raw = path.read_bytes()
        lock = json.loads((CONTENT_DIR / "LOCK.json").read_text(encoding="utf-8"))
        entry = lock["taxonomies"][TAXONOMY_FILE]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise TaxonomyError("taxonomy or its lock entry is unreadable") from exc
    digest = content_sha256(raw)
    if digest != entry.get("sha256"):
        raise TaxonomyError("taxonomy bytes do not match LOCK.json")
    try:
        document = TaxonomyDocument.model_validate(json.loads(raw.decode("utf-8")))
    except ValueError as exc:
        raise TaxonomyError(str(exc)) from exc
    if document.version != entry.get("version"):
        raise TaxonomyError("taxonomy version does not match LOCK.json")
    return Taxonomy(document, digest)
