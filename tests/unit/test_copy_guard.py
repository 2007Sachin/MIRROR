"""Copy guard: banned words, the lint script, and the report regeneration check."""

import asyncio
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.copy_guard import clean_or_fallback, find_banned, find_soft
from app.verdict_service import (
    SAFE_CONFIDENCE_NOTE,
    SAFE_ROOT_CAUSE,
    SAFE_SUMMARY,
    VerdictLanguageService,
)
from app.verdict_models import VerdictLanguageOutput

ROOT = Path(__file__).parents[2]


def test_banned_words_match_whole_words_and_inflections() -> None:
    assert find_banned("Your evidence was strong")
    assert find_banned("We were EVALUATING the answers")
    assert find_banned("A red flag appeared")
    assert find_banned("That was wrong")
    assert find_banned("Diagnostics are ready")


def test_identifiers_and_class_names_do_not_trigger() -> None:
    for text in ("diagnostic_id", "gap-3", "evidence_direction", "is-failed", "Contest results"):
        assert find_banned(text) == [], text


def test_soft_avoid_words_only_suggest() -> None:
    assert find_soft("Your claims are clear")
    assert find_banned("Your claims are clear") == []


def test_clean_text_passes_and_dirty_text_falls_back() -> None:
    assert clean_or_fallback("You explained that clearly.", "fallback", field="test") == "You explained that clearly."
    assert clean_or_fallback("Your score was low.", "fallback", field="test") == "fallback"
    assert clean_or_fallback("", "fallback", field="test") == "fallback"


class _Runner:
    """Returns queued verdict outputs so regeneration can be checked without a model."""

    def __init__(self, outputs: list[dict[str, str]]) -> None:
        self.outputs = outputs
        self.calls = 0

    async def run(self, *_args, **_kwargs):
        output = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return SimpleNamespace(success=True, output=output)


CLEAN = {
    "verdict_summary": "Thank you for your time. Several parts of your story came through clearly.",
    "root_cause_explanation": "One small place to start is describing what you led yourself.",
    "confidence_note": "This comes from one conversation, so it can only show so much.",
}
DIRTY = {**CLEAN, "verdict_summary": "Your assessment shows a weakness in ownership."}


def _write(outputs: list[dict[str, str]]):
    runner = _Runner(outputs)
    result = asyncio.run(VerdictLanguageService(runner).write(None, session_id=uuid4(), user_id=uuid4()))
    return runner, result


def test_clean_report_language_is_generated_once() -> None:
    runner, result = _write([CLEAN])
    assert runner.calls == 1
    assert isinstance(result, VerdictLanguageOutput)
    assert result.verdict_summary == CLEAN["verdict_summary"]


def test_banned_word_triggers_one_regeneration() -> None:
    runner, result = _write([DIRTY, CLEAN])
    assert runner.calls == 2
    assert result.verdict_summary == CLEAN["verdict_summary"]


def test_still_dirty_after_retry_falls_back_only_for_that_field() -> None:
    runner, result = _write([DIRTY, DIRTY])
    assert runner.calls == 2
    assert result.verdict_summary == SAFE_SUMMARY
    assert result.root_cause_explanation == CLEAN["root_cause_explanation"]
    assert SAFE_ROOT_CAUSE and SAFE_CONFIDENCE_NOTE


def test_copy_lint_script_passes_on_the_repository() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "copy_lint.py"), "--quiet"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout
