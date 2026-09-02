from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from .claims_models import ClaimRead, ClaimStatus, EvidenceDirection
from .claims_repository import CLAIM_COLUMNS, ClaimsGraphUnavailable, SupabaseClaimsGraphRepository, _claim
from .report_models import (
    ReportClaim,
    ReportClaimsAudit,
    ReportEvidence,
    ReportReadiness,
    ReportResponse,
    ReportSession,
    ReportSessionMoment,
    ReportVerdict,
    SessionMomentType,
    TrustAndLimitations,
)
from .schemas import SessionEventRead, SessionRead, SessionStatus
from .specialist_assessor_models import SpecialistAssessmentOutput
from .verdict_models import VerdictCode


class ReportNotFound(Exception):
    pass


class ReportAssessmentIncomplete(Exception):
    pass


class ReportUnavailable(Exception):
    pass


class ReportRepository(Protocol):
    async def get_session(self, session_id: UUID, user_id: UUID) -> SessionRead | None: ...
    async def get_result(self, session_id: UUID, user_id: UUID) -> dict[str, Any] | None: ...
    async def list_claims(self, session_id: UUID, user_id: UUID) -> list[ClaimRead]: ...
    async def list_evidence(self, claim_ids: list[UUID], user_id: UUID) -> list[dict[str, Any]]: ...
    async def list_specialists(self, session_id: UUID, user_id: UUID) -> list[dict[str, Any]]: ...
    async def list_events(self, session_id: UUID, user_id: UUID) -> list[SessionEventRead]: ...


class SupabaseReportRepository(SupabaseClaimsGraphRepository):
    """Read-only report aggregate. Each collection is fetched in one query."""

    async def get_session(self, session_id: UUID, user_id: UUID) -> SessionRead | None:
        rows = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "*", "limit": "1"})
        return SessionRead.model_validate(rows[0]) if rows else None

    async def get_result(self, session_id: UUID, user_id: UUID) -> dict[str, Any] | None:
        sessions = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not sessions:
            return None
        rows = await self._get("session_results", {"session_id": f"eq.{session_id}", "select": "*", "limit": "1"})
        return dict(rows[0]) if rows else None

    async def list_claims(self, session_id: UUID, user_id: UUID) -> list[ClaimRead]:
        # Include resume claims (session_id null) and spoken claims for this session.
        rows = await self._get("claims", {
            "user_id": f"eq.{user_id}",
            "or": f"(session_id.eq.{session_id},session_id.is.null)",
            "select": CLAIM_COLUMNS,
            "order": "created_at.asc",
            "limit": "1000",
        })
        return [_claim(row) for row in rows]

    async def list_evidence(self, claim_ids: list[UUID], user_id: UUID) -> list[dict[str, Any]]:
        if not claim_ids:
            return []
        return await self._get("claim_evidence", {
            "user_id": f"eq.{user_id}",
            "claim_id": f"in.({','.join(str(value) for value in claim_ids)})",
            "validated": "eq.true",
            "select": "id,claim_id,turn_id,document_id,quote_text,evidence_direction,strength,created_at",
            "order": "created_at.asc",
            "limit": "1000",
        })

    async def list_specialists(self, session_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        sessions = await self._get("sessions", {"id": f"eq.{session_id}", "user_id": f"eq.{user_id}", "select": "id", "limit": "1"})
        if not sessions:
            return []
        return await self._get("specialist_assessments", {
            "session_id": f"eq.{session_id}",
            "select": "assessor_type,status,result_json,created_at",
            "order": "created_at.desc",
            "limit": "30",
        })

    async def list_events(self, session_id: UUID, user_id: UUID) -> list[SessionEventRead]:
        rows = await self._get("session_events", {
            "session_id": f"eq.{session_id}", "user_id": f"eq.{user_id}",
            "select": "*", "order": "created_at.asc", "limit": "500",
        })
        return [SessionEventRead.model_validate(row) for row in rows]


class ReportService:
    def __init__(self, repository: ReportRepository) -> None:
        self._repository = repository

    async def get_report(self, session_id: UUID, user_id: UUID) -> ReportResponse:
        try:
            session = await self._repository.get_session(session_id, user_id)
        except ClaimsGraphUnavailable as exc:
            raise ReportUnavailable from exc
        if session is None:
            raise ReportNotFound
        if session.status != SessionStatus.COMPLETED:
            raise ReportAssessmentIncomplete
        try:
            result = await self._repository.get_result(session_id, user_id)
            if not result:
                raise ReportAssessmentIncomplete
            claims = await self._repository.list_claims(session_id, user_id)
            evidence_rows = await self._repository.list_evidence([claim.id for claim in claims], user_id)
            specialists = await self._repository.list_specialists(session_id, user_id)
            events = await self._repository.list_events(session_id, user_id)
        except ReportAssessmentIncomplete:
            raise
        except ClaimsGraphUnavailable as exc:
            raise ReportUnavailable from exc
        evidence_by_claim = self._evidence_by_claim(evidence_rows, events)

        confidence = _number(result.get("assessment_confidence"), 0.0)
        session_view = ReportSession(
            target_role=session.target_role,
            completed_at=session.completed_at or session.updated_at,
            duration_seconds=self._duration(session),
            assessment_confidence=confidence,
        )
        role = self._readiness(result, "role", confidence)
        interview = self._readiness(result, "interview", confidence)
        verdict_code = self._verdict_code(result)
        verdict = ReportVerdict(
            code=verdict_code,
            label=_verdict_label(verdict_code),
            summary=str(result.get("summary") or "Your result reflects the evidence available in this interview."),
        )
        audit = self._audit(claims, evidence_by_claim)
        return ReportResponse(
            session=session_view,
            verdict=verdict,
            role_readiness=role,
            interview_readiness=interview,
            claims_audit=audit,
            skill_assessments=self._skill_assessments(specialists, evidence_by_claim),
            session_moments=self._moments(events, evidence_rows),
            root_cause=str(result.get("root_cause_code") or result.get("root_cause") or "ROLE_SKILL_GAP"),
            trust_and_limitations=TrustAndLimitations(
                outcome_validation_status="NOT_VALIDATED",
            ),
            prescription=None,
        )

    @staticmethod
    def _duration(session: SessionRead) -> int:
        if session.started_at and session.completed_at:
            return max(0, round((session.completed_at - session.started_at).total_seconds()))
        return max(0, session.elapsed_seconds)

    @staticmethod
    def _verdict_code(result: dict[str, Any]) -> VerdictCode:
        raw = result.get("verdict_code") or result.get("verdict_word") or VerdictCode.NOT_READY_YET.value
        text = str(raw).upper().replace(" ", "_")
        aliases = {"NOT_READY": "NOT_READY_YET", "STABLE": "NEAR_READY", "NOT_ENOUGH_SIGNAL": "NOT_READY_YET"}
        return VerdictCode(aliases.get(text, text))

    @staticmethod
    def _readiness(result: dict[str, Any], prefix: str, confidence: float) -> ReportReadiness:
        low = _int_or_none(result.get(f"{prefix}_readiness_low"))
        high = _int_or_none(result.get(f"{prefix}_readiness_high"))
        if low is None or high is None:
            low = high = None
            label = "Not enough signal"
        else:
            label = "Available"
        signal = str(result.get(f"{prefix}_signal_strength") or result.get("availability_status") or _signal_label(confidence))
        note = str(result.get("confidence_note") or "This range reflects the amount and quality of evidence collected.")
        return ReportReadiness(low=low, high=high, label=label, signal_strength=signal, confidence_note=note)

    @classmethod
    def _audit(cls, claims: list[ClaimRead], evidence: dict[UUID, list[ReportEvidence]]) -> ReportClaimsAudit:
        grouped: dict[ClaimStatus, list[ReportClaim]] = {status: [] for status in ClaimStatus}
        for claim in claims:
            grouped[claim.status].append(ReportClaim(
                id=claim.id, claim_text=claim.claim_text, source=claim.source,
                status=claim.status, explanation=_claim_explanation(claim.status),
                evidence=evidence.get(claim.id, []), confidence=claim.confidence,
            ))
        return ReportClaimsAudit(
            held=grouped[ClaimStatus.CORROBORATED], partially_held=grouped[ClaimStatus.PARTIALLY_HELD],
            walked_back=grouped[ClaimStatus.WALKED_BACK], contradicted=grouped[ClaimStatus.CONTRADICTED],
            insufficient_evidence=grouped[ClaimStatus.INSUFFICIENT_EVIDENCE], unverified=grouped[ClaimStatus.UNVERIFIED],
        )

    @staticmethod
    def _evidence_by_claim(rows: list[dict[str, Any]], events: list[SessionEventRead]) -> dict[UUID, list[ReportEvidence]]:
        timecodes: dict[str, int] = {}
        for event in events:
            turn_id = event.payload.get("turn_id")
            timecode = event.payload.get("timecode_ms")
            if turn_id and isinstance(timecode, int):
                timecodes[str(turn_id)] = timecode
        grouped: dict[UUID, list[ReportEvidence]] = {}
        for row in rows:
            try:
                claim_id = UUID(str(row["claim_id"]))
                turn_id = UUID(str(row["turn_id"])) if row.get("turn_id") else None
                direction = EvidenceDirection(str(row.get("evidence_direction", "CONTEXT_ONLY")).upper())
            except (KeyError, TypeError, ValueError):
                continue
            quote = str(row.get("quote_text") or "").strip()
            if not quote:
                continue
            grouped.setdefault(claim_id, []).append(ReportEvidence(
                turn_id=turn_id, timecode_ms=timecodes.get(str(turn_id)) if turn_id else None,
                quote=quote, direction=direction,
            ))
        return grouped

    @staticmethod
    def _skill_assessments(rows: list[dict[str, Any]], evidence: dict[UUID, list[ReportEvidence]]) -> list[Any]:
        from .report_models import ReportSkillAssessment
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            kind = str(row.get("assessor_type", "")).upper()
            latest.setdefault(kind, row)
        output: list[ReportSkillAssessment] = []
        for row in latest.values():
            try:
                parsed = SpecialistAssessmentOutput.model_validate(row.get("result_json") or {})
            except Exception:
                continue
            for domain in parsed.dimensions + parsed.competency_or_domain_assessments:
                quotes = [ReportEvidence(turn_id=item.turn_id, quote=item.quote, direction=EvidenceDirection.CONTEXT_ONLY) for item in domain.evidence_quotes]
                output.append(ReportSkillAssessment(
                    skill=domain.domain, status=domain.status.value,
                    signal_strength=domain.signal_strength.value, evidence=quotes,
                    explanation=domain.reason_summary,
                ))
        return output

    @staticmethod
    def _moments(events: list[SessionEventRead], evidence_rows: list[dict[str, Any]]) -> list[ReportSessionMoment]:
        moments: list[ReportSessionMoment] = []
        mapping = {
            "RECOVERY_TRIGGERED": SessionMomentType.RECOVERY,
            "OWNERSHIP_CLARIFICATION": SessionMomentType.OWNERSHIP_CLARIFICATION,
            "UNSUPPORTED_SCALE": SessionMomentType.UNSUPPORTED_SCALE,
            "TECHNICAL_DEPTH": SessionMomentType.TECHNICAL_DEPTH,
        }
        for event in events:
            kind = mapping.get(event.event_type.upper())
            if kind is None:
                continue
            turn_id = _uuid(event.payload.get("turn_id"))
            quote = event.payload.get("quote")
            moments.append(ReportSessionMoment(type=kind, turn_id=turn_id, quote=str(quote) if quote else None, explanation=str(event.payload.get("explanation") or "Recorded during the interview.")))
        for row in evidence_rows:
            if str(row.get("strength", "")).upper() != "STRONG" or not row.get("quote_text"):
                continue
            moments.append(ReportSessionMoment(type=SessionMomentType.STRONG_EVIDENCE, turn_id=_uuid(row.get("turn_id")), quote=str(row["quote_text"]), explanation="Strong supporting evidence was recorded."))
        return moments[:50]


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def _signal_label(confidence: float) -> str:
    if confidence < 0.34:
        return "NONE"
    if confidence < 0.67:
        return "MODERATE"
    return "STRONG"


def _verdict_label(code: VerdictCode) -> str:
    return {VerdictCode.NOT_READY_YET: "Not ready yet", VerdictCode.DEVELOPING: "Developing", VerdictCode.NEAR_READY: "Near ready", VerdictCode.READY: "Ready", VerdictCode.STRONG: "Strong"}[code]


def _claim_explanation(status: ClaimStatus) -> str:
    return {
        ClaimStatus.CORROBORATED: "Supported by the available interview evidence.",
        ClaimStatus.PARTIALLY_HELD: "Some parts were supported, while other details remained incomplete.",
        ClaimStatus.WALKED_BACK: "You narrowed or corrected this claim during the interview.",
        ClaimStatus.CONTRADICTED: "The available evidence conflicted with this claim.",
        ClaimStatus.INSUFFICIENT_EVIDENCE: "There was not enough evidence to evaluate this claim.",
        ClaimStatus.UNVERIFIED: "This claim was not tested enough in the interview.",
    }[status]

