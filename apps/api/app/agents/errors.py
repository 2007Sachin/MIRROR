from __future__ import annotations

from .definitions import AgentErrorType


class AgentError(Exception):
    error_type = AgentErrorType.INTERNAL_FAILURE


class UnknownAgentError(AgentError):
    error_type = AgentErrorType.UNKNOWN_AGENT


class DuplicateAgentError(AgentError):
    error_type = AgentErrorType.INTERNAL_FAILURE


class DuplicateToolError(AgentError):
    error_type = AgentErrorType.TOOL_FAILURE


class AgentInputValidationError(AgentError):
    error_type = AgentErrorType.INPUT_VALIDATION


class ProviderFailureError(AgentError):
    error_type = AgentErrorType.PROVIDER_FAILURE


class AgentTimeoutError(AgentError):
    error_type = AgentErrorType.TIMEOUT


class InvalidStructuredOutputError(AgentError):
    error_type = AgentErrorType.INVALID_STRUCTURED_OUTPUT


class OutputValidationError(AgentError):
    error_type = AgentErrorType.VALIDATION_FAILURE


class ToolExecutionError(AgentError):
    error_type = AgentErrorType.TOOL_FAILURE


class ToolPermissionError(AgentError):
    error_type = AgentErrorType.TOOL_PERMISSION


class PromptNotFoundError(AgentError):
    error_type = AgentErrorType.INTERNAL_FAILURE

