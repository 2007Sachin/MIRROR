from .base import BaseAgent
from ..interviewer_models import InterviewerContext, InterviewerDecision


INTERVIEWER_AGENT_NAME = "interviewer"
INTERVIEWER_PROMPT_VERSION = "v1"


def create_interviewer_agent(
    model: str,
) -> BaseAgent[InterviewerContext, InterviewerDecision]:
    return BaseAgent(
        name=INTERVIEWER_AGENT_NAME,
        description="Chooses the next concise text interview action",
        model=model,
        temperature=0.2,
        input_schema=InterviewerContext,
        output_schema=InterviewerDecision,
        prompt_version=INTERVIEWER_PROMPT_VERSION,
        allowed_tools=(),
        timeout_seconds=30,
        max_retries=2,
    )

