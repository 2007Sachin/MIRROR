"""Session lifecycle routes that are not part of a running conversation.

`POST /api/v1/sessions/{session_id}/abandon` discards a practice that has not finished
(CREATED, PREPARING, READY or ACTIVE). Owner-only: another person's session is 404.
Idempotent: an already abandoned session returns 200 unchanged. A session that reached
review (ASSESSING, COMPLETED) or FAILED is 409. Abandoning never enqueues a review.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from .auth import current_user_id
from .deferred_writes import get_deferred_writes
from .dependencies import get_interview_state_machine
from .interview_engine import (
    ConcurrentSessionChange,
    IllegalSessionTransition,
    InterviewStateMachine,
    SessionNotFound,
)
from .schemas import SessionRead

router = APIRouter()


@router.post("/api/v1/sessions/{session_id}/abandon", response_model=SessionRead)
async def abandon_session(
    session_id: UUID,
    user_id: UUID = Depends(current_user_id),
    engine: InterviewStateMachine = Depends(get_interview_state_machine),
) -> SessionRead:
    await get_deferred_writes().flush(session_id)  # pending turn writes land before the session closes
    try:
        for _ in range(2):  # a concurrent turn write moved updated_at: re-read and try again
            try:
                return await engine.abandon(session_id, user_id)
            except ConcurrentSessionChange:
                pass
        return await engine.abandon(session_id, user_id)
    except SessionNotFound as exc:
        raise HTTPException(status_code=404, detail="We couldn't find that session.") from exc
    except IllegalSessionTransition as exc:
        raise HTTPException(status_code=409, detail="This practice has already finished, so it can't be discarded.") from exc
    except ConcurrentSessionChange as exc:
        raise HTTPException(
            status_code=409, detail="Your session changed while we were working. Please refresh and try again."
        ) from exc
