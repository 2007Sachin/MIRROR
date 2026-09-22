"""Conversation flow check: does the interviewer repeat itself or lean on the fallback?

Runs a short scripted conversation through the real voice pipeline on a throwaway clone of a
prepared session (calls real providers; keep it to about 12 turns).

    python scripts/conversation_flow_check.py --turns 12 --pause 6
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import voice_latency_harness as harness  # noqa: E402

SCRIPT = [
    "yes",
    "I worked on a checkout project where I analysed drop off data and suggested changes to the payment page.",
    "My part was building the dashboard in Tableau and presenting the weekly numbers to my team.",
    "not really",
    "We compared two versions of the page and the new one improved conversion by a small margin, but I am not sure how large the sample was.",
    "I learned that clear communication with the team matters as much as the analysis itself.",
    "Okay",
    "Honestly the hardest part was that the data was messy. Events were logged twice on mobile, some sessions had no user id, and the definitions of a conversion differed between the marketing team and the product team. I spent about two weeks cleaning it up, writing checks in SQL to catch duplicates, agreeing one definition with both teams, and documenting it so the weekly numbers stayed consistent afterwards.",
    "I would start by checking the data quality and then talk to the people who use the report.",
    "Probably around ten percent, I think.",
    "Yes I would.",
    "No, that covers it. Thank you.",
]


class Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.fallbacks = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "interviewer fallback used" in record.getMessage():
            self.fallbacks += 1


def similar(a: str, b: str) -> bool:
    a, b = " ".join(a.lower().split()), " ".join(b.lower().split())
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() > 0.8


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=12)
    parser.add_argument("--pause", type=float, default=6.0)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "apps" / "api"))

    from app.config import get_settings
    from app.dependencies import get_text_to_speech_provider, get_voice_interview_service
    from app.interview_engine import InterviewFlowRejected

    settings = get_settings()
    service = get_voice_interview_service()
    tts = get_text_to_speech_provider()
    db = harness.rest(settings)
    capture = Capture()
    logging.getLogger().addHandler(capture)
    session_id, user_id = harness.clone_session(db)
    interviewer: list[str] = []
    types: list[str] = []
    phases: list[str] = []
    try:
        started = await service.start(session_id, user_id)
        interviewer.append(started.question_text)
        types.append(started.turn_type.value)
        phases.append(started.phase.value)
        for index in range(args.turns):
            answer = SCRIPT[index % len(SCRIPT)]
            result = await tts.synthesize(answer, settings.interview_tts_language)
            if index:
                await asyncio.sleep(args.pause)
            try:
                reply = await service.submit(
                    session_id, user_id, content=result.audio_bytes,
                    claimed_mime_type=result.mime_type, client_turn_id=uuid4(),
                    recorded_duration_ms=4000, audio_upload_ms=0,
                )
            except InterviewFlowRejected:
                print(f"turn {index + 1}: interview finished")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"turn {index + 1}: {type(exc).__name__}")
                continue
            interviewer.append(reply.question_text)
            types.append(reply.turn_type.value)
            phases.append(reply.phase.value)
            print(f"turn {index + 1}: {reply.turn_type.value} [{reply.phase.value}] {reply.question_text[:90]}", flush=True)
        repeats = [
            (i, j) for i in range(len(interviewer)) for j in range(i)
            if similar(interviewer[i], interviewer[j])
        ]
        print("\n== flow check")
        print(f"interviewer turns: {len(interviewer)}")
        print(f"repeats: {len(repeats)} {repeats}")
        print(f"fallback used: {capture.fallbacks}")
        print("turn types:", " ".join(types))
        print("phases:", " ".join(phases))
        print("phase advanced:", len(set(phases)) > 1)
    finally:
        await __import__("app.deferred_writes", fromlist=["x"]).get_deferred_writes().flush_all()
        harness.cleanup(db, session_id)
        left = db.get("sessions", params={"id": f"eq.{session_id}", "select": "id"}).json()
        print("synthetic sessions left:", len(left))


if __name__ == "__main__":
    asyncio.run(main())
