from .base import BaseAgent
from ..assessment_adjudication_models import AdjudicationContext, AdjudicationDecision


ADJUDICATOR_AGENT_NAME = "assessment_adjudicator"


def create_adjudicator_agent(model: str) -> BaseAgent[AdjudicationContext, AdjudicationDecision]:
    return BaseAgent(name=ADJUDICATOR_AGENT_NAME, description="Resolves one material specialist disagreement",
        model=model, temperature=0.0, input_schema=AdjudicationContext,
        output_schema=AdjudicationDecision, prompt_version="v1", allowed_tools=(),
        timeout_seconds=30, max_retries=2)

