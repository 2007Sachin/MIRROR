from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from app.agents.definitions import (
    AgentErrorType,
    ProviderRequest,
    ProviderResponse,
    ToolCall,
)
from app.agents.errors import (
    DuplicateAgentError,
    PromptNotFoundError,
    ProviderFailureError,
    UnknownAgentError,
)
from app.agents.prompts import PromptLoader
from app.agents.registry import AgentRegistry
from app.agents.runner import AgentRunner
from app.agents.testing import create_framework_test_agent
from app.agents.tools import ToolDefinition, ToolRegistry


PROMPT_ROOT = Path(__file__).parents[1] / "app" / "prompts"


class FakeProvider:
    def __init__(self, *responses: ProviderResponse | Exception) -> None:
        self.responses = deque(responses)
        self.requests: list[ProviderRequest] = []

    async def complete(
        self, request: ProviderRequest, *, timeout_seconds: float
    ) -> ProviderResponse:
        self.requests.append(request)
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response


class SlowProvider:
    async def complete(
        self, request: ProviderRequest, *, timeout_seconds: float
    ) -> ProviderResponse:
        await asyncio.sleep(0.05)
        return ProviderResponse(content={"normalized_text": "late"})


class CapturingLogger:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, fields: dict[str, Any]) -> None:
        self.events.append(fields)


class EchoToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


def registry_for(agent: Any | None = None) -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(agent or create_framework_test_agent("test-model"))
    return registry


def runner_for(
    provider: Any, *, agent: Any | None = None, tools: ToolRegistry | None = None
) -> AgentRunner:
    return AgentRunner(
        registry_for(agent),
        provider,
        PromptLoader(PROMPT_ROOT),
        tool_registry=tools,
        execution_logger=CapturingLogger(),
    )


def test_agent_registration_and_unknown_agent() -> None:
    agent = create_framework_test_agent("test-model")
    registry = registry_for(agent)
    assert registry.get("framework_test") is agent
    with pytest.raises(DuplicateAgentError):
        registry.register(agent)
    with pytest.raises(UnknownAgentError):
        registry.get("missing")


def test_runner_normalizes_unknown_agent() -> None:
    runner = AgentRunner(AgentRegistry(), FakeProvider(), PromptLoader(PROMPT_ROOT))
    result = asyncio.run(runner.run("missing", {"text": "hello"}))
    assert result.success is False
    assert result.error_type == AgentErrorType.UNKNOWN_AGENT


def test_input_validation_happens_before_provider_call() -> None:
    provider = FakeProvider()
    result = asyncio.run(runner_for(provider).run("framework_test", {"text": ""}))
    assert result.error_type == AgentErrorType.INPUT_VALIDATION
    assert provider.requests == []


def test_valid_structured_output_and_request_schema() -> None:
    provider = FakeProvider(
        ProviderResponse(
            content='{"normalized_text":"hello"}', input_tokens=7, output_tokens=3
        )
    )
    result = asyncio.run(runner_for(provider).run("framework_test", {"text": "hello"}))
    assert result.success is True
    assert result.output == {"normalized_text": "hello"}
    assert result.input_tokens == 7
    assert result.output_tokens == 3
    assert provider.requests[0].output_schema_name == "framework_test_output"
    assert "normalized_text" in provider.requests[0].output_json_schema["properties"]


def test_invalid_json_is_classified_after_retry() -> None:
    provider = FakeProvider(
        ProviderResponse(content="not-json"), ProviderResponse(content="still-not-json")
    )
    result = asyncio.run(runner_for(provider).run("framework_test", {"text": "hello"}))
    assert result.success is False
    assert result.error_type == AgentErrorType.INVALID_STRUCTURED_OUTPUT
    assert result.retry_count == 1
    assert len(provider.requests) == 2


def test_output_validation_failure_is_distinct() -> None:
    provider = FakeProvider(
        ProviderResponse(content={"wrong": "value"}),
        ProviderResponse(content={"wrong": "value"}),
    )
    result = asyncio.run(runner_for(provider).run("framework_test", {"text": "hello"}))
    assert result.error_type == AgentErrorType.VALIDATION_FAILURE


def test_malformed_output_retries_then_succeeds() -> None:
    provider = FakeProvider(
        ProviderResponse(content="bad"),
        ProviderResponse(content={"normalized_text": "hello"}),
    )
    result = asyncio.run(runner_for(provider).run("framework_test", {"text": "hello"}))
    assert result.success is True
    assert result.retry_count == 1
    assert len(provider.requests) == 2


def test_provider_failure_is_classified_without_retry() -> None:
    provider = FakeProvider(ProviderFailureError("unavailable"))
    result = asyncio.run(runner_for(provider).run("framework_test", {"text": "hello"}))
    assert result.error_type == AgentErrorType.PROVIDER_FAILURE
    assert result.retry_count == 0


def test_runner_enforces_agent_timeout() -> None:
    agent = replace(create_framework_test_agent("test-model"), timeout_seconds=0.01)
    result = asyncio.run(
        runner_for(SlowProvider(), agent=agent).run("framework_test", {"text": "hello"})
    )
    assert result.error_type == AgentErrorType.TIMEOUT


def test_unapproved_tool_call_is_rejected() -> None:
    provider = FakeProvider(
        ProviderResponse(
            tool_calls=(ToolCall(id="call-1", name="arbitrary_sql", arguments={}),)
        )
    )
    result = asyncio.run(runner_for(provider).run("framework_test", {"text": "hello"}))
    assert result.error_type == AgentErrorType.TOOL_PERMISSION
    assert len(provider.requests) == 1


def test_registered_allowed_tool_can_be_invoked() -> None:
    agent = replace(create_framework_test_agent("test-model"), allowed_tools=("echo",))
    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            name="echo",
            description="Echo a test value",
            input_schema=EchoToolInput,
            handler=lambda value, context: {"value": value.value},
        )
    )
    provider = FakeProvider(
        ProviderResponse(
            tool_calls=(
                ToolCall(id="call-1", name="echo", arguments={"value": "hello"}),
            )
        ),
        ProviderResponse(content={"normalized_text": "hello"}),
    )
    result = asyncio.run(
        runner_for(provider, agent=agent, tools=tools).run(
            "framework_test", {"text": "hello"}
        )
    )
    assert result.success is True
    assert provider.requests[0].tools[0]["function"]["name"] == "echo"
    assert provider.requests[1].messages[-1]["role"] == "tool"


def test_prompt_version_loading(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "framework_test"
    prompt_dir.mkdir()
    (prompt_dir / "v2.md").write_text("version two", encoding="utf-8")
    loader = PromptLoader(tmp_path)
    assert loader.load("framework_test", "v2") == "version two"
    with pytest.raises(PromptNotFoundError):
        loader.load("framework_test", "v1")
    with pytest.raises(PromptNotFoundError):
        loader.load("../secrets", "v2")


def test_execution_logs_exclude_input_and_output_content() -> None:
    logger = CapturingLogger()
    runner = AgentRunner(
        registry_for(),
        FakeProvider(ProviderResponse(content={"normalized_text": "secret"})),
        PromptLoader(PROMPT_ROOT),
        execution_logger=logger,
    )
    asyncio.run(runner.run("framework_test", {"text": "sensitive input"}))
    event = logger.events[0]
    assert "input" not in event
    assert "output" not in event
    assert event["success"] is True

