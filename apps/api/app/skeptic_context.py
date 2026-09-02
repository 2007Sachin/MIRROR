from __future__ import annotations

import re
from uuid import UUID

from .claims_models import ClaimSource
from .skeptic_models import (
    SkepticClaim,
    SkepticContext,
    SkepticRelation,
)
from .skeptic_repository import SkepticRepository


TOKEN_PATTERN = re.compile(r"[a-z0-9+#.]{3,}")
STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "also",
        "been",
        "built",
        "from",
        "have",
        "into",
        "that",
        "their",
        "then",
        "they",
        "this",
        "using",
        "with",
    }
)


def _tokens(value: str) -> set[str]:
    return {token for token in TOKEN_PATTERN.findall(value.casefold()) if token not in STOP_WORDS}


class SkepticContextBuilder:
    """Builds a bounded Claims Graph subset instead of forwarding all candidate data."""

    def __init__(self, repository: SkepticRepository) -> None:
        self._repository = repository

    async def build(self, turn_id: UUID) -> SkepticContext:
        data = await self._repository.load_retrieval_data(turn_id)
        query_tokens = _tokens(data.current_turn.text)
        for turn in data.prior_turns[-4:]:
            query_tokens |= _tokens(turn.text)

        entity_by_id = {entity.id: entity for entity in data.entities}
        scored: list[tuple[int, SkepticClaim]] = []
        for claim in data.claims:
            claim_tokens = _tokens(claim.claim_text)
            entity_tokens: set[str] = set()
            for entity_id in claim.related_entity_ids:
                entity = entity_by_id.get(entity_id)
                if entity:
                    entity_tokens |= _tokens(entity.canonical_name)
            score = len(query_tokens & claim_tokens) * 2 + len(query_tokens & entity_tokens) * 4
            if claim.source == ClaimSource.SPOKEN.value:
                score += 1
            scored.append((score, claim))

        selected = [claim for score, claim in sorted(scored, key=lambda row: row[0], reverse=True) if score > 0]
        if not selected:
            selected = [claim for _, claim in scored[:20]]
        selected = selected[:40]
        selected_claim_ids = {claim.id for claim in selected}
        selected_entity_ids = {
            entity_id for claim in selected for entity_id in claim.related_entity_ids
        }
        relations = [
            relation
            for relation in data.relations
            if relation.source_entity_id in selected_claim_ids
            or relation.target_entity_id in selected_claim_ids
        ][:160]
        selected_entity_ids |= {
            identifier
            for relation in relations
            for node_type, identifier in (
                (relation.source_entity_type, relation.source_entity_id),
                (relation.target_entity_type, relation.target_entity_id),
            )
            if node_type.upper() == "ENTITY"
        }
        entities = [
            entity for entity in data.entities if entity.id in selected_entity_ids
        ][:80]
        projects = [
            entity
            for entity in entities
            if entity.entity_type.upper() == "PROJECT"
        ][:20]
        return SkepticContext(
            session_id=data.session_id,
            current_turn=data.current_turn,
            related_resume_claims=self._source(selected, ClaimSource.RESUME),
            related_spoken_claims=self._source(selected, ClaimSource.SPOKEN),
            relevant_prior_turns=data.prior_turns[-8:],
            current_project_context=projects,
            current_phase=data.current_turn.phase,
            entities=entities,
            claim_relations=[SkepticRelation.model_validate(item) for item in relations],
        )

    @staticmethod
    def _source(claims: list[SkepticClaim], source: ClaimSource) -> list[SkepticClaim]:
        return [claim for claim in claims if claim.source == source.value][:40]

