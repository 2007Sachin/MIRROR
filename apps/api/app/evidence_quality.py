"""Quality gate: turns a resume reading into experience items a person can review.

Pure and deterministic, no language model. Resume text is untrusted, so the gate
drops anything that is not experience (contact details, links, addresses, names,
headings, boilerplate) before it can be shown, and never invents facts: a title
only rephrases the subject ("Improved X" becomes "You improved X"); when unsure it
keeps the person's own wording.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable

from .resume_models import ResumeAgentOutput, ResumeClaim, ResumeClaimType, SkillCategory

KINDS = ("ACHIEVEMENT", "PROJECT", "RESPONSIBILITY", "SKILL")
_KIND_ORDER = {"ACHIEVEMENT": 0, "PROJECT": 0, "RESPONSIBILITY": 1, "SKILL": 2}
LABEL_PREFIX = "From your resume"

# ------------------------------------------------------------------ what is not experience

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|in|org|io|dev|me|co|ai|uk)\b(?:/\S*)?", re.IGNORECASE)
_PHONE_RUN = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
# Street lines are capitalised ("221B Baker Street", "12 MG Road"), so "5 accounts in the banking sector" is kept.
_STREET = re.compile(
    r"\b\d{1,5}[A-Za-z]?,?\s+(?:[A-Z][\w.'-]*\s+){1,4}"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Nagar|Marg|Colony|Sector|Block|Drive|Boulevard|Blvd|Cross)\b"
)
_POSTCODE = re.compile(r",\s*\d{6}\b|\b(?:pin ?code|zip ?code|postcode)\b", re.IGNORECASE)
# Personal fields only count as boilerplate when written as a label ("Gender:"), so a
# statement like "Led a gender diversity hiring drive" is kept.
_BOILERPLATE = re.compile(
    r"\b(?:references?\s+(?:are\s+)?available|hereby\s+declare|curriculum\s+vitae|best\s+of\s+my\s+knowledge|"
    r"languages\s+known)\b"
    r"|\b(?:date\s+of\s+birth|d\.?o\.?b|marital\s+status|nationality|gender|father'?s\s+name|mother'?s\s+name|"
    r"hobbies|passport(?:\s+(?:no|number))?|location|e-?mail|phone|mobile|contact|address)\s*:"
    r"|^page\s+\d+(?:\s+of\s+\d+)?$|\[\s*page",
    re.IGNORECASE,
)
_HEADINGS = frozenset(
    """experience|work experience|professional experience|employment history|employment|education|
    academic background|qualifications|skills|technical skills|key skills|core skills|core competencies|
    competencies|projects|academic projects|key projects|achievements|key achievements|accomplishments|
    awards|honours|honors|certifications|certificates|summary|professional summary|profile|
    professional profile|objective|career objective|about me|contact|contact details|personal details|
    personal information|references|languages|interests|hobbies|declaration|resume|cv|curriculum vitae|
    responsibilities|key responsibilities|internships|internship|extracurricular activities|activities|
    volunteering|publications|tools|technologies""".replace("\n", " ").split("|")
)
# Words that keep a short title-case line from looking like a name or a place.
_NOT_A_NAME = frozenset(
    "award awards prize rank winner certified certificate certification scholarship medal hackathon "
    "datathon champion finalist honour honor dean's list".split()
)

ACTION_VERBS = frozenset(
    """accelerated achieved analysed analyzed automated boosted built coached consolidated coordinated
    conducted created cut delivered designed developed drove enabled established executed expanded
    forecasted generated grew handled identified implemented improved increased introduced launched led
    maintained managed mentored migrated modelled modeled monitored negotiated optimised optimized
    organised organized owned partnered planned prepared presented produced raised rebuilt recommended
    redesigned reduced resolved restructured saved scaled secured shipped simplified spearheaded
    streamlined supported tracked trained won wrote""".split()
)
_QUANTIFIED = re.compile(
    r"\d|%|\b(?:percent|half|double|doubled|twice|triple|tripled|two|three|four|five|six|seven|eight|nine|"
    r"ten|dozen|hundred|thousand|lakh|crore|million|billion)\b",
    re.IGNORECASE,
)
_METRIC = re.compile(
    r"(?:[$₹£€]\s?)?\d[\d,.]*\s?(?:%|x\b|k\b|(?:per\s?cent|percent|lakh|crore|million|billion|thousand|"
    r"hours?|days?|weeks?|months?|minutes?|users|customers|clients|people|accounts|reports|stores|members)\b)?",
    re.IGNORECASE,
)
_YEAR = re.compile(r"(?:19|20)\d\d")
_BULLET = re.compile(r"^[\s•●▪◦*·\-–—>]+")


def clean(text: str | None) -> str:
    """One line, no bullet, no trailing full stop."""
    text = _BULLET.sub("", " ".join((text or "").split()))
    return text.rstrip(" .;,")


def _has_phone(text: str) -> bool:
    return any(10 <= sum(ch.isdigit() for ch in run) <= 15 for run in _PHONE_RUN.findall(text))


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", text.casefold()).split())


def _name_or_place_only(text: str) -> bool:
    """A short line of capitalised words with no verb, number or award word: a name, a place, a label."""
    tokens = [token.strip(",.;:()|") for token in text.split()]
    tokens = [token for token in tokens if token]
    if not tokens or len(tokens) > 5:
        return False
    if any(token.casefold() in ACTION_VERBS or token.casefold() in _NOT_A_NAME for token in tokens):
        return False
    return all(token[0].isupper() and token.replace("-", "").replace("'", "").isalpha() for token in tokens)


def is_noise(text: str | None, *, named: bool = False) -> bool:
    """True for anything that is not experience worth showing or talking through.

    ``named`` is for a skill or tool name ("SQL", "Power BI"), which is legitimately short
    and capitalised, so only the contact, link, heading and boilerplate checks apply to it.
    """
    line = clean(text)
    if len(line) < 2:
        return True
    if (_EMAIL.search(line) or _URL.search(line) or _has_phone(line) or _STREET.search(line)
            or _POSTCODE.search(line) or _BOILERPLATE.search(line)):
        return True
    if _norm(line.rstrip(":")) in _HEADINGS or (line.endswith(":") and len(line.split()) <= 4):
        return True
    if named:
        return False
    if len(line.split()) <= 4 and line.upper() == line and any(ch.isalpha() for ch in line):
        return True  # an all-capitals heading
    return _name_or_place_only(line)


# ------------------------------------------------------------------ wording


def first_person(text: str) -> str:
    """Rephrase only the subject. Anything that does not start with an action verb stays as written."""
    line = clean(text)
    if not line:
        return line
    first, _, rest = line.partition(" ")
    lowered = first.casefold().rstrip(",")
    if lowered == "i" and rest:
        return f"You {rest}"
    if lowered in ACTION_VERBS:
        return f"You {lowered}{' ' + rest if rest else ''}"
    if line.casefold().startswith("responsible for "):
        return f"You were responsible for {line[len('responsible for '):]}"
    return line


def starts_with_action(title: str) -> bool:
    words = clean(title).split()
    if words and words[0].casefold() == "you" and len(words) > 1:
        words = words[1:]
    return bool(words) and words[0].casefold() in ACTION_VERBS


def is_quantified(*texts: str | None) -> bool:
    return any(text and _QUANTIFIED.search(text) for text in texts)


def metric_in(text: str) -> str | None:
    """The first measured amount in the text ("40%", "₹2 crore", "3 hours"), never a bare year."""
    for match in _METRIC.finditer(text):
        found = match.group(0).strip(" ,.")
        if _YEAR.fullmatch(found) or not any(ch.isdigit() for ch in found):
            continue
        return found
    return None


def rank_key(kind: str, title: str, metric: str | None = None) -> tuple[int, int, int]:
    """Quantified outcomes first, then action-verb statements, then by kind."""
    return (
        0 if (metric or is_quantified(title)) else 1,
        0 if starts_with_action(title) else 1,
        _KIND_ORDER.get(kind, 3),
    )


# ------------------------------------------------------------------ drafts


@dataclass
class EvidenceDraft:
    source_key: str
    kind: str
    title: str
    detail: str | None = None
    outcome: str | None = None
    metric: str | None = None
    tools: list[str] = field(default_factory=list)
    source_label: str | None = None


def _clip(text: str | None, limit: int) -> str | None:
    text = clean(text) if text else None
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _tools_in(text: str, names: Iterable[str]) -> list[str]:
    found: list[str] = []
    for name in names:
        if len(name) >= 2 and re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text, re.IGNORECASE):
            if name.casefold() not in {item.casefold() for item in found}:
                found.append(name)
    return found


def _claim_metric(claim: ResumeClaim) -> str | None:
    if claim.metric_value is None:
        return None
    value = f"{claim.metric_value:g}"
    unit = (claim.metric_unit or "").strip()
    if not unit:
        return value
    return f"{value}{unit}" if unit in ("%", "x") else f"{value} {unit}"


class _Builder:
    def __init__(self, output: ResumeAgentOutput, claims: Iterable[ResumeClaim]) -> None:
        self.claims = list(claims)
        named = [*(skill.name for skill in output.skills), *(tool.name for tool in output.tools)]
        named += [tech for project in output.projects for tech in project.technologies]
        self.tool_names = [clean(name) for name in named if not is_noise(name, named=True)]
        self.drafts: list[EvidenceDraft] = []
        self.seen: list[str] = []

    def _duplicate(self, key: str) -> bool:
        for seen in self.seen:
            if key == seen:
                return True
            if len(key.split()) >= 4 and len(seen.split()) >= 4 and (key in seen or seen in key):
                return True
        return False

    def _matching_claim(self, key: str) -> ResumeClaim | None:
        for claim in self.claims:
            other = _norm(claim.claim_text)
            if other == key or (len(key.split()) >= 4 and (other in key or key in other)):
                return claim
        return None

    def add(
        self, kind: str, text: str | None, *, label: str, detail: str | None = None, outcome: str | None = None,
        extra_tools: Iterable[str] = (), statement: bool = True,
    ) -> None:
        line = clean(text)
        if not line or is_noise(line, named=not statement):
            return
        if detail and is_noise(detail):
            detail = None
        key = _norm(line)
        if not key or self._duplicate(key):
            return
        self.seen.append(key)
        claim = self._matching_claim(key) if statement else None
        searchable = " ".join(filter(None, (line, detail, outcome)))
        tools = _tools_in(searchable, self.tool_names) if statement else []
        for name in (*extra_tools, *((claim.tool,) if claim and claim.tool else ())):
            if name and not is_noise(name, named=True) and name.casefold() not in {item.casefold() for item in tools}:
                tools.append(clean(name))
        metric = (_claim_metric(claim) if claim else None) or (metric_in(searchable) if statement else None)
        outcome = (claim.outcome if claim and claim.outcome and not is_noise(claim.outcome) else None) or outcome
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
        self.drafts.append(
            EvidenceDraft(
                source_key=f"{kind.lower()}:{digest}",
                kind=kind,
                title=_clip(first_person(line) if statement else line, 500) or line[:500],
                detail=_clip(detail, 3000),
                outcome=_clip(outcome, 2000),
                metric=_clip(metric, 200),
                tools=[name[:200] for name in tools[:30]],
                source_label=_clip(label, 300),
            )
        )


_CLAIM_KIND = {
    ResumeClaimType.OUTCOME: "ACHIEVEMENT",
    ResumeClaimType.SCALE: "ACHIEVEMENT",
    ResumeClaimType.PROJECT: "PROJECT",
    ResumeClaimType.RESPONSIBILITY: "RESPONSIBILITY",
    ResumeClaimType.OWNERSHIP: "RESPONSIBILITY",
    ResumeClaimType.EXPERIENCE: "RESPONSIBILITY",
}


def _label(*parts: str | None) -> str:
    kept = [clean(part) for part in parts if part and not is_noise(part, named=True)]
    return f"{LABEL_PREFIX} - {' '.join(kept)}" if kept else LABEL_PREFIX


def evidence_drafts(output: ResumeAgentOutput, claims: Iterable[ResumeClaim] = ()) -> list[EvidenceDraft]:
    """Reviewable experience from one resume reading, best first. Same input, same output."""
    build = _Builder(output, claims)
    for achievement in output.achievements:
        title, description = clean(achievement.title), clean(achievement.description)
        # A short label title ("Best Employee Award") keeps its description as detail.
        detail = description if _norm(description) not in _norm(title) else None
        outcome = title if starts_with_action(title) or is_quantified(title) else None
        build.add("ACHIEVEMENT", title, label=LABEL_PREFIX, detail=detail, outcome=outcome)
    for job in output.work_experience:
        where = f"{clean(job.role)} at {clean(job.organization)}" if not is_noise(job.organization, named=True) else job.role
        label = _label(where)
        for outcome in job.claimed_outcomes:
            build.add("ACHIEVEMENT", outcome, label=label, outcome=outcome)
        for duty in job.claimed_responsibilities:
            build.add("RESPONSIBILITY", duty, label=label)
        if not job.claimed_outcomes and not job.claimed_responsibilities and job.description:
            build.add("RESPONSIBILITY", job.description, label=label)
    for project in output.projects:
        label = _label(f"{clean(project.project_name)} project")
        description = clean(project.description)
        title = description if starts_with_action(description) else project.project_name
        detail = description if title != description else None
        outcomes = [clean(item) for item in project.claimed_outcomes if clean(item)]
        build.add("PROJECT", title, label=label, detail=detail, outcome=outcomes[0] if outcomes else None,
                  extra_tools=project.technologies)
        for outcome in outcomes[1:]:
            build.add("ACHIEVEMENT", outcome, label=label, outcome=outcome, extra_tools=project.technologies)
    for claim in build.claims:
        kind = _CLAIM_KIND.get(claim.claim_type)
        if kind is None:
            continue
        label = _label(f"{clean(claim.project_name)} project") if claim.project_name else LABEL_PREFIX
        build.add(kind, claim.claim_text, label=label,
                  outcome=claim.claim_text if kind == "ACHIEVEMENT" else None)
    tool_names = {clean(tool.name).casefold() for tool in output.tools}
    for skill in [*output.skills, *output.tools]:
        is_tool = clean(skill.name).casefold() in tool_names or getattr(skill, "category", None) == SkillCategory.TOOL
        build.add("SKILL", skill.name, label=f"{LABEL_PREFIX} - Skills", extra_tools=(skill.name,) if is_tool else (),
                  statement=False)
    order = {id(draft): index for index, draft in enumerate(build.drafts)}
    return sorted(build.drafts, key=lambda draft: (*rank_key(draft.kind, draft.title, draft.metric), order[id(draft)]))
