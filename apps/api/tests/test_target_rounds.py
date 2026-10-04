"""Mirror practice rounds and their prompt packs: original, guarded, filled only from the person's own data."""

from datetime import date

import pytest

from app.prompt_originality import GuardContext, RecentPrompt, check_prompt, excerpts_from_catalog, novelty_sha256
from app.research_catalog import load_catalog
from app.target_rounds import (
    PACK_MIN,
    ROUNDS,
    CandidateMaterial,
    build_round_pack,
    get_round,
)

TODAY = date(2026, 10, 4)


def context(recent=(), excerpts=None):
    return GuardContext(
        source_excerpts=excerpts_from_catalog(load_catalog()) if excerpts is None else excerpts,
        company_names=("Amazon",),
        recent_prompts=tuple(recent),
        today=TODAY,
    )


def test_three_rounds_with_distinct_keys_and_enough_templates() -> None:
    assert [r.key for r in ROUNDS] == ["coding_reasoning", "system_design", "behavioural"]
    for round_ in ROUNDS:
        assert len(round_.templates) >= PACK_MIN + 2
        assert len({t.id for t in round_.templates}) == len(round_.templates)
        assert set(t.competency_key for t in round_.templates) <= set(round_.competency_keys)


def test_every_template_and_fallback_passes_the_originality_guard_with_real_excerpts() -> None:
    ctx = context()
    for round_ in ROUNDS:
        for template in round_.templates:
            texts = [template.fallback]
            if template.slot:
                texts.append(template.text.replace("{story}", "Moving billing to a new queue"))
            for text in texts:
                assert check_prompt(text, ctx).ok, (template.id, check_prompt(text, ctx).reason)


def test_pack_is_full_with_at_least_four_mirror_prompts() -> None:
    pack = build_round_pack(get_round("coding_reasoning"), CandidateMaterial(), context(), researched=False)
    assert pack.state == "FULL"
    assert len(pack.prompts) >= PACK_MIN
    assert [p.position for p in pack.prompts] == list(range(1, len(pack.prompts) + 1))
    assert all(p.provenance_class == "MIRROR_GENERATED" for p in pack.prompts)
    assert all(p.novelty_sha256 == novelty_sha256(p.text) for p in pack.prompts)


def test_story_slot_is_filled_only_with_the_persons_own_story_titles() -> None:
    material = CandidateMaterial(story_titles=("Moving billing to a new queue",))
    pack = build_round_pack(get_round("behavioural"), material, context(), researched=False)
    personalised = [p for p in pack.prompts if p.rationale_code == "YOUR_STORY"]
    assert personalised and all("Moving billing to a new queue" in p.text for p in personalised)
    assert all(p.derived_from["story_titles"] == ["Moving billing to a new queue"] for p in personalised)
    for prompt in pack.prompts:
        assert "{" not in prompt.text


def test_without_stories_the_plain_fallback_is_used() -> None:
    pack = build_round_pack(get_round("behavioural"), CandidateMaterial(), context(), researched=False)
    assert not any(p.rationale_code == "YOUR_STORY" for p in pack.prompts)
    assert all(p.derived_from["story_titles"] == [] for p in pack.prompts)


def test_a_story_title_that_names_the_company_is_not_used() -> None:
    material = CandidateMaterial(story_titles=("My Amazon interview prep",))
    pack = build_round_pack(get_round("behavioural"), material, context(), researched=False)
    assert all("Amazon" not in p.text for p in pack.prompts)


def test_not_researched_never_cites_published_guidance() -> None:
    for round_ in ROUNDS:
        pack = build_round_pack(round_, CandidateMaterial(), context(), researched=False)
        assert {p.rationale_code for p in pack.prompts} <= {"MIRROR_SUGGESTED", "YOUR_STORY"}
    pack = build_round_pack(get_round("system_design"), CandidateMaterial(), context(), researched=True)
    assert "PUBLISHED_GUIDANCE_AREA" in {p.rationale_code for p in pack.prompts}


def test_used_prompts_are_never_reused_and_the_pack_reports_short() -> None:
    round_ = get_round("system_design")
    used = frozenset(novelty_sha256(t.fallback) for t in round_.templates)
    pack = build_round_pack(round_, CandidateMaterial(), context(), researched=False, used_hashes=used)
    assert pack.state == "SHORT_PACK"
    assert len(pack.prompts) < PACK_MIN
    assert pack.minimum == PACK_MIN


def test_recently_served_prompts_are_rejected_by_the_guard() -> None:
    round_ = get_round("coding_reasoning")
    recent = [RecentPrompt(text=t.fallback, served_on=TODAY) for t in round_.templates]
    pack = build_round_pack(round_, CandidateMaterial(), context(recent=recent), researched=False)
    assert pack.state == "SHORT_PACK"


def test_pack_is_deterministic() -> None:
    material = CandidateMaterial(story_titles=("A", "Second story title"))
    one = build_round_pack(get_round("behavioural"), material, context(), researched=True)
    two = build_round_pack(get_round("behavioural"), material, context(), researched=True)
    assert one == two


def test_unknown_round_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_round("bar_raiser")
