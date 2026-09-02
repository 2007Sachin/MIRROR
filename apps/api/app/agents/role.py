from .base import BaseAgent
from ..role_models import RoleAgentInput, RoleAgentOutput


ROLE_AGENT_NAME = "role"
ROLE_PROMPT_VERSION = "v1"
ROLE_ANALYSIS_VERSION = "role-v1"


def create_role_agent(model: str) -> BaseAgent[RoleAgentInput, RoleAgentOutput]:
    return BaseAgent(
        name=ROLE_AGENT_NAME,
        description="Builds a source-grounded competency map for a target role",
        model=model,
        temperature=0,
        input_schema=RoleAgentInput,
        output_schema=RoleAgentOutput,
        prompt_version=ROLE_PROMPT_VERSION,
        allowed_tools=(),
        timeout_seconds=45,
        max_retries=2,
    )

