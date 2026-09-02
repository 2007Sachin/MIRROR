from __future__ import annotations

import asyncio
import json
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from .base import BaseAgent
from .definitions import (
    AgentErrorType,
    AgentExecutionContext,
    AgentExecutionResult,
    ProviderRequest,
    ProviderResponse,
)
from .errors import (
    AgentError,
    AgentInputValidationError,
    AgentTimeoutError,
    InvalidStructuredOutputError,
    OutputValidationError,
    ToolExecutionError,
)
from .logging import AgentExecutionLogger, StructuredAgentLogger
from .prompts import PromptLoader
from .providers import AgentProvider
from .registry import AgentRegistry
from .tools import ToolRegistry


class AgentRunner:
    """Application-owned execution boundary for all model agents."""

    def __init__(
        self,
        registry: AgentRegistry,
        provider: AgentProvider,
        prompt_loader: PromptLoader,
        *,
        tool_registry: ToolRegistry | None = None,
        execution_logger: AgentExecutionLogger | None = None,
    ) -> None:
        self._registry = registry
        self._provider = provider
        self._prompt_loader = prompt_loader
        self._tools = tool_registry or ToolRegistry()
        self._logger = execution_logger or StructuredAgentLogger()

    async def run(
        self,
        agent_name: str,
        payload: BaseModel | dict[str, Any],
        *,
        context: AgentExecutionContext | None = None,
    ) -> AgentExecutionResult:
        execution_id = uuid4()
        started = perf_counter()
        execution_context = context or AgentExecutionContext()
        agent: BaseAgent | None = None
        retry_count = 0
        input_tokens = output_tokens = 0
        has_input_tokens = has_output_tokens = False

        try:
            agent = self._registry.get(agent_name)
            validated_input = self._validate_input(agent, payload)
            prompt = self._prompt_loader.load(agent.name, agent.prompt_version)
            request = ProviderRequest(
                model=agent.model,
                temperature=agent.temperature,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": validated_input.model_dump_json()},
                ],
                output_schema_name=f"{agent.name}_output",
                output_json_schema=agent.output_schema.model_json_schema(),
                tools=self._tools.specs_for(agent.allowed_tools),
            )

            while True:
                try:
                    response = await self._complete(request, agent.timeout_seconds)
                    input_tokens, has_input_tokens = self._add_tokens(
                        input_tokens, has_input_tokens, response.input_tokens
                    )
                    output_tokens, has_output_tokens = self._add_tokens(
                        output_tokens, has_output_tokens, response.output_tokens
                    )
                    if response.tool_calls:
                        response = await self._complete_after_tools(
                            request, response, agent, execution_context
                        )
                        input_tokens, has_input_tokens = self._add_tokens(
                            input_tokens, has_input_tokens, response.input_tokens
                        )
                        output_tokens, has_output_tokens = self._add_tokens(
                            output_tokens, has_output_tokens, response.output_tokens
                        )
                    output = self._validate_output(agent, response)
                    result = self._result(
                        execution_id,
                        agent.name,
                        agent.model,
                        agent.prompt_version,
                        True,
                        output.model_dump(mode="json"),
                        started,
                        retry_count,
                        None,
                        input_tokens if has_input_tokens else None,
                        output_tokens if has_output_tokens else None,
                    )
                    self._emit(result, execution_context)
                    return result
                except (InvalidStructuredOutputError, OutputValidationError):
                    if retry_count >= agent.max_retries:
                        raise
                    retry_count += 1
                    request = request.model_copy(
                        update={
                            "messages": [
                                *request.messages,
                                {
                                    "role": "system",
                                    "content": "Return only one JSON object that strictly matches the requested output schema.",
                                },
                            ]
                        }
                    )
        except AgentError as exc:
            error = exc
        except Exception as exc:
            error = AgentError("unexpected agent execution failure")
            error.__cause__ = exc

        result = self._result(
            execution_id,
            agent.name if agent else agent_name,
            agent.model if agent else "unknown",
            agent.prompt_version if agent else "unknown",
            False,
            None,
            started,
            retry_count,
            error.error_type,
            input_tokens if has_input_tokens else None,
            output_tokens if has_output_tokens else None,
        )
        self._emit(result, execution_context)
        return result

    @staticmethod
    def _validate_input(
        agent: BaseAgent, payload: BaseModel | dict[str, Any]
    ) -> BaseModel:
        if isinstance(payload, agent.input_schema):
            return payload
        raw = (
            payload.model_dump(mode="python")
            if isinstance(payload, BaseModel)
            else payload
        )
        try:
            return agent.input_schema.model_validate(raw)
        except ValidationError as exc:
            raise AgentInputValidationError("agent input validation failed") from exc

    async def _complete(
        self, request: ProviderRequest, timeout_seconds: float
    ) -> ProviderResponse:
        try:
            async with asyncio.timeout(timeout_seconds):
                return await self._provider.complete(
                    request, timeout_seconds=timeout_seconds
                )
        except TimeoutError as exc:
            raise AgentTimeoutError("agent execution timed out") from exc

    async def _complete_after_tools(
        self,
        request: ProviderRequest,
        response: ProviderResponse,
        agent: BaseAgent,
        context: AgentExecutionContext,
    ) -> ProviderResponse:
        provider_calls: list[dict[str, Any]] = []
        tool_messages: list[dict[str, Any]] = []
        for call in response.tool_calls:
            result = await self._tools.invoke(call, agent.allowed_tools, context)
            arguments = (
                call.arguments
                if isinstance(call.arguments, str)
                else json.dumps(call.arguments)
            )
            provider_calls.append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": arguments},
                }
            )
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": self._encode_tool_result(result),
                }
            )
        follow_up = request.model_copy(
            update={
                "messages": [
                    *request.messages,
                    {
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": provider_calls,
                    },
                    *tool_messages,
                ]
            }
        )
        completed = await self._complete(follow_up, agent.timeout_seconds)
        if completed.tool_calls:
            raise ToolExecutionError("multiple tool-call rounds are not supported")
        return completed

    @staticmethod
    def _validate_output(agent: BaseAgent, response: ProviderResponse) -> BaseModel:
        if response.content is None:
            raise InvalidStructuredOutputError("provider returned no structured output")
        try:
            value = (
                json.loads(response.content)
                if isinstance(response.content, str)
                else response.content
            )
        except json.JSONDecodeError as exc:
            raise InvalidStructuredOutputError(
                "provider returned malformed JSON"
            ) from exc
        if not isinstance(value, dict):
            raise InvalidStructuredOutputError("provider output must be a JSON object")
        try:
            return agent.output_schema.model_validate(value)
        except ValidationError as exc:
            raise OutputValidationError(
                "provider output failed schema validation"
            ) from exc

    @staticmethod
    def _encode_tool_result(result: Any) -> str:
        if isinstance(result, BaseModel):
            result = result.model_dump(mode="json")
        try:
            return json.dumps(result)
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError(
                "tool returned a non-JSON-serializable result"
            ) from exc

    @staticmethod
    def _add_tokens(total: int, present: bool, value: int | None) -> tuple[int, bool]:
        return (total + value, True) if value is not None else (total, present)

    @staticmethod
    def _result(
        execution_id: UUID,
        agent_name: str,
        model: str,
        prompt_version: str,
        success: bool,
        output: dict[str, Any] | None,
        started: float,
        retry_count: int,
        error_type: AgentErrorType | None,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> AgentExecutionResult:
        return AgentExecutionResult(
            execution_id=execution_id,
            agent_name=agent_name,
            model=model,
            prompt_version=prompt_version,
            success=success,
            output=output,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
            retry_count=retry_count,
            error_type=error_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def _emit(
        self, result: AgentExecutionResult, context: AgentExecutionContext
    ) -> None:
        self._logger.emit(
            {
                "execution_id": result.execution_id,
                "agent_name": result.agent_name,
                "session_id": context.session_id,
                "user_id": context.user_id,
                "model": result.model,
                "prompt_version": result.prompt_version,
                "latency_ms": result.latency_ms,
                "retry_count": result.retry_count,
                "success": result.success,
                "error_type": result.error_type,
            }
        )

