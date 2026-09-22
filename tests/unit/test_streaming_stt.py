import asyncio
import io
import json
import wave

import pytest
import websockets

pytest.importorskip("av", reason="PyAV is required for streaming STT audio decoding")

from app.speech_providers import SarvamStreamingSpeechToTextProvider, decode_to_pcm16k


def wav_bytes(seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\x01\x00" * int(16000 * seconds))
    return buffer.getvalue()


def run_against_fake_server(seconds: float, replies: list[dict], rest_limit: float = 25.0):
    received: list[dict] = []

    async def handler(ws):
        async for raw in ws:
            message = json.loads(raw)
            received.append(message)
            if message.get("type") == "flush":
                for reply in replies:
                    await ws.send(json.dumps(reply))

    async def go():
        async with websockets.serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            provider = SarvamStreamingSpeechToTextProvider(
                "key", ws_url=f"ws://127.0.0.1:{port}", rest_limit_seconds=rest_limit, grace_seconds=0.2
            )
            return await provider.transcribe(wav_bytes(seconds), "audio/wav")

    return asyncio.run(go()), received


def test_decoder_returns_16k_mono_pcm() -> None:
    assert len(decode_to_pcm16k(wav_bytes(2.0))) == 2 * 32_000


def test_long_answer_is_streamed_in_chunks_then_flushed() -> None:
    reply = {"type": "data", "data": {"request_id": "r1", "transcript": "a long answer", "language_code": "en-IN"}}
    result, received = run_against_fake_server(5.0, [reply], rest_limit=1.0)
    audio = [m for m in received if "audio" in m]
    assert len(audio) == 5 and received[-1] == {"type": "flush"}
    assert result.transcript == "a long answer" and result.provider_metadata["streaming"] is True


def test_several_result_messages_are_joined_in_order() -> None:
    replies = [{"type": "data", "data": {"transcript": "first part"}}, {"type": "data", "data": {"transcript": "second part"}}]
    result, _ = run_against_fake_server(3.0, replies, rest_limit=1.0)
    assert result.transcript == "first part second part"


def test_server_error_becomes_a_provider_failure() -> None:
    from app.speech_providers import TranscriptionProviderFailure

    try:
        run_against_fake_server(3.0, [{"type": "error", "data": {"error": "bad", "code": "x"}}], rest_limit=1.0)
    except TranscriptionProviderFailure:
        return
    raise AssertionError("expected a TranscriptionProviderFailure")
