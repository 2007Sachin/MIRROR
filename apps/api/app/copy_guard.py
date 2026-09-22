"""Banned-word guard for text people read or hear (see docs/copy-guide.md).

One list is shared by the copy lint script and by report generation, so the
words we ban in the interface are the same ones we keep out of generated
reflections. Matching is by whole word, case-insensitive, with inflections.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

logger = logging.getLogger("mirror.copy_guard")

BANNED_PATTERNS: tuple[str, ...] = (
    r"evidences?",
    r"diagnostics?",
    r"assess\w*",
    r"skeptics?",
    r"scor(?:e|es|ed|ing)",
    r"weakness(?:es)?",
    r"gaps?",
    r"deficienc(?:y|ies)",
    r"deficient",
    r"fail(?:s|ed|ing|ure|ures)?",
    r"incorrect(?:ly)?",
    r"wrong(?:ly)?",
    r"red[ -]flags?",
    r"critical(?:ly)?",
    r"candidates?",
    r"verdicts?",
    r"evaluat(?:e|es|ed|ing|ion|ions|or|ors)",
    r"analy(?:sis|ses|se|sed|sing|ze|zed|zing)",
    r"audit(?:s|ed|ing)?",
    r"test(?:s|ed|ing)?",
    r"verif(?:y|ies|ied|ying|ication)",
    r"proofs?",
    r"performances?",
    r"scrutiny",
    r"substantiat(?:e|es|ed|ing)",
    r"flag(?:s|ged|ging)?",
)

# Warn only. Prefer the glossary alternatives in docs/copy-guide.md.
SOFT_AVOID: dict[str, str] = {
    r"claims?": "what you shared / moments worth talking through",
    r"benchmark(?:s|ing)?": "your target role / getting to know the role",
    r"thesis": "your conversation plan",
    r"inquiry": "areas to explore",
    r"prob(?:e|es|ed|ing)": "ask more about / explore",
    r"challenged": "asked more",
    r"unproven": "still to explore",
    r"bottlenecks?": "growth area",
}

BANNED_RE = re.compile(r"(?<![\w-])(?:" + "|".join(BANNED_PATTERNS) + r")(?![\w-])", re.IGNORECASE)
SOFT_RE = {re.compile(r"(?<![\w-])(?:" + pattern + r")(?![\w-])", re.IGNORECASE): hint for pattern, hint in SOFT_AVOID.items()}


def find_banned(text: str) -> list[str]:
    """Return every banned word found in ``text`` (empty when the text is clean)."""
    return [match.group(0) for match in BANNED_RE.finditer(text or "")]


def find_soft(text: str) -> list[tuple[str, str]]:
    """Return ``(word, suggestion)`` pairs for soft-avoid words."""
    found: list[tuple[str, str]] = []
    for regex, hint in SOFT_RE.items():
        found.extend((match.group(0), hint) for match in regex.finditer(text or ""))
    return found


def clean_or_fallback(text: str | None, fallback: str, *, field: str) -> str:
    """Return ``text`` when it is clean, otherwise the safe ``fallback`` (and log it)."""
    if not text:
        return fallback
    hits = find_banned(text)
    if not hits:
        return text
    logger.warning("copy_guard_fallback field=%s banned=%s", field, sorted({hit.lower() for hit in hits}))
    return fallback


def all_clean(values: Iterable[str]) -> bool:
    return not any(find_banned(value) for value in values)
