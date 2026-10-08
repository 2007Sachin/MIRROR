from .base import BaseAgent
from ..specialist_assessor_models import (
    AssessorType, SpecialistAssessmentContext, SpecialistAssessmentOutput,
)


def create_specialist_assessor(
    assessor_type: AssessorType,
    model: str,
    *,
    prompt_version: str = "v1",
) -> BaseAgent[SpecialistAssessmentContext, SpecialistAssessmentOutput]:
    return BaseAgent(
        name=f"assessor_{assessor_type.value.lower()}",
        description=f"Narrow {assessor_type.value.lower()} interview assessor",
        model=model, temperature=0.0,
        input_schema=SpecialistAssessmentContext,
        output_schema=SpecialistAssessmentOutput,
        prompt_version=prompt_version, allowed_tools=(), timeout_seconds=35, max_retries=2,
    )

