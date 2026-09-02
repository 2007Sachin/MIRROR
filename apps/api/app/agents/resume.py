from .base import BaseAgent
from ..resume_models import ResumeAgentInput, ResumeAgentOutput


RESUME_AGENT_NAME = "resume"
RESUME_PROMPT_VERSION = "v1"
RESUME_ANALYSIS_VERSION = "resume-v1"


def create_resume_agent(model: str) -> BaseAgent[ResumeAgentInput, ResumeAgentOutput]:
    return BaseAgent(
        name=RESUME_AGENT_NAME,
        description="Extracts neutral, source-grounded claims from resume text",
        model=model,
        temperature=0,
        input_schema=ResumeAgentInput,
        output_schema=ResumeAgentOutput,
        prompt_version=RESUME_PROMPT_VERSION,
        allowed_tools=(),
        timeout_seconds=45,
        max_retries=2,
    )

