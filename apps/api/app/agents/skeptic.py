from .base import BaseAgent
from ..skeptic_models import SkepticAnalysis, SkepticContext


SKEPTIC_AGENT_NAME = "skeptic"
SKEPTIC_PROMPT_VERSION = "v1"


def create_skeptic_agent(model: str) -> BaseAgent[SkepticContext, SkepticAnalysis]:
    return BaseAgent(
        name=SKEPTIC_AGENT_NAME,
        description="Silently proposes claim observations and future probes",
        model=model,
        temperature=0.1,
        input_schema=SkepticContext,
        output_schema=SkepticAnalysis,
        prompt_version=SKEPTIC_PROMPT_VERSION,
        allowed_tools=(),
        timeout_seconds=30,
        max_retries=2,
    )

