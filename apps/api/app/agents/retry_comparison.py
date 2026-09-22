from .base import BaseAgent
from ..attempt_models import RetryComparisonInput, RetryComparisonOutput

RETRY_COMPARISON_AGENT_NAME = "retry_comparison"
RETRY_COMPARISON_PROMPT_VERSION = "v1"


def create_retry_comparison_agent(model: str) -> BaseAgent[RetryComparisonInput, RetryComparisonOutput]:
    """Compares two answers to one question by what each contains. One call per explicit retry."""
    return BaseAgent(
        name=RETRY_COMPARISON_AGENT_NAME,
        description="Reports which answer aspects are present in a first and a latest answer",
        model=model,
        temperature=0.0,
        input_schema=RetryComparisonInput,
        output_schema=RetryComparisonOutput,
        prompt_version=RETRY_COMPARISON_PROMPT_VERSION,
        allowed_tools=(),
        timeout_seconds=20,
        max_retries=1,
    )
