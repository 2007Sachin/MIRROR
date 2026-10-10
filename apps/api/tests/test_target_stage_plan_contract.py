from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.target_repository import CandidateStagePlanInput


def test_stage_plan_requires_canonical_lowercase_uuid_and_exact_keys():
    stage = {"stage_id": str(uuid4()).upper(), "kind": "OTHER", "custom_label": "Take-home", "certainty": "SURE", "sequence": 1}
    with pytest.raises(ValidationError):
        CandidateStagePlanInput.model_validate({"state": "KNOWN", "order_known": True, "stages": [stage], "notes": {}})


def test_stage_plan_accepts_valid_known_order_and_bounds_note_text():
    stage_id = str(uuid4())
    stage = {"stage_id": stage_id, "kind": "OTHER", "custom_label": "Take-home", "certainty": "SURE", "sequence": 1}
    plan = CandidateStagePlanInput.model_validate({"state": "KNOWN", "order_known": True, "stages": [stage], "notes": {stage_id: "x" * 500}})
    assert plan.stages[0].sequence == 1
    with pytest.raises(ValidationError):
        CandidateStagePlanInput.model_validate({"state": "KNOWN", "order_known": True, "stages": [stage], "notes": {stage_id: "x" * 501}})


def test_stage_plan_rejects_missing_sequence_key():
    stage_id = str(uuid4())
    stage = {"stage_id": stage_id, "kind": "OTHER", "custom_label": "Take-home", "certainty": "SURE"}
    with pytest.raises(ValidationError):
        CandidateStagePlanInput.model_validate({
            "state": "KNOWN", "order_known": False, "stages": [stage], "notes": {},
        })


def test_stage_plan_rejects_extra_stage_key():
    stage_id = str(uuid4())
    stage = {
        "stage_id": stage_id, "kind": "OTHER", "custom_label": "Take-home",
        "certainty": "SURE", "sequence": 1, "verified": True,
    }
    with pytest.raises(ValidationError):
        CandidateStagePlanInput.model_validate({
            "state": "KNOWN", "order_known": True, "stages": [stage], "notes": {},
        })


def test_stage_plan_rejects_coercion_whitespace_null_and_invalid_order():
    stage_id = str(uuid4())
    stage = {"stage_id": stage_id, "kind": "OTHER", "custom_label": "Take-home", "certainty": "SURE", "sequence": 1}
    invalid = [
        {"state": "KNOWN", "order_known": True, "stages": [stage], "notes": {stage_id: " note "}},
        {"state": "KNOWN", "order_known": True, "stages": [stage], "notes": {stage_id: None}},
        {"state": "KNOWN", "order_known": True, "stages": [{**stage, "sequence": 1.0}], "notes": {}},
        {"state": "KNOWN", "order_known": "true", "stages": [stage], "notes": {}},
        {"state": "NOT_YET", "order_known": True, "stages": [], "notes": {}},
    ]
    for payload in invalid:
        with pytest.raises(ValidationError):
            CandidateStagePlanInput.model_validate(payload)
