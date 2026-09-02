from .base import BaseAgent
from ..specialist_assessor_models import (
    AssessorType, SpecialistAssessmentContext, SpecialistAssessmentOutput,
)


def create_specialist_assessor(
    assessor_type: AssessorType, model: str
) -> BaseAgent[SpecialistAssessmentContext, SpecialistAssessmentOutput]:
    return BaseAgent(
        name=f"assessor_{assessor_type.value.lower()}",
        description=f"Narrow {assessor_type.value.lower()} interview assessor",
        model=model, temperature=0.0,
        input_schema=SpecialistAssessmentContext,
        output_schema=SpecialistAssessmentOutput,
        prompt_version="v1", allowed_tools=(), timeout_seconds=35, max_retries=2,
    )

