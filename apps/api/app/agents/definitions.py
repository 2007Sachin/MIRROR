from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentErrorType(StrEnum):
    UNKNOWN_AGENT = "unknown_agent"
    INPUT_VALIDATION = "input_validation"
    PROVIDER_FAILURE = "provider_failure"
    TIMEOUT = "timeout"
    INVALID_STRUCTURED_OUTPUT = "invalid_structured_output"
    VALIDATION_FAILURE = "validation_failure"
    TOOL_FAILURE = "tool_failure"
    TOOL_PERMISSION = "tool_permission"
    INTERNAL_FAILURE = "internal_failure"


class AgentExecutionContext(BaseModel):
    """Non-prompt execution identifiers used for authorization and safe logs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: UUID | None = None
    user_id: UUID | None = None


class ToolCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    arguments: dict[str, Any] | str


class ProviderRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    model: str
    temperature: float
    messages: list[dict[str, Any]]
    output_schema_name: str
    output_json_schema: dict[str, Any]
    tools: list[dict[str, Any]] = Field(default_factory=list)


class ProviderResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str | dict[str, Any] | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    input_tokens: int | None = None
    output_tokens: int | None = None


class AgentExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_id: UUID
    agent_name: str
    model: str
    prompt_version: str
    success: bool
    output: dict[str, Any] | None = None
    latency_ms: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    error_type: AgentErrorType | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)

