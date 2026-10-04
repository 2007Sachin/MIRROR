"""Loop 2 web copy stays complete and lint-clean for every backend key it renders.

The web app never renders raw research-catalog text (statements/notes are not copy-lint
checked); it maps catalog claim/unknown/conflict keys, round keys, competency keys, reason codes
and prompt rationale codes to reviewed words in apps/web/src/lib/copy-targets.ts. A key without
words would silently disappear from the page, so this test fails instead.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

from app.copy_guard import find_banned
from app.research_catalog import load_catalog
from app.target_rounds import ROUNDS, Rationale

ROOT = Path(__file__).resolve().parents[2]
COPY = (ROOT / "apps/web/src/lib/copy-targets.ts").read_text(encoding="utf-8")
PRIORITY = (ROOT / "apps/api/app/target_priority.py").read_text(encoding="utf-8")


def _has_key(key: str) -> bool:
    return f'"{key}":' in COPY or re.search(rf"(?m)^\s+{re.escape(key)}:", COPY) is not None


def test_every_visible_claim_unknown_and_conflict_has_reviewed_words() -> None:
    catalog = load_catalog().document
    keys = [c.id for c in catalog.claims if c.candidate_visible]
    keys += [u.key for u in catalog.unknowns] + [c.key for c in catalog.conflict_sets]
    missing = [key for key in keys if not _has_key(key)]
    assert not missing, f"add words for these catalog keys to copy-targets.ts: {missing}"


def test_hidden_claims_have_no_words() -> None:
    catalog = load_catalog().document
    hidden = [c.id for c in catalog.claims if not c.candidate_visible]
    assert hidden and not [key for key in hidden if _has_key(key)]


def test_rounds_competencies_reasons_and_rationales_have_words() -> None:
    keys = {r.key for r in ROUNDS} | {k for r in ROUNDS for k in r.competency_keys}
    keys |= set(re.findall(r'codes\.append\("([A-Z_]+)"\)', PRIORITY))
    keys |= set(re.findall(r': "([A-Z_]+)"', PRIORITY.split("_COVERAGE_CODE = ", 1)[1].split("\n", 1)[0]))
    keys |= set(typing.get_args(Rationale))
    assert len(keys) > 15
    missing = sorted(key for key in keys if not _has_key(key))
    assert not missing, f"add words for these keys to copy-targets.ts: {missing}"


def test_target_copy_strings_pass_the_banned_word_list() -> None:
    strings = re.findall(r'"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`', COPY)
    texts = [a or b for a, b in strings if (a or b) and " " in (a or b)]
    assert len(texts) > 40
    offending = [text for text in texts if find_banned(text)]
    assert not offending, offending
