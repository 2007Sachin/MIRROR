from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel


InputModel = TypeVar("InputModel", bound=BaseModel)
OutputModel = TypeVar("OutputModel", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class BaseAgent(Generic[InputModel, OutputModel]):
    name: str
    description: str
    model: str
    temperature: float
    input_schema: type[InputModel]
    output_schema: type[OutputModel]
    prompt_version: str
    allowed_tools: tuple[str, ...] = ()
    timeout_seconds: float = 30.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        if (
            not self.name
            or not self.name.replace("_", "").isalnum()
            or self.name.lower() != self.name
        ):
            raise ValueError(
                "agent name must use lowercase letters, digits, and underscores"
            )
        if not self.model.strip():
            raise ValueError("agent model is required")
        if not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if len(set(self.allowed_tools)) != len(self.allowed_tools):
            raise ValueError("allowed_tools must not contain duplicates")

