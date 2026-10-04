"""B12: deterministic contradiction grounding and candidate-facing probe safety.

Two separate questions, both answered by code rather than by model wording:

1. Is a model-asserted CONTRADICTION grounded in candidate-authored statements?
   A denial or negation alone is not a contradiction. A contradiction exists only when
   a negation in one candidate-authored statement is *about the same content* that
   another statement (a resume claim, or an earlier spoken turn) affirms.
2. Is a piece of model-written text safe to hand to the interviewer/candidate?
   Hostile or dishonesty-implying assertions never are. Plain assertions that two
   statements disagree are allowed only when (1) established the discrepancy.

Firm, grounded questions ("Earlier you described X; help me reconcile that with Y",
"What evidence supports that result?") are deliberately untouched.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .copy_guard import find_banned

# ------------------------------------------------------------------ grounding
# Negation is a closed grammatical class (function words), not a phrase list.
_NEGATION_CUES = frozenset({
    "never", "not", "no", "none", "nobody", "nothing", "neither", "nor", "without", "cannot",
    "didnt", "dont", "doesnt", "wasnt", "werent", "havent", "hasnt", "hadnt", "isnt", "arent",
    "wont", "wouldnt", "couldnt", "shouldnt", "cant",
})
_NEGATION_PHRASES = ("instead of", "rather than")
# Explicit self-correction only. A bare "actually"/"sorry" inside a sentence ("I actually never led it")
# is a flat reversal, not a correction, so only a sentence-initial "Actually," counts.
_SELF_CORRECTION = re.compile(
    r"(?:\b(?:to clarify|let me clarify|correction|let me rephrase|what i meant|i meant|to be (?:more )?precise|"
    r"let me correct|i misspoke)\b|(?:^|[.!?]\s*)actually,)", re.IGNORECASE)
_HOMOGLYPHS = str.maketrans({"\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c", "\u0445": "x",
                             "\u0443": "y", "\u0456": "i", "\u0455": "s", "\u04cf": "l"})


def canonical(text: str) -> str:
    """Defeat trivial obfuscation before any pattern runs: NFKC, no invisible/format/control
    characters, ASCII apostrophes, common Cyrillic look-alikes, single-spaced."""
    text = unicodedata.normalize("NFKC", text or "").translate(_HOMOGLYPHS)
    for fancy, plain in (("\u2019", "'"), ("\u2018", "'"), ("\u02bc", "'"), ("\u201c", '"'), ("\u201d", '"')):
        text = text.replace(fancy, plain)
    text = "".join(" " if ch.isspace() else ch for ch in text if unicodedata.category(ch) not in {"Cf", "Cc"} or ch.isspace())
    return " ".join(text.split())
_STOP = frozenset("""
a an the and or but if so than then that this these those it its i me my mine we us our you your he she they them their
is am are was were be been being do does did done doing have has had having will would can could should may might must
of to in on at by for from with as into over about up out off only just yet still even also very really any anything
much many some part thing things how what when where why who whom which there here before after ever again
used use using work worked working involved responsible say said know knew
""".split())
_CLAUSE_SPLIT = re.compile(r"[,;.!?:()\u2014]|\bbut\b|\bhowever\b|\balthough\b", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+")
_SCOPE_WORDS = 10


def _norm(text: str) -> str:
    return canonical(text).lower().replace("'", "")


_IRREGULAR = {"ran": "run", "wrote": "write", "written": "write", "made": "make", "took": "take",
              "taken": "take", "built": "build", "chose": "choose", "chosen": "choose", "owned": "own", "ownership": "own"}


def _content(tokens: Iterable[str]) -> set[str]:
    return {_IRREGULAR.get(t, t) for t in tokens if t not in _STOP and len(t) > 2}


def _same_term(a: str, b: str) -> bool:
    if a == b:
        return True
    return len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]


def _overlap(left: set[str], right: set[str]) -> bool:
    return any(_same_term(a, b) for a in left for b in right)


def negated_scopes(text: str) -> list[set[str]]:
    """Content words inside the scope of each negation in `text` (clause-bounded)."""
    scopes: list[set[str]] = []
    for clause in _CLAUSE_SPLIT.split(_norm(text)):
        tokens = _WORD.findall(clause)
        for i, token in enumerate(tokens):
            if token in _NEGATION_CUES:
                scopes.append(_content(tokens[i + 1:i + 1 + _SCOPE_WORDS]))
                break
        else:
            for phrase in _NEGATION_PHRASES:
                if phrase in clause:
                    tail = _WORD.findall(clause.split(phrase, 1)[1])
                    scopes.append(_content(tail[:_SCOPE_WORDS]))
                    break
    return [s for s in scopes if s]


def negation_conflict(negating_text: str, other_text: str) -> bool:
    """True if a negation in `negating_text` is about content that `other_text` is about."""
    other = _content(_WORD.findall(_norm(other_text)))
    return any(_overlap(scope, other) for scope in negated_scopes(negating_text))


def statements_conflict(current: str, statement: str, *, statement_is_spoken_turn: bool) -> bool:
    """Do two candidate-authored statements (current answer vs resume claim / earlier turn) disagree?

    Compatible statements, plain clarifications and self-corrections of an earlier spoken turn are
    not contradictions. A bare denial that does not touch the other statement's content is not either.
    """
    if statement_is_spoken_turn and _SELF_CORRECTION.search(current):
        return False
    return negation_conflict(current, statement) or negation_conflict(statement, current)


# ------------------------------------------------------------------ candidate-facing text
# Class A: hostile / dishonesty-implying wording. Never candidate-facing.
_HOSTILE = re.compile(
    r"\b(?:lying|lied|liar|dishonest\w*|untruthful\w*|fabricat\w+|misrepresent\w*|exaggerat\w+|mislead\w*|"
    r"deceiv\w+|deceptive|false claims?|made (?:it|that|this|things|them) up|making (?:it|that|this|things|them) up|"
    r"(?:obviously|clearly|plainly|evidently) (?:false|untrue|wrong|a lie|lying|didn'?t|did not|never|have(?:n'?t| not)|can'?t|cannot|don'?t|do not)|"
    r"you(?:'re| are) (?:clearly|obviously) \w+|"
    r"you(?: have)? contradicted yourself|you(?:'re| are) contradicting yourself|caught you|"
    r"(?:don'?t|do not) believe you|not (?:being )?(?:honest|truthful)|be honest with me|"
    r"that(?:'s| is) (?:a )?(?:lie|bs|nonsense|made up)|(?:not|n'?t) telling (?:me )?the truth|come clean|playing games|"
    r"(?:took|taking|take|claiming) (?:the )?credit|inflat\w+ (?:your|the) (?:role|impact|experience|numbers|resume)|embellish\w*|bluff\w*|"
    r"(?:don'?t|do not) buy (?:it|that)|too good to be true|did you (?:lie|fake|invent|make)|inventing (?:details|things)|"
    r"stop (?:dodging|stalling|lying|fibbing)|made up|"
    r"(?:don'?t|do not|never|stop) (?:lie|lying|fib|fibbing)(?: to me)?|(?:was|is|a|that|this|it|another|just) (?:a |an )?(?:lie|fib)|"
    r"lie to me|fraud\w*|fibb\w+|phony|bogus|fishy|"
    r"(?:sounds?|looks?|seems?) (?:fake|made up|false|fishy|invented|fabricated)|that(?:'s| is) (?:simply |just |totally )?(?:false|untrue|fake)|"
    r"admit (?:it|that|you|this)|just admit)\b",
    re.IGNORECASE)
# Class B: asserting that statements disagree. Allowed only when the discrepancy is grounded.
_DISCREPANCY = re.compile(
    r"\b(?:(?:does|do|did)(?:n'?t| not) (?:match|line up|add up|agree)|conflicts? with|contradict\w*|inconsisten\w+|"
    r"which (?:one )?is (?:true|correct|right)|which is it|that(?:'s| is) not what (?:you (?:said|wrote)|(?:your|the) resume says)|"
    r"differs? from|clash\w* with|now you say|changed your story|your story (?:keeps|has|is|changed|changes|doesn'?t)|"
    r"(?:can'?t|cannot|can not) both be true|both be true|story keeps changing|(?:doesn'?t|does not|don'?t|do not) line up|"
    r"you (?:said|claimed|stated|told me) .{0,300}\bbut\b)\b",
    re.IGNORECASE)


def is_hostile(text: str) -> bool:
    return bool(_HOSTILE.search(canonical(text)))


def asserts_discrepancy(text: str) -> bool:
    return bool(_DISCREPANCY.search(canonical(text)))


def _snippet(text: str | None, limit: int = 110) -> str:
    cleaned = canonical(text or "")
    for ch in '\u201c\u201d"`*<>':
        cleaned = cleaned.replace(ch, "")
    if find_banned(cleaned) or is_hostile(cleaned):  # never read banned copy or hostile text aloud to the candidate
        return ""
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].rstrip(",;:-") + "\u2026"


def neutral_probe(*, claim_text: str | None, grounded_discrepancy: bool) -> str:
    """Rigorous, evidence-seeking, non-accusatory replacement question."""
    snippet = _snippet(claim_text)
    if snippet and grounded_discrepancy:
        return f"Earlier you described \u201c{snippet}\u201d. Help me reconcile that with what you just said."
    if snippet:
        return f"Walk me through \u201c{snippet}\u201d: what part did you personally own, and what was the result?"
    return "Could you walk me through that part again with one specific example and what came of it?"


def neutral_reason(*, claim_text: str | None, grounded_discrepancy: bool) -> str:
    snippet = _snippet(claim_text, 140)
    if snippet and grounded_discrepancy:
        return f"The answer may not fit the earlier statement \u201c{snippet}\u201d and needs to be reconciled."
    if snippet:
        return f"The answer needs more specifics about \u201c{snippet}\u201d; no conflict has been established."
    return "The answer needs more specifics; no conflict has been established."


def safe_probe_text(text: str, *, claim_text: str | None, grounded_discrepancy: bool) -> str:
    """Return `text` unchanged when safe, otherwise a neutral rigorous alternative."""
    if is_hostile(text) or (asserts_discrepancy(text) and not grounded_discrepancy):
        return neutral_probe(claim_text=claim_text, grounded_discrepancy=grounded_discrepancy)
    return text


def safe_reason_text(text: str, *, claim_text: str | None, grounded_discrepancy: bool) -> str:
    if is_hostile(text) or (asserts_discrepancy(text) and not grounded_discrepancy):
        return neutral_reason(claim_text=claim_text, grounded_discrepancy=grounded_discrepancy)
    return text


def question_is_safe(text: str, *, discrepancy_grounded: bool) -> bool:
    """Final gate on the interviewer's own wording before it reaches the candidate."""
    return not is_hostile(text) and (discrepancy_grounded or not asserts_discrepancy(text))
