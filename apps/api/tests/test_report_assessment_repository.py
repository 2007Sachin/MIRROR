from __future__ import annotations

import asyncio
from typing import Any, cast
from uuid import uuid4

import pytest

from app.target_assessment_contract import AssessmentContractUnavailable, TargetAssessmentScopeResolver
from app.report_service import SupabaseReportRepository
from tests.test_assessment_contract import target_scope_inputs


class OwnerScopedTargetStore:
    def __init__(self, target, blueprint, link):
        self.target = target
        self.blueprint = blueprint
        self.link = link

    async def link_for_session(self, session_id, user_id):
        if self.link.session_id == session_id and self.link.user_id == user_id:
            return self.link
        return None

    async def get_target(self, target_id, user_id):
        if self.target.id == target_id and self.target.user_id == user_id:
            return self.target
        return None

    async def blueprints(self, target_id, user_id):
        if self.blueprint.candidate_target_id == target_id and self.blueprint.user_id == user_id:
            return [self.blueprint]
        return []


@pytest.mark.asyncio
async def test_report_repository_resolves_exact_owner_scoped_target_contract() -> None:
    user_id, session_id, role_profile_id, target, blueprint, link = target_scope_inputs()
    repository = object.__new__(SupabaseReportRepository)
    repository._scope_reader = cast(Any, TargetAssessmentScopeResolver(cast(Any, OwnerScopedTargetStore(target, blueprint, link))))

    scope = await repository.get_target_assessment_scope(session_id, user_id, role_profile_id)

    assert scope is not None
    assert scope.target_id == target.id
    assert scope.role_profile_id == role_profile_id
    assert scope.round_key == link.round_key
    assert scope.competency_keys == (
        "structured_problem_solving",
        "quantitative_reasoning",
        "business_judgement",
    )
    assert scope.provenance_class == "MIRROR_GENERATED"


@pytest.mark.asyncio
async def test_report_repository_rejects_session_role_profile_mismatch() -> None:
    user_id, session_id, _, target, blueprint, link = target_scope_inputs()
    repository = object.__new__(SupabaseReportRepository)
    repository._scope_reader = cast(Any, TargetAssessmentScopeResolver(cast(Any, OwnerScopedTargetStore(target, blueprint, link))))

    with pytest.raises(AssessmentContractUnavailable):
        await repository.get_target_assessment_scope(session_id, user_id, uuid4())
