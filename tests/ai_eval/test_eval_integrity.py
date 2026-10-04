"""Adversarial checks of the evaluation oracle itself (offline)."""
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

import ai_eval_checks as checks

pytestmark = pytest.mark.ai_eval


def result(turn, *, domain_turn=None, status="COMPLETE"):
    domain = NS(evidence_turn_ids=[domain_turn], evidence_quotes=[]) if domain_turn else None
    return NS(assessor_type="TECHNICAL", status=status, evidence_turn_ids=[turn],
              evidence_quotes=[], dimensions=[domain] if domain else [],
              competency_or_domain_assessments=[])


def bundle(res):
    return NS(technical=NS(result_json=res), behaviour=None, claims=None)


def confident():
    return NS(availability_status="AVAILABLE", overall_signal_confidence=1,
              role_readiness_low=78, role_readiness_high=86,
              interview_readiness_low=78, interview_readiness_high=86, verdict_code="STRONG")


@pytest.mark.parametrize("collection", ["dimensions", "competency_or_domain_assessments"])
def test_domain_ids_without_quotes_are_checked(collection):
    real, ghost = uuid4(), uuid4()
    res = result(real)
    setattr(res, collection, [NS(evidence_turn_ids=[ghost], evidence_quotes=[])])
    assert checks.check_no_invented_evidence([res], {real: "Actual answer"})


def test_nonempty_invented_ids_do_not_support_confident_publishing():
    assert checks.check_no_numeric_publish_without_evidence(
        bundle(result(uuid4())), confident(), transcript={uuid4(): "Actual answer"})


def test_domain_invented_ids_invalidate_publishing_support():
    real = uuid4()
    assert checks.check_no_numeric_publish_without_evidence(
        bundle(result(real, domain_turn=uuid4())), confident(), transcript={real: "Actual answer"})


def test_valid_complete_ids_support_publishing_without_quotes():
    real = uuid4()
    assert checks.check_no_numeric_publish_without_evidence(
        bundle(result(real)), confident(), transcript={real: "Actual answer"}) == []


def test_incomplete_row_does_not_support_publishing():
    real = uuid4()
    assert checks.check_no_numeric_publish_without_evidence(
        bundle(result(real, status="NOT_ENOUGH_SIGNAL")), confident(), transcript={real: "Answer"})



def test_legacy_numeric_checker_call_fails_closed_without_transcript():
    assert checks.check_no_numeric_publish_without_evidence(bundle(result(uuid4())), confident())


def test_none_returning_service_checks_only_observable_contract():
    assert checks.check_safe_degradation(
        [{"name": "verdict", "content": None}], require_typed_error=False) == []


def test_none_returning_service_still_rejects_fabricated_content():
    assert checks.check_safe_degradation(
        [{"name": "verdict", "content": "invented"}], require_typed_error=False)


def test_default_degradation_still_requires_typed_failure():
    assert checks.check_safe_degradation([{"name": "planner", "content": None}])


def test_explicit_success_is_not_a_failure_result():
    assert checks.check_safe_degradation(
        [{"name": "verdict", "content": None, "success": True}], require_typed_error=False)


def test_optional_live_checks_reject_empty_and_failed_executions(monkeypatch):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parent / "live" / "test_eval_live_skeptic.py"
    spec = importlib.util.spec_from_file_location("offline_live_integrity", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.checks, "check_no_unsupported_criticism", lambda run: [])
    monkeypatch.setattr(module.checks, "check_p5_not_accused", lambda run: [])
    for test in (module.test_live_strong_answer_gets_no_unsupported_criticism,
                 module.test_live_honest_beginner_is_never_accused):
        for results in ([], [NS(success=False)], [NS(success=True), NS(success=False)]):
            monkeypatch.setattr(module, "_run", lambda cid, results=results: NS(worker_results=results))
            with pytest.raises(AssertionError):
                test()
        monkeypatch.setattr(module, "_run", lambda cid: NS(worker_results=[NS(success=True)]))
        test()
