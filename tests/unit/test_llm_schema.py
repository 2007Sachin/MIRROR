import json

from app.agents.providers import _strict_json_schema
from app.interviewer_models import InterviewerDecision
from app.planner_models import InterviewPlanDraft


def test_optional_fields_become_nullable_types_not_anyof() -> None:
    schema = _strict_json_schema(InterviewerDecision.model_json_schema())
    text = json.dumps(schema)
    assert "anyOf" not in text and "$ref" not in text and "$defs" not in text
    phase = schema["properties"]["requested_phase_transition"]
    assert None in phase["enum"] and "null" in phase["type"] and "INTRO" in phase["enum"]
    assert "null" in schema["properties"]["used_flag_id"]["type"]


def test_every_property_is_required_and_closed() -> None:
    schema = _strict_json_schema(InterviewPlanDraft.model_json_schema())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_provider_accepts_null_tool_calls_and_sends_bearer_key() -> None:
    import asyncio

    import httpx

    from app.agents.definitions import ProviderRequest
    from app.agents.providers import ChatCompletionsProvider

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "{}", "tool_calls": None}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })

    request = ProviderRequest(
        model="sarvam-105b-conversations", temperature=0,
        messages=[{"role": "user", "content": "hi"}],
        output_schema_name="X", output_json_schema={"type": "object", "properties": {}},
    )

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ChatCompletionsProvider("k", client=client).complete(request, timeout_seconds=5)

    result = asyncio.run(go())
    assert result.content == "{}" and result.tool_calls == ()
    assert seen["auth"] == "Bearer k" and seen["url"].startswith("https://api.sarvam.ai/v1/")
