"""Originality guard for Mirror-written practice prompts (Loop 2 P1).

A prompt must be Mirror's own words: no reuse of research excerpts, no banned interface words
(shared with the copy lint), no company attribution, and no repeat of the person's recent prompts.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.copy_guard import BANNED_PATTERNS
from app.prompt_originality import (
    ORIGINALITY_RULES_VERSION,
    GuardContext,
    RecentPrompt,
    check_prompt,
    excerpts_from_catalog,
    novelty_sha256,
)
from app.research_catalog import load_catalog

TODAY = date(2026, 10, 4)
ORIGINAL = "Pick a part of your billing service you would split into a few classes. Walk me through the pieces and why."


def _ctx(**overrides) -> GuardContext:
    values = {
        "source_excerpts": excerpts_from_catalog(load_catalog()),
        "company_names": ("Amazon",),
        "recent_prompts": (),
        "today": TODAY,
    }
    values.update(overrides)
    return GuardContext(**values)


def test_rules_are_versioned() -> None:
    assert ORIGINALITY_RULES_VERSION == "originality-1"


def test_an_original_prompt_passes() -> None:
    result = check_prompt(ORIGINAL, _ctx())
    assert (result.ok, result.reason) == (True, None)


def test_catalog_excerpts_feed_the_guard() -> None:
    excerpts = excerpts_from_catalog(load_catalog())
    assert "Your loop will include four 55-minute interviews" in excerpts
    assert len(excerpts) >= 20


def test_shape_limits() -> None:
    assert check_prompt("Too short?", _ctx()).reason == "SHAPE"
    assert check_prompt("x " * 300, _ctx()).reason == "SHAPE"
    assert check_prompt("Walk me through https://example.com/design and what you would change there.", _ctx()).reason == "SHAPE"


def test_reusing_source_wording_is_rejected_even_with_light_edits() -> None:
    verbatim = "Expect to be asked to write syntactically correct code with no pseudo code in this round."
    assert check_prompt(verbatim, _ctx()).reason == "SOURCE_OVERLAP"
    edited = "In this practice, how would you write scalable, robust, and well-made code for a queue?"
    assert check_prompt(edited, _ctx()).reason == "SOURCE_OVERLAP"


def test_short_excerpts_are_still_protected() -> None:
    context = _ctx(source_excerpts=("meet the hiring team",))
    assert check_prompt("Imagine you meet the hiring team today; how do you open the chat?", context).reason == "SOURCE_OVERLAP"


def test_banned_interface_words_are_rejected_using_the_shared_list() -> None:
    assert BANNED_PATTERNS  # same list as the copy lint
    assert check_prompt("How would you test a cache that expires items after a minute?", _ctx()).reason == "BANNED_TERM"
    assert check_prompt("Describe a failure you learned from while building a small service.", _ctx()).reason == "BANNED_TERM"


def test_no_company_attribution_in_any_form() -> None:
    for text in (
        "Amazon asks this one: design a service that shortens long links for sharing.",
        "This is a common amazon style question about designing a parking garage system.",
        "Tell me about a time you showed one of the Leadership Principles in your project.",
        "This is a real interview question: design a cache for a busy product page.",
        "Practise what the Bar Raiser will ask about a project you led last year.",
    ):
        assert check_prompt(text, _ctx()).reason == "COMPANY_ATTRIBUTION", text


def test_recent_prompts_are_not_repeated() -> None:
    recent = (RecentPrompt(text=ORIGINAL, served_on=TODAY - timedelta(days=3)),)
    assert check_prompt(ORIGINAL, _ctx(recent_prompts=recent)).reason == "REPEAT"

    near = ORIGINAL.replace("billing service", "payments service")
    assert check_prompt(near, _ctx(recent_prompts=recent)).reason == "REPEAT"

    old = (RecentPrompt(text=near, served_on=TODAY - timedelta(days=31)),)
    assert check_prompt(ORIGINAL, _ctx(recent_prompts=old)).ok


def test_novelty_hash_ignores_case_punctuation_and_spacing() -> None:
    assert novelty_sha256("Walk me  through it!") == novelty_sha256("walk me through it")
    assert len(novelty_sha256("x")) == 64


def test_every_seeded_excerpt_is_itself_rejected_as_a_prompt() -> None:
    context = _ctx()
    for excerpt in context.source_excerpts:
        assert not check_prompt(f"{excerpt} Talk me through your approach here.", context).ok, excerpt
