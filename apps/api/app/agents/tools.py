from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ValidationError

from .definitions import AgentExecutionContext, ToolCall
from .errors import DuplicateToolError, ToolExecutionError, ToolPermissionError


ToolHandler = Callable[[BaseModel, AgentExecutionContext], Any | Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: type[BaseModel]
    handler: ToolHandler

    def provider_spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema.model_json_schema(),
            },
        }


class ToolRegistry:
    """Explicit allow-list boundary between model requests and application tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise DuplicateToolError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def specs_for(self, allowed_tools: tuple[str, ...]) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for name in allowed_tools:
            tool = self._tools.get(name)
            if tool is None:
                raise ToolExecutionError(f"allowed tool is not registered: {name}")
            specs.append(tool.provider_spec())
        return specs

    async def invoke(
        self,
        call: ToolCall,
        allowed_tools: tuple[str, ...],
        context: AgentExecutionContext,
    ) -> Any:
        if call.name not in allowed_tools:
            raise ToolPermissionError(
                f"agent is not permitted to call tool: {call.name}"
            )

        tool = self._tools.get(call.name)
        if tool is None:
            raise ToolExecutionError(f"tool is not registered: {call.name}")

        try:
            arguments = (
                json.loads(call.arguments)
                if isinstance(call.arguments, str)
                else call.arguments
            )
            validated = tool.input_schema.model_validate(arguments)
            result = tool.handler(validated, context)
            return await result if inspect.isawaitable(result) else result
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ToolExecutionError(
                f"invalid arguments for tool: {call.name}"
            ) from exc
        except (ToolExecutionError, ToolPermissionError):
            raise
        except Exception as exc:
            raise ToolExecutionError(f"tool execution failed: {call.name}") from exc

