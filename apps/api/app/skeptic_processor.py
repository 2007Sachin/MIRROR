from __future__ import annotations

import hashlib
import re
from uuid import UUID

from .claims_models import (
    ClaimChangedBy,
    ClaimCreate,
    ClaimEvidenceCreate,
    ClaimEvidenceType,
    ClaimNodeType,
    ClaimRelationCreate,
    ClaimRelationSource,
    ClaimRelationType,
    ClaimSource,
    ClaimStatus,
    EvidenceDirection,
    VerificationPriority,
)
from .claims_service import ClaimsGraphService
from .skeptic_models import (
    ObservationType,
    SkepticAnalysis,
    SkepticContext,
    SkepticProcessSummary,
)
from .skeptic_repository import SkepticRepository


INSTRUCTION_PATTERNS = (
    "ignore previous",
    "ignore the resume",
    "mark everything",
    "tell the system",
    "do not flag",
    "don't flag",
    "system prompt",
)
CONFLICT_MARKERS = re.compile(
    r"\b(i did not|i didn't|i never|not me|instead of|actually did not|was not involved)\b",
    re.IGNORECASE,
)


class SkepticOutputRejected(Exception):
    pass


class SkepticResultProcessor:
    def __init__(
        self, repository: SkepticRepository, claims: ClaimsGraphService
    ) -> None:
        self._repository = repository
        self._claims = claims

    async def process(
        self,
        raw: SkepticAnalysis | dict,
        context: SkepticContext,
        user_id: UUID,
        execution_id: UUID,
        *,
        shadow_mode: bool,
    ) -> SkepticProcessSummary:
        try:
            analysis = raw if isinstance(raw, SkepticAnalysis) else SkepticAnalysis.model_validate(raw)
        except ValueError as exc:
            raise SkepticOutputRejected("invalid Skeptic structured output") from exc
        self._validate_references(analysis, context)
        analysis = self._conservative_normalization(analysis, context)

        claims_created = 0
        proposals_created = 0
        observations_created = 0
        flags_created = 0
        allowed_entities = {entity.id for entity in context.entities}
        for proposed in analysis.new_claims:
            if self._instruction_like(proposed.claim_text):
                continue
            normalized = " ".join(proposed.claim_text.split())
            if await self._repository.spoken_claim_exists(
                user_id, proposed.source_turn_id, normalized
            ):
                continue
            claim = await self._claims.create_claim(
                user_id,
                ClaimCreate(
                    session_id=context.session_id,
                    claim_text=normalized,
                    claim_type=proposed.claim_type,
                    source=ClaimSource.SPOKEN,
                    source_reference=f"turn:{proposed.source_turn_id}",
                    confidence=proposed.confidence,
                    verification_priority=VerificationPriority.MEDIUM,
                ),
                changed_by=ClaimChangedBy.AI,
                reason="Skeptic shadow analysis extracted a spoken claim",
            )
            claims_created += 1
            await self._claims.link_evidence(
                claim.id,
                user_id,
                ClaimEvidenceCreate(
                    evidence_type=ClaimEvidenceType.INTERVIEW_TURN,
                    turn_id=proposed.source_turn_id,
                    evidence_direction=EvidenceDirection.CONTEXT_ONLY,
                    strength=proposed.confidence,
                ),
            )
            for entity_id in proposed.related_entity_ids:
                if entity_id not in allowed_entities:
                    continue
                await self._claims.create_relation(
                    user_id,
                    ClaimRelationCreate(
                        source_entity_type=ClaimNodeType.CLAIM,
                        source_entity_id=claim.id,
                        relation_type=ClaimRelationType.RELATED_TO,
                        target_entity_type=ClaimNodeType.ENTITY,
                        target_entity_id=entity_id,
                        confidence=proposed.confidence,
                        source=ClaimRelationSource.INTERVIEW,
                    ),
                )

        for proposal in analysis.claim_updates:
            key = self._key(
                "update",
                context.session_id,
                proposal.claim_id,
                proposal.proposed_status,
                *sorted(str(item) for item in proposal.related_turn_ids),
            )
            if await self._repository.create_claim_update_proposal(
                context.session_id,
                user_id,
                context.current_turn.id,
                execution_id,
                proposal,
                key,
            ):
                proposals_created += 1

        for observation in analysis.observations:
            if self._instruction_like(observation.summary):
                continue
            key = self._key(
                "observation",
                context.session_id,
                observation.observation_type,
                observation.summary.casefold(),
                *sorted(str(item) for item in observation.related_turn_ids),
            )
            if await self._repository.create_observation(
                context.session_id, user_id, execution_id, observation, key
            ):
                observations_created += 1

        for proposal in analysis.flag_proposals:
            if self._instruction_like(proposal.reason):
                continue
            key = self._key(
                "flag",
                context.session_id,
                proposal.claim_id or "none",
                proposal.flag_type,
                *sorted(str(item) for item in proposal.related_turn_ids),
            )
            if await self._repository.create_flag(
                context.session_id,
                user_id,
                context.current_turn.turn_index,
                execution_id,
                proposal,
                key,
                shadow_mode,
            ):
                flags_created += 1

        return SkepticProcessSummary(
            flags_created=flags_created,
            new_claims_created=claims_created,
            claim_update_proposals_created=proposals_created,
            observations_created=observations_created,
        )

    @staticmethod
    def _validate_references(analysis: SkepticAnalysis, context: SkepticContext) -> None:
        claim_ids = {
            claim.id
            for claim in context.related_resume_claims + context.related_spoken_claims
        }
        turn_ids = {context.current_turn.id} | {
            turn.id for turn in context.relevant_prior_turns
        }
        entity_ids = {entity.id for entity in context.entities}
        for claim in analysis.new_claims:
            if claim.source_turn_id != context.current_turn.id:
                raise SkepticOutputRejected("new claim source is outside current turn")
            if not set(claim.related_entity_ids) <= entity_ids:
                raise SkepticOutputRejected("new claim references unknown entities")
        for update in analysis.claim_updates:
            if update.claim_id not in claim_ids or not set(update.related_turn_ids) <= turn_ids:
                raise SkepticOutputRejected("claim update references unknown context")
        for observation in analysis.observations:
            if observation.source_turn_id != context.current_turn.id:
                raise SkepticOutputRejected("observation source is outside current turn")
            if not set(observation.related_claim_ids) <= claim_ids:
                raise SkepticOutputRejected("observation references unknown claims")
            if not set(observation.related_turn_ids) <= turn_ids:
                raise SkepticOutputRejected("observation references unknown turns")
        for flag in analysis.flag_proposals:
            if flag.source_turn_id != context.current_turn.id:
                raise SkepticOutputRejected("flag source is outside current turn")
            if flag.claim_id and flag.claim_id not in claim_ids:
                raise SkepticOutputRejected("flag references unknown claim")
            if not set(flag.related_turn_ids) <= turn_ids:
                raise SkepticOutputRejected("flag references unknown turns")

    @classmethod
    def _conservative_normalization(
        cls, analysis: SkepticAnalysis, context: SkepticContext
    ) -> SkepticAnalysis:
        if CONFLICT_MARKERS.search(context.current_turn.text):
            return analysis
        claims = {
            claim.id: claim
            for claim in context.related_resume_claims + context.related_spoken_claims
        }
        observations = [
            item.model_copy(
                update={
                    "observation_type": cls._fallback_type(
                        context.current_turn.text,
                        claims.get(item.related_claim_ids[0]).claim_text
                        if item.related_claim_ids and item.related_claim_ids[0] in claims
                        else "",
                    )
                }
            )
            if item.observation_type == ObservationType.CONTRADICTION
            else item
            for item in analysis.observations
        ]
        flags = [
            item.model_copy(
                update={
                    "flag_type": cls._fallback_type(
                        context.current_turn.text,
                        claims[item.claim_id].claim_text
                        if item.claim_id in claims
                        else "",
                    )
                }
            )
            if item.flag_type == ObservationType.CONTRADICTION
            else item
            for item in analysis.flag_proposals
        ]
        updates = [
            item.model_copy(update={"proposed_status": ClaimStatus.INSUFFICIENT_EVIDENCE})
            if item.proposed_status == ClaimStatus.CONTRADICTED
            else item
            for item in analysis.claim_updates
        ]
        return analysis.model_copy(
            update={"observations": observations, "flag_proposals": flags, "claim_updates": updates}
        )

    @staticmethod
    def _fallback_type(current_text: str, claim_text: str) -> ObservationType:
        lowered = current_text.casefold()
        if any(marker in lowered for marker in ("teammate", "team member", "our team")):
            return ObservationType.OWNERSHIP_DRIFT
        current_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", current_text))
        claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", claim_text))
        if current_numbers and claim_numbers and current_numbers != claim_numbers:
            return ObservationType.UNSUPPORTED_SCALE
        if any(marker in lowered for marker in ("different stage", "authentication", "environment")):
            return ObservationType.SCOPE_DIFFERENCE
        if any(marker in lowered for marker in ("later", "earlier", "timeline", "at first")):
            return ObservationType.TIMELINE_DIFFERENCE
        return ObservationType.CLARIFICATION

    @staticmethod
    def _instruction_like(value: str) -> bool:
        lowered = value.casefold()
        return any(pattern in lowered for pattern in INSTRUCTION_PATTERNS)

    @staticmethod
    def _key(*parts: object) -> str:
        return hashlib.sha256("\0".join(str(part) for part in parts).encode()).hexdigest()

