"""Versioned research catalog for interview intelligence (repo JSON, read-only at runtime).

Curated, Verifier-approved research lives as ``research_content/catalog_v<N>.json`` with a
``LOCK.json`` of content hashes. ``load_catalog`` is the single loader: it verifies the lock,
validates research policy (docs/mirror-company/RESEARCH_POLICY.md) and returns a read-only
catalog. Nothing here performs I/O beyond reading the content directory.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

CONTENT_DIR = Path(__file__).parent / "research_content"
LOCK_FILE = "LOCK.json"
SCHEMA = "mirror.research_catalog/1"

ProvenanceClass = Literal["FACT", "SUPPORTED_PATTERN", "CANDIDATE_REPORTED", "INFERENCE", "MIRROR_GENERATED"]
Band = Literal["LOW", "MEDIUM", "HIGH"]
Tier = Literal["T1_OFFICIAL", "T2_REPUTABLE", "T3_CANDIDATE_REPORTED", "T4_AGGREGATOR"]
Status = Literal["DRAFT", "PUBLISHED", "SUPERSEDED", "WITHDRAWN"]
KEY_PATTERN = r"^[a-z0-9][a-z0-9_]{0,62}$"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Scope(_Frozen):
    company: str = Field(pattern=KEY_PATTERN)
    role_family: str = Field(pattern=KEY_PATTERN)  # "all" = every role family
    level: str = Field(pattern=KEY_PATTERN)  # "all" = every level
    geography: str = Field(pattern=KEY_PATTERN)  # literal key; "global" is NOT a wildcard


class Source(_Frozen):
    id: str
    url: str = Field(pattern=r"^https://")
    publisher: str = Field(min_length=1, max_length=160)
    tier: Tier
    official: bool
    published_at: date | None
    retrieved_at: date
    text_sha256_prefix: str = Field(pattern=r"^[0-9a-f]{16,64}$")
    independence_group: str = Field(pattern=KEY_PATTERN)
    access_note: str = Field(min_length=1, max_length=500)


class Evidence(_Frozen):
    source_id: str
    stance: Literal["SUPPORTS", "CONTRADICTS", "CONTEXT"]
    excerpt: str = Field(min_length=1, max_length=300)


class Claim(_Frozen):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.]{2,159}$")
    version: int = Field(ge=1)
    verifier_ref: str = Field(min_length=1, max_length=40)
    status: Status
    provenance_class: ProvenanceClass
    dating: Literal["PUBLISHED_DATE", "RETRIEVED_ONLY"]
    freshness: Literal["CURRENT", "UNVERIFIED", "OLDER"]
    published_at: date | None
    retrieved_at: date
    confidence_band: Band
    confidence_features: dict[str, Any]
    scope: Scope
    subject: str = Field(pattern=KEY_PATTERN)
    predicate: str = Field(pattern=KEY_PATTERN)
    value: Any
    statement: str = Field(min_length=1, max_length=500)
    limits: tuple[str, ...]
    process_content: bool
    candidate_visible: bool
    conflict_set: str | None
    staleness_flags: tuple[str, ...]
    supersedes: int | None
    basis_claim_ids: tuple[str, ...]
    evidence: tuple[Evidence, ...]


class ConflictSet(_Frozen):
    key: str
    claim_ids: tuple[str, ...]
    resolution: Literal["UNRESOLVED"]
    note: str = Field(min_length=1, max_length=500)


class Unknown(_Frozen):
    key: str
    scope: Scope
    reason: Literal["NOT_PUBLISHED", "NOT_DATED", "CONFLICT", "POSSIBLY_STALE", "SCOPE_MISMATCH"]
    note: str = Field(min_length=1, max_length=500)
    related_claim_ids: tuple[str, ...]


class VerifierReceipt(_Frozen):
    ref: str = Field(min_length=1, max_length=200)
    verdict: Literal["PASS", "PASS_WITH_LIMITS"]


class CatalogDocument(_Frozen):
    schema_: Literal["mirror.research_catalog/1"] = Field(alias="schema")
    version: int = Field(ge=1)
    status: Status
    supersedes_version: int | None
    verifier_receipt: VerifierReceipt | None
    sources: tuple[Source, ...]
    claims: tuple[Claim, ...]
    conflict_sets: tuple[ConflictSet, ...]
    unknowns: tuple[Unknown, ...]


class CatalogError(ValueError):
    """Raised when catalog content, lock or policy is invalid. ``codes`` lists every violation."""

    def __init__(self, codes: Sequence[str]) -> None:
        self.codes = tuple(codes)
        super().__init__("; ".join(self.codes))


def content_sha256(raw: bytes) -> str:
    """Hash of file content with line endings normalised (git autocrlf must not break the lock)."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


class ResearchCatalog(Protocol):
    """The one read interface every consumer uses (a DB-backed catalog can replace it later)."""

    @property
    def version(self) -> int: ...

    @property
    def content_sha256(self) -> str: ...

    @property
    def claims(self) -> tuple[Claim, ...]: ...


class RepoResearchCatalog:
    def __init__(self, document: CatalogDocument, sha256: str) -> None:
        self._document = document
        self._sha256 = sha256

    @property
    def version(self) -> int:
        return self._document.version

    @property
    def content_sha256(self) -> str:
        return self._sha256

    @property
    def claims(self) -> tuple[Claim, ...]:
        return self._document.claims

    @property
    def document(self) -> CatalogDocument:
        return self._document


def parse_document(raw: bytes) -> CatalogDocument:
    return CatalogDocument.model_validate(json.loads(raw.decode("utf-8")))


# v1 policy: candidate reports are never seeded (owner/Verifier decision, loop2_reconciled_design R8).
CANDIDATE_REPORTED_PUBLISHABLE = False
SUPPORTED_PATTERN_MIN_INDEPENDENT = 3


def _claim_codes(claim: Claim, sources: dict[str, Source], published_catalog: bool) -> list[str]:
    codes: list[str] = []
    cid = claim.id
    supporting: list[Source] = []
    for item in claim.evidence:
        source = sources.get(item.source_id)
        if source is None:
            codes.append(f"unknown_source:{cid}:{item.source_id}")
        elif item.stance == "SUPPORTS":
            supporting.append(source)
    if not any(item.stance == "SUPPORTS" for item in claim.evidence):
        codes.append(f"no_supporting_evidence:{cid}")

    kind = claim.provenance_class
    if kind == "FACT" and not any(s.tier == "T1_OFFICIAL" and s.official for s in supporting):
        codes.append(f"fact_requires_t1_official:{cid}")
    if kind == "CANDIDATE_REPORTED":
        if claim.confidence_band != "LOW":
            codes.append(f"candidate_reported_must_be_low:{cid}")
        if published_catalog and not CANDIDATE_REPORTED_PUBLISHABLE:
            codes.append(f"candidate_reported_not_publishable:{cid}")
    if kind == "SUPPORTED_PATTERN":
        groups = {s.independence_group for s in supporting}
        if len(groups) < SUPPORTED_PATTERN_MIN_INDEPENDENT:
            codes.append(f"supported_pattern_needs_3_independent:{cid}")
    if kind == "INFERENCE" and not claim.basis_claim_ids:
        codes.append(f"inference_needs_basis:{cid}")
    if kind == "MIRROR_GENERATED":
        codes.append(f"mirror_generated_not_research:{cid}")

    if claim.published_at is None:
        if claim.dating != "RETRIEVED_ONLY":
            codes.append(f"undated_claim_must_be_retrieved_only:{cid}")
        if claim.freshness != "UNVERIFIED":
            codes.append(f"undated_claim_freshness_unverified:{cid}")
    if claim.freshness == "UNVERIFIED" and claim.confidence_band == "HIGH":
        codes.append(f"unverified_freshness_band_capped:{cid}")
    if published_catalog and claim.status != "PUBLISHED":
        codes.append(f"unpublished_claim_in_published_catalog:{cid}")
    return codes


def validate_document(document: CatalogDocument) -> list[str]:
    """Every research-policy violation in ``document`` as a stable code (empty = valid)."""
    published = document.status == "PUBLISHED"
    codes: list[str] = []
    if published and document.verifier_receipt is None:
        codes.append("published_without_verifier_receipt")
    sources = {source.id: source for source in document.sources}
    seen: set[str] = set()
    for claim in document.claims:
        if claim.id in seen:
            codes.append(f"duplicate_claim:{claim.id}")
        seen.add(claim.id)
        codes.extend(_claim_codes(claim, sources, published))

    sets = {conflict.key: conflict for conflict in document.conflict_sets}
    for conflict in document.conflict_sets:
        if len(set(conflict.claim_ids)) < 2:
            codes.append(f"conflict_set_needs_2_claims:{conflict.key}")
    for claim in document.claims:
        if claim.conflict_set is None:
            continue
        conflict = sets.get(claim.conflict_set)
        if conflict is None:
            codes.append(f"unknown_conflict_set:{claim.id}:{claim.conflict_set}")
        elif claim.id not in conflict.claim_ids:
            codes.append(f"conflict_membership_mismatch:{claim.id}")
    by_id = {claim.id: claim for claim in document.claims}
    for conflict in document.conflict_sets:
        for member in conflict.claim_ids:
            if member not in by_id or by_id[member].conflict_set != conflict.key:
                codes.append(f"conflict_membership_mismatch:{member}")

    if published and not document.unknowns:
        codes.append("unknowns_required")
    for unknown in document.unknowns:
        for related in unknown.related_claim_ids:
            if related not in by_id:
                codes.append(f"unknown_references_missing_claim:{unknown.key}:{related}")
    return sorted(set(codes))


def load_catalog(content_dir: Path = CONTENT_DIR, version: int | None = None) -> RepoResearchCatalog:
    lock = json.loads((content_dir / LOCK_FILE).read_text(encoding="utf-8"))
    entries = lock["catalogs"]
    documents: dict[int, tuple[CatalogDocument, str]] = {}
    codes: list[str] = []
    for name, entry in sorted(entries.items(), key=lambda item: item[1]["version"]):
        raw = (content_dir / name).read_bytes()
        sha = content_sha256(raw)
        if sha != entry["sha256"]:
            raise CatalogError([f"lock_mismatch:{name}"])
        document = parse_document(raw)
        if document.version != entry["version"]:
            codes.append(f"version_mismatch:{name}")
        codes.extend(validate_document(document))
        documents[document.version] = (document, sha)
    codes.extend(validate_history([document for document, _ in documents.values()]))
    if codes:
        raise CatalogError(sorted(set(codes)))
    chosen = version if version is not None else max(documents)
    if chosen not in documents:
        raise CatalogError([f"version_not_locked:{chosen}"])
    document, sha = documents[chosen]
    return RepoResearchCatalog(document, sha)


def _claim_hash(claim: Claim) -> str:
    canonical = json.dumps(claim.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_history(documents: Sequence[CatalogDocument]) -> list[str]:
    """Published entries are immutable: any change must appear as a new claim/catalog version."""
    ordered = sorted(documents, key=lambda document: document.version)
    codes: list[str] = []
    if [document.version for document in ordered] != list(range(1, len(ordered) + 1)):
        codes.append("catalog_versions_not_contiguous")
    seen: dict[tuple[str, int], str] = {}
    latest: dict[str, int] = {}
    latest_scope: dict[str, Scope] = {}
    for document in ordered:
        if document.version > 1 and document.supersedes_version != document.version - 1:
            codes.append(f"catalog_version_must_supersede_previous:{document.version}")
        for claim in document.claims:
            key = (claim.id, claim.version)
            digest = _claim_hash(claim)
            if key in seen:
                if seen[key] != digest:
                    codes.append(f"published_claim_mutated:{claim.id}@{claim.version}")
                continue
            previous = latest.get(claim.id)
            if previous is not None:
                previous_scope = latest_scope[claim.id]
                for field in ("company", "role_family", "level", "geography"):
                    if getattr(claim.scope, field) != getattr(previous_scope, field):
                        codes.append(f"claim_scope_changed:{claim.id}@{claim.version}:{field}")
                if claim.version < previous:
                    codes.append(f"claim_version_regressed:{claim.id}@{claim.version}")
                elif claim.supersedes != previous:
                    codes.append(f"claim_version_must_supersede_previous:{claim.id}@{claim.version}")
            elif claim.version > 1 and claim.supersedes is None:
                codes.append(f"claim_version_must_supersede_previous:{claim.id}@{claim.version}")
            seen[key] = digest
            latest[key[0]] = max(claim.version, previous or 0)
            latest_scope[claim.id] = claim.scope
    return sorted(set(codes))


# ------------------------------------------------------------------ exact scope matching

MatchState = Literal["RESEARCHED", "GENERAL_ONLY", "NOT_RESEARCHED"]
ALL = "all"


class TargetScope(_Frozen):
    """A person's target, already normalised to catalog keys. ``None`` = not sure / not given."""

    company: str = Field(pattern=KEY_PATTERN)
    role_family: str = Field(pattern=KEY_PATTERN)
    level: str | None = Field(default=None, pattern=KEY_PATTERN)
    geography: str | None = Field(default=None, pattern=KEY_PATTERN)


class ScopeMatch(_Frozen):
    state: MatchState
    catalog_version: int
    content_sha256: str
    claims: tuple[Claim, ...]
    conflict_sets: tuple[ConflictSet, ...]
    unknowns: tuple[Unknown, ...]


def _covers(scope: Scope, target: TargetScope) -> bool:
    # Geography is exact (owner decision): "global" never stands in for a specific location,
    # and a target without a location matches nothing.
    return (
        scope.company == target.company
        and scope.role_family in (ALL, target.role_family)
        and (scope.level == ALL or (target.level is not None and scope.level == target.level))
        and target.geography is not None
        and scope.geography == target.geography
    )


def match_scope(catalog: RepoResearchCatalog, target: TargetScope) -> ScopeMatch:
    """Claims, conflicts and unknowns that apply to exactly this target. Never widens."""
    document = catalog.document
    claims = tuple(c for c in document.claims if c.candidate_visible and _covers(c.scope, target))
    keys = {claim.conflict_set for claim in claims if claim.conflict_set}
    conflicts = tuple(conflict for conflict in document.conflict_sets if conflict.key in keys)
    unknowns = tuple(unknown for unknown in document.unknowns if _covers(unknown.scope, target))
    process = [claim for claim in claims if claim.process_content]
    if any(claim.scope.level != ALL for claim in process):
        state: MatchState = "RESEARCHED"
    elif process:
        state = "GENERAL_ONLY"
    else:
        state = "NOT_RESEARCHED"
    return ScopeMatch(
        state=state,
        catalog_version=catalog.version,
        content_sha256=catalog.content_sha256,
        claims=claims,
        conflict_sets=conflicts,
        unknowns=unknowns,
    )
