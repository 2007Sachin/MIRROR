"""Deterministic harness for the Mirror AI behavioural evaluation suite.

Everything here is offline: a scripted fake provider stands in for the model,
and production code (AgentRunner, SkepticWorker, SkepticContextBuilder,
SkepticResultProcessor, FlagEligibilityService, ...) runs unmodified on top of
in-memory repositories. No network, no secrets, no files outside fixtures/.
"""
from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.agents import AgentRegistry, AgentRunner, PromptLoader
from app.agents.definitions import ProviderRequest, ProviderResponse
from app.agents.skeptic import create_skeptic_agent
from app.claims_models import ClaimStatus, ClaimType
from app.flag_activation import EligibleFlagCandidate, FlagEligibilityService
from app.interviewer_models import InterviewerTurnType, TurnSpeaker
from app.schemas import Phase
from app.skeptic_context import SkepticContextBuilder
from app.skeptic_models import (
    SkepticClaim,
    SkepticJob,
    SkepticRetrievalData,
    SkepticTurn,
)
from app.skeptic_processor import SkepticResultProcessor
from app.skeptic_worker import SkepticWorker

FIXTURE_DIR = Path(__file__).parent / "fixtures"
VARIANTS = ("baseline", "short-answer", "transcription-noise", "recovery")
USER_ID = UUID("ae000000-0000-4000-8000-000000000001")
MIN_CONFIDENCE = 0.8


# ----------------------------------------------------------------- fixtures
def load_scenarios() -> dict[str, dict]:
    raw = json.loads((FIXTURE_DIR / "scenarios.json").read_text(encoding="utf-8"))
    return {item["id"]: item for item in raw["candidates"]}


def uid(*parts: str) -> UUID:
    return uuid5(NAMESPACE_URL, "mirror-ai-eval:" + ":".join(parts))


def apply_variant(text: str, variant: str) -> str:
    """Deterministic text perturbation; never adds or removes first-person claims."""
    if variant == "baseline":
        return text
    if variant == "short-answer":
        return re.split(r"(?<=[.!?])\s+", text.strip())[0]
    if variant == "transcription-noise":
        return "uh " + re.sub(r"[,.]", "", text).lower()
    if variant == "recovery":
        return "Sorry, let me restate that. " + text
    raise ValueError(f"unknown variant {variant}")


@dataclass(frozen=True)
class EvalTurn:
    id: UUID
    index: int
    speaker: str
    text: str
    key: str
    category: str | None
    script: dict | None


@dataclass(frozen=True)
class EvalCandidate:
    cid: str
    variant: str
    session_id: UUID
    marker: str
    claims: dict[str, dict]  # key -> {id, text, type}
    turns: list[EvalTurn]    # interleaved interviewer/candidate

    @property
    def candidate_turns(self) -> list[EvalTurn]:
        return [t for t in self.turns if t.speaker == "CANDIDATE"]

    def transcript_text(self) -> dict[UUID, str]:
        return {t.id: t.text for t in self.turns}


def build_candidate(cid: str, variant: str = "baseline", scenarios: dict | None = None) -> EvalCandidate:
    raw = (scenarios or load_scenarios())[cid]
    claims = {
        c["key"]: {"id": uid(cid, variant, "claim", c["key"]), "text": c["text"], "type": c["type"]}
        for c in raw["claims"]
    }
    turns: list[EvalTurn] = []
    for position, item in enumerate(raw["turns"]):
        turns.append(EvalTurn(uid(cid, variant, "q", item["key"]), 2 * position, "INTERVIEWER",
                              item["q"], item["key"] + "_q", None, None))
        turns.append(EvalTurn(uid(cid, variant, "a", item["key"]), 2 * position + 1, "CANDIDATE",
                              apply_variant(item["text"], variant), item["key"], item["category"],
                              item.get("skeptic")))
    return EvalCandidate(cid, variant, uid(cid, variant, "session"), raw["marker"], claims, turns)


# ----------------------------------------------------------- in-memory repo
class MemoryEvalRepository:
    """Implements SkepticRepository + FlagActivationRepository; shared across candidates."""

    def __init__(self) -> None:
        self.retrieval: dict[UUID, SkepticRetrievalData] = {}
        self.jobs: deque[SkepticJob] = deque()
        self.observations: list[dict] = []
        self.proposals: list[dict] = []
        self.flags: list[dict] = []
        self.failures: list[tuple[str, bool]] = []
        self.completed: list[UUID] = []
        self.analyses: list[tuple] = []
        self._keys: set[str] = set()

    # ---- SkepticRepository
    async def publish_candidate_turn_completed(self, session_id, user_id, turn_id):
        return None

    async def claim_job(self, worker_id, max_attempts):
        return self.jobs.popleft() if self.jobs else None

    async def load_retrieval_data(self, turn_id):
        return self.retrieval[turn_id]

    async def spoken_claim_exists(self, user_id, source_turn_id, normalized_text):
        return False

    async def create_observation(self, session_id, user_id, execution_id, observation, dedupe_key):
        if dedupe_key in self._keys:
            return False
        self._keys.add(dedupe_key)
        self.observations.append({"session_id": session_id, "observation": observation})
        return True

    async def create_claim_update_proposal(self, session_id, user_id, source_turn_id, execution_id,
                                           proposal, dedupe_key):
        if dedupe_key in self._keys:
            return False
        self._keys.add(dedupe_key)
        self.proposals.append({"session_id": session_id, "proposal": proposal})
        return True

    async def create_flag(self, session_id, user_id, turn_index, execution_id, proposal, dedupe_key,
                          shadow_mode):
        if dedupe_key in self._keys:
            return False
        self._keys.add(dedupe_key)
        self.flags.append({
            "id": uuid4(), "session_id": session_id, "turn_index": turn_index, "proposal": proposal,
            "shadow_mode": shadow_mode, "consumed": False,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=len(self.flags)),
        })
        return True

    async def record_analysis(self, job, execution, analysis, summary, shadow_mode):
        self.analyses.append((job, execution, analysis, summary, shadow_mode))

    async def complete_job(self, job_id):
        self.completed.append(job_id)

    async def fail_job(self, job, failure_type, *, retry, retry_base_seconds):
        self.failures.append((failure_type, retry))

    # ---- FlagActivationRepository (session-scoped; the service re-filters)
    def _eligible(self, row: dict) -> EligibleFlagCandidate:
        p = row["proposal"]
        return EligibleFlagCandidate(
            id=row["id"], claim_id=p.claim_id, flag_type=p.flag_type, severity=p.severity,
            confidence=p.confidence, reason=p.reason, suggested_probe=p.suggested_probe,
            detected_at_turn=row["turn_index"], created_at=row["created_at"],
            claim_summary=None, claim_verification_priority="HIGH", consumed=row["consumed"],
            safe_to_surface=p.safe_to_surface, shadow_mode=row["shadow_mode"],
        )

    async def list_eligible(self, session_id, user_id, current_turn, min_confidence, allow_shadow):
        return [self._eligible(r) for r in self.flags if r["session_id"] == session_id]

    async def consume(self, flag_id, session_id, user_id, current_turn, interviewer_turn_id,
                      min_confidence, allow_shadow):
        for row in self.flags:
            if row["id"] == flag_id and row["session_id"] == session_id and not row["consumed"] \
                    and row["turn_index"] < current_turn:
                row["consumed"] = True
                return True
        return False

    def flags_for(self, session_id: UUID) -> list[dict]:
        return [r for r in self.flags if r["session_id"] == session_id]

    def observations_for(self, session_id: UUID) -> list[Any]:
        return [r["observation"] for r in self.observations if r["session_id"] == session_id]

    def proposals_for(self, session_id: UUID) -> list[Any]:
        return [r["proposal"] for r in self.proposals if r["session_id"] == session_id]


# --------------------------------------------------------- scripted providers
class NullLogger:
    def emit(self, fields: dict[str, Any]) -> None:  # noqa: D401 - no-op logger
        return None


def _claim_uuid(context: dict, claim_key_text: str | None) -> str | None:
    claims = context.get("related_resume_claims") or []
    return claims[0]["id"] if claims else None


class ScriptedSkepticProvider:
    """Fake model. Looks up the current candidate turn in the registered candidates.

    styles: reference (well-behaved script from fixtures), paranoid (flags every turn),
    accuser (asserts CONTRADICTION + CONTRADICTED on every turn), generic (reference
    flags but with boilerplate reason/probe), hallucinating (references unknown ids).
    """

    accuser_probe = "Could you walk me through that part once more?"

    def __init__(self, candidates: list[EvalCandidate], style: str = "reference") -> None:
        self.style = style
        self.requests: list[ProviderRequest] = []
        self._by_turn: dict[str, tuple[EvalCandidate, EvalTurn]] = {}
        for cand in candidates:
            for turn in cand.candidate_turns:
                self._by_turn[str(turn.id)] = (cand, turn)

    def register(self, cand: EvalCandidate) -> None:
        for turn in cand.candidate_turns:
            self._by_turn[str(turn.id)] = (cand, turn)

    async def complete(self, request: ProviderRequest, *, timeout_seconds: float) -> ProviderResponse:
        self.requests.append(request)
        context = json.loads(request.messages[1]["content"])
        turn_id = context["current_turn"]["id"]
        cand, turn = self._by_turn[turn_id]
        return ProviderResponse(content=self._analysis(context, cand, turn))

    def _analysis(self, context: dict, cand: EvalCandidate, turn: EvalTurn) -> dict:
        turn_id = str(turn.id)
        claim_id = _claim_uuid(context, None)
        base = {"new_claims": [], "claim_updates": [], "observations": [], "flag_proposals": []}

        def flag(kind, severity, conf, reason, probe, cid=claim_id, related=None):
            return {"flag_type": kind, "claim_id": cid, "severity": severity, "confidence": conf,
                    "reason": reason, "suggested_probe": probe, "safe_to_surface": True,
                    "source_turn_id": turn_id, "related_turn_ids": related or [turn_id]}

        def obs(kind, summary, conf, cid=claim_id):
            return {"observation_type": kind, "summary": summary, "confidence": conf,
                    "source_turn_id": turn_id, "related_claim_ids": [cid] if cid else [],
                    "related_turn_ids": [turn_id]}

        if self.style in ("reference", "generic"):
            script = turn.script or {"flags": [], "observations": []}
            for item in script["flags"]:
                cid = str(cand.claims[item["claim"]]["id"])
                reason, probe = item["reason"], item["probe"]
                if self.style == "generic":
                    reason, probe = "The answer could use more detail.", "Please elaborate."
                base["flag_proposals"].append(flag(item["flag_type"], item["severity"],
                                                   item["confidence"], reason, probe, cid))
            for item in script["observations"]:
                cid = str(cand.claims[item["claim"]]["id"])
                base["observations"].append(obs(item["observation_type"], item["summary"],
                                                item["confidence"], cid))
        elif self.style == "paranoid":
            base["flag_proposals"].append(flag(
                "VAGUENESS", "HIGH", 0.95,
                f"Answer {turn.key} lacks verifiable detail.", "Can you prove that with specifics?"))
        elif self.style == "accuser":
            base["flag_proposals"].append(flag(
                "CONTRADICTION", "HIGH", 0.95,
                "The answer conflicts with the stated resume claim.",
                self.accuser_probe))
            base["observations"].append(obs("CONTRADICTION", "The answer conflicts with the resume claim.", 0.9))
            if claim_id:
                base["claim_updates"].append({
                    "claim_id": claim_id, "proposed_status": "CONTRADICTED", "confidence": 0.9,
                    "reason": "The answer conflicts with the resume claim.", "related_turn_ids": [turn_id]})
        elif self.style == "hallucinating":
            ghost = str(uuid4())
            base["flag_proposals"].append(flag(
                "VAGUENESS", "HIGH", 0.95, "References a claim and turn that do not exist.",
                "Tell me more.", cid=ghost, related=[ghost]))
        else:  # pragma: no cover - guard against typos in tests
            raise ValueError(self.style)
        return base


class LeakyProvider(ScriptedSkepticProvider):
    """Negative-control double: remembers earlier requests and leaks them into later ones."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._memory: list[str] = []

    async def complete(self, request, *, timeout_seconds):
        leaked = request.model_copy(update={"messages": [
            *request.messages, {"role": "system", "content": " ".join(self._memory)}]})
        self._memory.append(request.messages[1]["content"])
        return await super().complete(leaked, timeout_seconds=timeout_seconds)


class RaisingProvider:
    def __init__(self, exc: Exception | None = None, *, sleep: float = 0.0) -> None:
        self.exc, self.sleep, self.requests = exc, sleep, []

    async def complete(self, request, *, timeout_seconds):
        import asyncio

        self.requests.append(request)
        if self.sleep:
            await asyncio.sleep(self.sleep)
        if self.exc:
            raise self.exc
        return ProviderResponse(content={})


class RawProvider:
    """Returns pre-built raw provider payloads in order (used for malformed output)."""

    def __init__(self, *payloads: Any) -> None:
        self.payloads = deque(payloads)
        self.requests: list[ProviderRequest] = []

    async def complete(self, request, *, timeout_seconds):
        self.requests.append(request)
        payload = self.payloads[0] if len(self.payloads) == 1 else self.payloads.popleft()
        return ProviderResponse(content=payload)


# ------------------------------------------------------------------ pipeline
def build_runner(provider: Any, *, timeout_seconds: float | None = None, max_retries: int | None = None,
                 model: str = "eval-fake-model") -> AgentRunner:
    from dataclasses import replace

    agent = create_skeptic_agent(model)
    changes = {}
    if timeout_seconds is not None:
        changes["timeout_seconds"] = timeout_seconds
    if max_retries is not None:
        changes["max_retries"] = max_retries
    if changes:
        agent = replace(agent, **changes)
    registry = AgentRegistry()
    registry.register(agent)
    return AgentRunner(registry, provider, PromptLoader(), execution_logger=NullLogger())


@dataclass
class SelectionRecord:
    candidate: str
    turn_key: str
    mode: str
    evaluated_at: int
    selected_flag_id: UUID | None
    selected_detected_at: int | None
    selected_flag_type: str | None
    turn_type: str | None
    reason: str | None
    probe: str | None
    claim_id: UUID | None
    live_after: str  # "immediate" (turn N) or "next" (turn N+1)


@dataclass
class PipelineRun:
    candidate: EvalCandidate
    mode: str
    repo: MemoryEvalRepository
    provider: Any
    worker_results: list = field(default_factory=list)
    selections: list[SelectionRecord] = field(default_factory=list)

    @property
    def flags(self) -> list[dict]:
        return self.repo.flags_for(self.candidate.session_id)

    @property
    def observations(self) -> list[Any]:
        return self.repo.observations_for(self.candidate.session_id)

    @property
    def proposals(self) -> list[Any]:
        return self.repo.proposals_for(self.candidate.session_id)


def _retrieval(cand: EvalCandidate, turn: EvalTurn) -> SkepticRetrievalData:
    def as_turn(t: EvalTurn) -> SkepticTurn:
        return SkepticTurn(
            id=t.id, turn_index=t.index,
            speaker=TurnSpeaker.CANDIDATE if t.speaker == "CANDIDATE" else TurnSpeaker.INTERVIEWER,
            text=t.text, turn_type=InterviewerTurnType.PLANNED, phase=Phase.PROJECTS,
            primary_thread_id="thread-1", created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=t.index))

    claims = [
        SkepticClaim(id=c["id"], claim_text=c["text"], claim_type=ClaimType(c["type"]), source="RESUME",
                     status=ClaimStatus.UNVERIFIED, confidence=0.9)
        for c in cand.claims.values()
    ]
    return SkepticRetrievalData(
        session_id=cand.session_id, user_id=USER_ID, current_turn=as_turn(turn),
        prior_turns=[as_turn(t) for t in cand.turns if t.index < turn.index],
        claims=claims, entities=[], relations=[])


def make_worker(repo: MemoryEvalRepository, runner: AgentRunner, *, mode: str,
                processor: SkepticResultProcessor | None = None) -> SkepticWorker:
    return SkepticWorker(
        repo, SkepticContextBuilder(repo), runner,
        processor or SkepticResultProcessor(repo, None),  # type: ignore[arg-type]
        model="eval-fake-model", shadow_mode=(mode != "active"), max_attempts=2, retry_base_seconds=1)


def make_flag_service(repo: MemoryEvalRepository, *, mode: str,
                      service_cls: type[FlagEligibilityService] = FlagEligibilityService) -> FlagEligibilityService:
    return service_cls(repo, live_probes=(mode == "active"), shadow_mode=(mode == "shadow"),
                       min_confidence=MIN_CONFIDENCE)


async def run_candidate(
    cand: EvalCandidate, provider: Any, *, mode: str = "active",
    repo: MemoryEvalRepository | None = None, runner: AgentRunner | None = None,
    processor: SkepticResultProcessor | None = None,
    processor_cls: type[SkepticResultProcessor] | None = None,
    service_cls: type[FlagEligibilityService] = FlagEligibilityService,
) -> PipelineRun:
    """Feeds every candidate turn through worker -> processor -> flag eligibility."""
    repo = repo or MemoryEvalRepository()
    runner = runner or build_runner(provider)
    if processor is None and processor_cls is not None:
        processor = processor_cls(repo, None)  # type: ignore[arg-type]
    worker = make_worker(repo, runner, mode=mode, processor=processor)
    service = make_flag_service(repo, mode=mode, service_cls=service_cls)
    run = PipelineRun(cand, mode, repo, provider)
    relevant = [c["id"] for c in cand.claims.values()]
    for turn in cand.candidate_turns:
        repo.retrieval[turn.id] = _retrieval(cand, turn)
        repo.jobs.append(SkepticJob(id=uuid4(), session_id=cand.session_id, turn_id=turn.id,
                                    user_id=USER_ID, attempts=1))
        run.worker_results.append(await worker.run_once("eval-worker"))
        for when, at in (("immediate", turn.index), ("next", turn.index + 1)):
            pending = await service.select(cand.session_id, USER_ID, at, session_active=True,
                                           probe_count=0, relevant_claim_ids=relevant)
            detected = None
            if pending is not None:
                detected = next((r["turn_index"] for r in repo.flags if r["id"] == pending.flag_id), None)
            run.selections.append(SelectionRecord(
                cand.cid, turn.key, mode, at, pending.flag_id if pending else None, detected,
                pending.flag_type if pending else None,
                pending.recommended_turn_type.value if pending else None,
                pending.reason_summary if pending else None,
                pending.suggested_probe if pending else None,
                next((r["proposal"].claim_id for r in repo.flags if pending and r["id"] == pending.flag_id), None),
                when))
    return run


def run_sync(coro):
    import asyncio

    return asyncio.run(coro)
