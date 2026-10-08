"""Originality guard for Mirror-written practice prompts (pure, no I/O).

Checks, in order, with the first failure returned as a stable reason code:
SHAPE -> BANNED_TERM (copy_guard, shared with lint:copy) -> COMPANY_ATTRIBUTION ->
SOURCE_OVERLAP (word n-grams against stored research excerpts) -> REPEAT (the person's own
recent prompts). Deliberately conservative: a false reject costs a fallback template, a false
accept costs trust. Rejected text is never logged by this module.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.copy_guard import find_banned
from app.research_catalog import RepoResearchCatalog
from app.target_taxonomy import load_taxonomy

ORIGINALITY_RULES_VERSION = "originality-1"

MIN_CHARS, MAX_CHARS = 20, 400
OVERLAP_N = 5  # any shared 5-word run with a research excerpt is a copy
SHORT_EXCERPT_MIN = 3  # excerpts shorter than OVERLAP_N are matched whole (if >= 3 words)
REPEAT_WINDOW_DAYS = 30
REPEAT_JACCARD = 0.6  # word 3-gram similarity to a recent prompt

# A company's own process vocabulary (regex fragments) is taxonomy data
# (``companies.<key>.process_terms`` in research_content/taxonomy_v1.json), looked up by the
# exact company names in the guard context. No company is named in this module.
ATTRIBUTION_PHRASES: tuple[str, ...] = (
    r"(?:real|actual|leaked|reported) interview questions?",
    r"question banks?",
    r"frequently asked",
    r"asked (?:at|by|in) (?:the )?(?:company|interviews?)",
)
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)

Reason = Literal["SHAPE", "BANNED_TERM", "COMPANY_ATTRIBUTION", "SOURCE_OVERLAP", "REPEAT"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecentPrompt(_Frozen):
    text: str
    served_on: date


class GuardContext(_Frozen):
    source_excerpts: tuple[str, ...]
    company_names: tuple[str, ...]
    recent_prompts: tuple[RecentPrompt, ...]
    today: date


class GuardResult(_Frozen):
    ok: bool
    reason: Reason | None = None


def normalise(text: str) -> list[str]:
    return re.sub(r"[^0-9a-z]+", " ", (text or "").casefold()).split()


def novelty_sha256(text: str) -> str:
    return hashlib.sha256(" ".join(normalise(text)).encode("utf-8")).hexdigest()


def _grams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _contains(tokens: list[str], run: list[str]) -> bool:
    width = len(run)
    return any(tokens[i : i + width] == run for i in range(len(tokens) - width + 1))


def _attribution_re(company_names: tuple[str, ...]) -> re.Pattern[str]:
    terms: list[str] = list(ATTRIBUTION_PHRASES)
    taxonomy = load_taxonomy()  # TaxonomyError propagates: no guard, no prompts
    for name in company_names:
        terms.append(re.escape(name))
        terms.extend(taxonomy.process_terms(taxonomy.company_key(name)))
    return re.compile(r"(?<![\w-])(?:" + "|".join(terms) + r")(?![\w-])", re.IGNORECASE)


def _overlaps(tokens: list[str], excerpts: tuple[str, ...]) -> bool:
    prompt_grams = _grams(tokens, OVERLAP_N)
    for excerpt in excerpts:
        words = normalise(excerpt)
        if len(words) >= OVERLAP_N:
            if prompt_grams & _grams(words, OVERLAP_N):
                return True
        elif len(words) >= SHORT_EXCERPT_MIN and _contains(tokens, words):
            return True
    return False


def _repeats(text: str, tokens: list[str], context: GuardContext) -> bool:
    digest = novelty_sha256(text)
    mine = _grams(tokens, 3)
    for recent in context.recent_prompts:
        age = (context.today - recent.served_on).days
        if age < 0 or age > REPEAT_WINDOW_DAYS:
            continue
        if novelty_sha256(recent.text) == digest:
            return True
        theirs = _grams(normalise(recent.text), 3)
        union = mine | theirs
        if union and len(mine & theirs) / len(union) >= REPEAT_JACCARD:
            return True
    return False


def check_prompt(text: str, context: GuardContext) -> GuardResult:
    stripped = (text or "").strip()
    if not (MIN_CHARS <= len(stripped) <= MAX_CHARS) or _URL.search(stripped):
        return GuardResult(ok=False, reason="SHAPE")
    if find_banned(stripped):
        return GuardResult(ok=False, reason="BANNED_TERM")
    if _attribution_re(context.company_names).search(stripped):
        return GuardResult(ok=False, reason="COMPANY_ATTRIBUTION")
    tokens = normalise(stripped)
    if _overlaps(tokens, context.source_excerpts):
        return GuardResult(ok=False, reason="SOURCE_OVERLAP")
    if _repeats(stripped, tokens, context):
        return GuardResult(ok=False, reason="REPEAT")
    return GuardResult(ok=True)


def excerpts_from_catalog(catalog: RepoResearchCatalog) -> tuple[str, ...]:
    """Every stored research excerpt (all claims, visible or not) for the overlap check."""
    seen: dict[str, None] = {}
    for claim in catalog.claims:
        for item in claim.evidence:
            seen.setdefault(item.excerpt, None)
    return tuple(seen)
