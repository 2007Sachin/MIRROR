"""OPTIONAL live-model evaluation (thin scaffold, 2 scenarios).

Skipped unless BOTH hold:  MIRROR_LIVE_EVAL=1  AND  SARVAM_API_KEY is set in the process
environment (this file never reads .env files and never prints the key).  Also requires
MIRROR_LIVE_MODEL (the chat model id).  Never run in CI.  Costs real tokens.

    MIRROR_LIVE_EVAL=1 MIRROR_LIVE_MODEL=<model-id> SARVAM_API_KEY=... \
        .venv/Scripts/python.exe -m pytest tests/ai_eval/live -p no:cacheprovider -q

It reuses the deterministic harness and the SAME check functions, replacing only the fake
provider with the real ChatCompletionsProvider, so a model/prompt regression is reported
by exactly the checks that guard the deterministic suite.
"""
from __future__ import annotations

import os

import pytest

import ai_eval_checks as checks
import ai_eval_harness as h

pytestmark = pytest.mark.ai_eval


def live_enabled(env=os.environ) -> bool:
    return env.get("MIRROR_LIVE_EVAL") == "1" and bool(env.get("SARVAM_API_KEY")) and bool(env.get("MIRROR_LIVE_MODEL"))


pytestmark = [pytest.mark.ai_eval, pytest.mark.skipif(
    not live_enabled(), reason="live eval disabled: set MIRROR_LIVE_EVAL=1, SARVAM_API_KEY, MIRROR_LIVE_MODEL")]


def _run(cid):
    from app.agents.providers import ChatCompletionsProvider

    cand = h.build_candidate(cid)
    provider = ChatCompletionsProvider(os.environ["SARVAM_API_KEY"])
    runner = h.build_runner(provider, model=os.environ["MIRROR_LIVE_MODEL"], timeout_seconds=60)
    return h.run_sync(h.run_candidate(cand, provider, runner=runner, mode="active"))


def test_live_strong_answer_gets_no_unsupported_criticism():
    run = _run("P7")
    assert run.worker_results, "no live results"
    assert all(r.success for r in run.worker_results), "live execution failed"
    assert checks.check_no_unsupported_criticism(run) == []


def test_live_honest_beginner_is_never_accused():
    run = _run("P5")
    assert run.worker_results, "no live results"
    assert all(r.success for r in run.worker_results), "live execution failed"
    assert checks.check_p5_not_accused(run) == []
