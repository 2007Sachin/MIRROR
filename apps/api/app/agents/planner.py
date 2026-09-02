from .base import BaseAgent
from ..planner_models import InterviewPlannerInput, InterviewPlanDraft


PLANNER_AGENT_NAME = "planner"
PLANNER_PROMPT_VERSION = "v1"
PLANNING_VERSION = "planner-v1"


def create_planner_agent(
    model: str,
) -> BaseAgent[InterviewPlannerInput, InterviewPlanDraft]:
    return BaseAgent(
        name=PLANNER_AGENT_NAME,
        description="Builds evidence-gathering objectives for an interview",
        model=model,
        temperature=0,
        input_schema=InterviewPlannerInput,
        output_schema=InterviewPlanDraft,
        prompt_version=PLANNER_PROMPT_VERSION,
        allowed_tools=(),
        timeout_seconds=45,
        max_retries=2,
    )

