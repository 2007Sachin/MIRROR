from pydantic import BaseModel, ConfigDict, Field

from .base import BaseAgent


class FrameworkTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1_000)


class FrameworkTestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    normalized_text: str


def create_framework_test_agent(model: str) -> BaseAgent:
    """Builds a test-only agent; production registries must not include it."""
    return BaseAgent(
        name="framework_test",
        description="Internal structured-output framework test",
        model=model,
        temperature=0,
        input_schema=FrameworkTestInput,
        output_schema=FrameworkTestOutput,
        prompt_version="v1",
        timeout_seconds=1,
        max_retries=1,
    )

