from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from .audio_validation import AudioValidator
from .interview_engine import InterviewFlowRejected, InterviewStateMachine
from .interviewer_models import StoredInterviewTurn, TextTurnRequest, TurnSpeaker
from .interviewer_repository import InterviewTurnRepository
from .interviewer_service import TextInterviewService
from .schemas import SessionStatus
from .speech_providers import (
    SpeechToTextProvider,
    SynthesisProviderFailure,
    TextToSpeechProvider,
    TranscriptionProviderFailure,
)
from .voice_models import (
    AudioStatus,
    OwnedVoiceTurn,
    TtsCacheRecord,
    VoiceLatencyMetrics,
    VoiceTurnResponse,
)
from .voice_repository import (
    InterviewAudioStorage,
    VoicePersistenceUnavailable,
    VoiceRepository,
)


logger = logging.getLogger("mirror.voice")


class TranscriptionFailed(Exception):
    code = "TRANSCRIPTION_FAILED"


class VoiceRequestInProgress(Exception):
    code = "VOICE_REQUEST_IN_PROGRESS"


class VoiceTurnNotFound(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TtsOutcome:
    audio_status: AudioStatus
    audio_url: str | None
    storage_path: str | None
    provider: str | None
    model: str | None
    tts_ms: int = 0
    storage_ms: int = 0


class VoiceInterviewService:
    """Turn-based audio adapter around the existing text interview orchestration."""

    def __init__(
        self,
        state: InterviewStateMachine,
        text_interview: TextInterviewService,
        turns: InterviewTurnRepository,
        repository: VoiceRepository,
        storage: InterviewAudioStorage,
        stt: SpeechToTextProvider,
        tts: TextToSpeechProvider,
        validator: AudioValidator,
        *,
        tts_language: str,
        tts_model: str,
        tts_voice: str,
        signed_url_seconds: int,
        minimum_transcript_confidence: float,
    ) -> None:
        self._state = state
        self._text = text_interview
        self._turns = turns
        self._repository = repository
        self._storage = storage
        self._stt = stt
        self._tts = tts
        self._validator = validator
        self._tts_language = tts_language
        self._tts_model = tts_model
        self._tts_voice = tts_voice
        self._signed_url_seconds = signed_url_seconds
        self._minimum_confidence = minimum_transcript_confidence

    async def start(self, session_id: UUID, user_id: UUID) -> VoiceTurnResponse:
        started = await self._text.start(session_id, user_id)
        rows = await self._turns.list_turns(session_id)
        turn = next(
            (
                item
                for item in rows
                if item.turn_index == started.interviewer_turn_index
                and item.speaker == TurnSpeaker.INTERVIEWER
            ),
            None,
        )
        if turn is None:
            raise VoicePersistenceUnavailable("opening turn was not stored")
        owned = await self._repository.get_owned_turn(turn.id, user_id)
        if owned is None:
            raise VoiceTurnNotFound
        tts = await self._ensure_audio(owned)
        await self._safe_metrics(
            VoiceLatencyMetrics(
                session_id=session_id,
                user_id=user_id,
                turn_index=turn.turn_index,
                interviewer_turn_id=turn.id,
                tts_ms=tts.tts_ms,
                storage_ms=tts.storage_ms,
                total_turn_ms=tts.tts_ms + tts.storage_ms,
                tts_provider=tts.provider,
                tts_model=tts.model,
            )
        )
        return self._response(owned, started.remaining_time_seconds, tts)

    async def submit(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        content: bytes,
        claimed_mime_type: str | None,
        client_turn_id: UUID,
        recorded_duration_ms: int | None,
        audio_upload_ms: int,
    ) -> VoiceTurnResponse:
        total_started = perf_counter()
        session = await self._state.get_state(session_id, user_id)
        if session.status != SessionStatus.ACTIVE:
            raise InterviewFlowRejected("session is not accepting candidate turns")

        processing_started = perf_counter()
        audio = self._validator.validate(
            content, claimed_mime_type, recorded_duration_ms
        )
        audio_processing_ms = self._elapsed(processing_started)
        claim = await self._repository.claim_request(
            session_id, user_id, client_turn_id, recorded_duration_ms
        )
        if not claim.claimed:
            if claim.request.status.value == "COMPLETED" and claim.request.interviewer_turn_id:
                turn = await self._repository.get_owned_turn(
                    claim.request.interviewer_turn_id, user_id
                )
                if turn is None:
                    raise VoiceTurnNotFound
                return await self._existing_response(turn, user_id)
            raise VoiceRequestInProgress

        request = claim.request
        candidate_path = (
            f"interviews/{user_id}/{session_id}/candidate/"
            f"{request.id}.{audio.extension}"
        )
        storage_started = perf_counter()
        await self._storage.upload(
            candidate_path, audio.content, audio.mime_type, upsert=True
        )
        storage_ms = self._elapsed(storage_started)
        await self._repository.set_request_audio(
            request.id, user_id, candidate_path, audio.mime_type
        )

        try:
            stt_result = await self._stt.transcribe(audio.content, audio.mime_type)
        except TranscriptionProviderFailure as exc:
            await self._transcription_failed(
                request.id,
                user_id,
                session_id,
                candidate_path,
                audio_upload_ms,
                audio_processing_ms,
                storage_ms,
                stt_provider=self._stt.provider_name,
                stt_model=getattr(self._stt, "model", None),
            )
            raise TranscriptionFailed from exc

        transcript = stt_result.transcript.strip()
        if (
            not transcript
            or not any(character.isalnum() for character in transcript)
            or len(transcript) > 20_000
            or (
                stt_result.confidence is not None
                and stt_result.confidence < self._minimum_confidence
            )
        ):
            await self._transcription_failed(
                request.id,
                user_id,
                session_id,
                candidate_path,
                audio_upload_ms,
                audio_processing_ms,
                storage_ms,
                stt_ms=stt_result.latency_ms,
                stt_provider=stt_result.provider,
                stt_model=stt_result.model,
            )
            raise TranscriptionFailed

        candidate_holder: list[StoredInterviewTurn] = []

        async def persist_candidate_audio(candidate: StoredInterviewTurn) -> None:
            candidate_holder[:] = [candidate]
            await self._repository.attach_candidate_audio(
                candidate.id,
                user_id,
                {
                    "audio_storage_path": candidate_path,
                    "audio_mime_type": audio.mime_type,
                    "audio_status": "READY",
                    "duration_ms": recorded_duration_ms,
                    "stt_provider": stt_result.provider,
                    "stt_model": stt_result.model,
                    "stt_confidence": stt_result.confidence,
                    "stt_detected_language": stt_result.detected_language,
                    "stt_metadata": stt_result.provider_metadata,
                    "stt_latency_ms": stt_result.latency_ms,
                },
            )

        interview_started = perf_counter()
        text_response = await self._text.submit(
            session_id,
            user_id,
            TextTurnRequest(text=transcript, client_turn_id=client_turn_id),
            on_candidate_ready=persist_candidate_audio,
        )
        text_pipeline_ms = self._elapsed(interview_started)
        candidate = candidate_holder[0] if candidate_holder else None
        if candidate is None:
            candidate = await self._turns.get_candidate_by_client_id(
                session_id, client_turn_id
            )
        if candidate is None:
            raise VoicePersistenceUnavailable("candidate turn was not stored")
        interviewer = await self._turns.get_response(session_id, candidate.id)
        if interviewer is None:
            raise VoicePersistenceUnavailable("interviewer turn was not stored")

        owned_interviewer = await self._repository.get_owned_turn(
            interviewer.id, user_id
        )
        if owned_interviewer is None:
            raise VoiceTurnNotFound
        tts = await self._ensure_audio(owned_interviewer)
        response = self._response(
            owned_interviewer, text_response.remaining_time_seconds, tts
        )
        await self._repository.complete_request(
            request.id,
            user_id,
            candidate.id,
            interviewer.id,
            response.model_copy(update={"audio_url": None}).model_dump(mode="json"),
        )

        interviewer_ms = interviewer.latency_ms or text_pipeline_ms
        context_build_ms = max(0, text_pipeline_ms - interviewer_ms)
        total_ms = audio_upload_ms + self._elapsed(total_started)
        await self._safe_metrics(
            VoiceLatencyMetrics(
                session_id=session_id,
                user_id=user_id,
                turn_index=interviewer.turn_index,
                candidate_turn_id=candidate.id,
                interviewer_turn_id=interviewer.id,
                audio_upload_ms=audio_upload_ms,
                audio_processing_ms=audio_processing_ms,
                stt_ms=stt_result.latency_ms,
                context_build_ms=context_build_ms,
                interviewer_ms=interviewer_ms,
                tts_ms=tts.tts_ms,
                storage_ms=storage_ms + tts.storage_ms,
                total_turn_ms=total_ms,
                stt_provider=stt_result.provider,
                stt_model=stt_result.model,
                tts_provider=tts.provider,
                tts_model=tts.model,
            )
        )
        await self._state.record_event(
            session_id,
            user_id,
            "VOICE_TURN_COMPLETED",
            {
                "candidate_turn_index": candidate.turn_index,
                "interviewer_turn_index": interviewer.turn_index,
                "audio_status": tts.audio_status.value,
                "total_turn_ms": total_ms,
            },
        )
        logger.info(
            "voice turn completed",
            extra={
                "session_id": str(session_id),
                "turn_index": interviewer.turn_index,
                "stt_provider": stt_result.provider,
                "stt_model": stt_result.model,
                "tts_provider": tts.provider,
                "tts_model": tts.model,
                "total_turn_ms": total_ms,
            },
        )
        return response

    async def retry_audio(self, turn_id: UUID, user_id: UUID) -> VoiceTurnResponse:
        turn = await self._repository.get_owned_turn(turn_id, user_id)
        if turn is None or turn.speaker != TurnSpeaker.INTERVIEWER:
            raise VoiceTurnNotFound
        outcome = await self._ensure_audio(turn, force_retry=True)
        session = await self._state.get_state(turn.session_id, user_id)
        _, remaining = self._state.remaining_times(session)
        await self._safe_metrics(
            VoiceLatencyMetrics(
                session_id=turn.session_id,
                user_id=user_id,
                turn_index=turn.turn_index,
                interviewer_turn_id=turn.id,
                tts_ms=outcome.tts_ms,
                storage_ms=outcome.storage_ms,
                total_turn_ms=outcome.tts_ms + outcome.storage_ms,
                tts_provider=outcome.provider,
                tts_model=outcome.model,
            )
        )
        return self._response(turn, remaining, outcome)

    async def _ensure_audio(
        self, turn: OwnedVoiceTurn, *, force_retry: bool = False
    ) -> TtsOutcome:
        if (
            not force_retry
            and turn.audio_status == AudioStatus.READY
            and turn.audio_storage_path
        ):
            try:
                url = await self._storage.signed_url(
                    turn.audio_storage_path, self._signed_url_seconds
                )
                return TtsOutcome(
                    AudioStatus.READY,
                    url,
                    turn.audio_storage_path,
                    turn.tts_provider,
                    turn.tts_model,
                )
            except VoicePersistenceUnavailable:
                return TtsOutcome(AudioStatus.FAILED, None, turn.audio_storage_path, None, None)

        normalized = " ".join(turn.text.split())
        text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        cache_key = hashlib.sha256(
            (
                f"{turn.session_id}\0{self._tts.provider_name}\0{normalized}\0{self._tts_voice}\0"
                f"{self._tts_model}\0{self._tts_language}"
            ).encode("utf-8")
        ).hexdigest()
        cached = await self._repository.get_cache(
            cache_key, turn.user_id, turn.session_id
        )
        if cached:
            try:
                await self._repository.attach_interviewer_audio(
                    turn.id,
                    turn.user_id,
                    {
                        "audio_storage_path": cached.storage_path,
                        "audio_mime_type": cached.mime_type,
                        "audio_status": "READY",
                        "tts_provider": cached.provider,
                        "tts_model": cached.model,
                        "tts_voice": cached.voice,
                        "tts_language": cached.language,
                        "tts_metadata": {"cache_hit": True},
                        "tts_latency_ms": 0,
                    },
                )
                url = await self._storage.signed_url(
                    cached.storage_path, self._signed_url_seconds
                )
                return TtsOutcome(
                    AudioStatus.READY, url, cached.storage_path, cached.provider,
                    cached.model
                )
            except VoicePersistenceUnavailable:
                pass

        try:
            result = await self._tts.synthesize(normalized, self._tts_language)
            extension = {
                "audio/wav": "wav",
                "audio/mpeg": "mp3",
                "audio/ogg": "ogg",
                "audio/webm": "webm",
                "audio/mp4": "m4a",
            }.get(result.mime_type)
            if extension is None:
                raise SynthesisProviderFailure("unsupported synthesized audio type")
            storage_path = (
                f"interviews/{turn.user_id}/{turn.session_id}/mirror/"
                f"{turn.id}-{cache_key[:12]}.{extension}"
            )
            storage_started = perf_counter()
            await self._storage.upload(
                storage_path, result.audio_bytes, result.mime_type, upsert=True
            )
            storage_ms = self._elapsed(storage_started)
            cache = TtsCacheRecord(
                cache_key=cache_key,
                user_id=turn.user_id,
                session_id=turn.session_id,
                provider=result.provider,
                model=result.model,
                voice=result.voice,
                language=result.language,
                storage_path=storage_path,
                mime_type=result.mime_type,
            )
            await self._repository.save_cache(cache, text_hash)
            await self._repository.attach_interviewer_audio(
                turn.id,
                turn.user_id,
                {
                    "audio_storage_path": storage_path,
                    "audio_mime_type": result.mime_type,
                    "audio_status": "READY",
                    "tts_provider": result.provider,
                    "tts_model": result.model,
                    "tts_voice": result.voice,
                    "tts_language": result.language,
                    "tts_metadata": result.provider_metadata,
                    "tts_latency_ms": result.latency_ms,
                },
            )
            url = await self._storage.signed_url(
                storage_path, self._signed_url_seconds
            )
            return TtsOutcome(
                AudioStatus.READY,
                url,
                storage_path,
                result.provider,
                result.model,
                result.latency_ms,
                storage_ms,
            )
        except (SynthesisProviderFailure, VoicePersistenceUnavailable):
            try:
                await self._repository.attach_interviewer_audio(
                    turn.id, turn.user_id, {"audio_status": "FAILED"}
                )
            except VoicePersistenceUnavailable:
                pass
            return TtsOutcome(
                AudioStatus.FAILED,
                None,
                None,
                self._tts.provider_name,
                self._tts_model,
            )

    async def _existing_response(
        self, turn: OwnedVoiceTurn, user_id: UUID
    ) -> VoiceTurnResponse:
        session = await self._state.get_state(turn.session_id, user_id)
        _, remaining = self._state.remaining_times(session)
        outcome = await self._ensure_audio(turn)
        return self._response(turn, remaining, outcome)

    async def _transcription_failed(
        self,
        request_id: UUID,
        user_id: UUID,
        session_id: UUID,
        path: str,
        upload_ms: int,
        processing_ms: int,
        storage_ms: int,
        *,
        stt_ms: int = 0,
        stt_provider: str | None = None,
        stt_model: str | None = None,
    ) -> None:
        try:
            await self._storage.delete(path)
        except VoicePersistenceUnavailable:
            logger.warning(
                "failed transcription audio cleanup failed",
                extra={"session_id": str(session_id)},
            )
        await self._repository.fail_request(
            request_id, user_id, TranscriptionFailed.code
        )
        await self._safe_metrics(
            VoiceLatencyMetrics(
                session_id=session_id,
                user_id=user_id,
                audio_upload_ms=upload_ms,
                audio_processing_ms=processing_ms,
                stt_ms=stt_ms,
                storage_ms=storage_ms,
                total_turn_ms=upload_ms + processing_ms + stt_ms + storage_ms,
                stt_provider=stt_provider,
                stt_model=stt_model,
            )
        )
        await self._state.record_event(
            session_id,
            user_id,
            "VOICE_TRANSCRIPTION_FAILED",
            {"error_code": TranscriptionFailed.code},
        )

    async def _safe_metrics(self, metrics: VoiceLatencyMetrics) -> None:
        try:
            await self._repository.record_metrics(metrics)
        except VoicePersistenceUnavailable:
            logger.warning(
                "voice metrics persistence failed",
                extra={"session_id": str(metrics.session_id)},
            )

    @staticmethod
    def _response(
        turn: OwnedVoiceTurn, remaining: int, outcome: TtsOutcome
    ) -> VoiceTurnResponse:
        return VoiceTurnResponse(
            session_id=turn.session_id,
            turn_id=turn.id,
            question_text=turn.text,
            audio_url=outcome.audio_url,
            audio_status=outcome.audio_status,
            turn_index=turn.turn_index,
            phase=turn.phase,
            turn_type=turn.turn_type,
            remaining_time_seconds=remaining,
        )

    @staticmethod
    def _elapsed(started: float) -> int:
        return max(0, round((perf_counter() - started) * 1000))

