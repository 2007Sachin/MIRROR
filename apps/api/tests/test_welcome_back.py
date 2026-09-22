"""Resuming a saved conversation adds a welcome line without a duplicate interviewer turn."""

import asyncio

from app.interviewer_service import WELCOME_BACK_TEXT
from tests.test_interviewer_agent import (
    USER_A, QueueTts, decision, setup_service, setup_voice, tts_result,
)


def test_text_start_welcomes_back_only_after_a_pause():
    text, engine, _, turns, _, session_id = asyncio.run(setup_service(decision()))
    first = asyncio.run(text.start(session_id, USER_A))
    assert first.welcome_back is False and first.welcome_text is None
    again = asyncio.run(text.start(session_id, USER_A))
    assert again.welcome_back is False

    asyncio.run(engine.pause(session_id, USER_A))
    back = asyncio.run(text.start(session_id, USER_A))
    assert back.welcome_back is True and back.welcome_text == WELCOME_BACK_TEXT
    assert back.question_text == first.question_text
    assert back.interviewer_turn_index == first.interviewer_turn_index
    stored = asyncio.run(turns.list_turns(session_id))
    assert len([t for t in stored if t.speaker.value == "INTERVIEWER"]) == 1

    after = asyncio.run(text.start(session_id, USER_A))
    assert after.welcome_back is False


def test_voice_start_returns_cached_welcome_audio_and_no_extra_turn():
    voice, engine, turns, _, _, _, tts, session_id = asyncio.run(setup_voice(decision(), tts=QueueTts(tts_result(), tts_result())))
    first = asyncio.run(voice.start(session_id, USER_A))
    assert first.welcome_back is False and first.welcome_audio_url is None

    asyncio.run(engine.pause(session_id, USER_A))
    back = asyncio.run(voice.start(session_id, USER_A))
    assert back.welcome_back is True
    assert back.welcome_text == WELCOME_BACK_TEXT
    assert back.welcome_audio_url
    assert back.turn_id == first.turn_id and back.question_text == first.question_text
    stored = asyncio.run(turns.list_turns(session_id))
    assert len([t for t in stored if t.speaker.value == "INTERVIEWER"]) == 1

    calls = tts.calls
    asyncio.run(engine.pause(session_id, USER_A))
    again = asyncio.run(voice.start(session_id, USER_A))
    assert again.welcome_back is True and again.welcome_audio_url
    assert tts.calls == calls  # welcome audio came from the cache
