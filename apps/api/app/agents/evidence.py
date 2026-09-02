from .base import BaseAgent
from ..evidence_models import EvidenceAssessment, EvidenceContext


EVIDENCE_AGENT_NAME = "evidence"
EVIDENCE_PROMPT_VERSION = "v1"


def create_evidence_agent(model: str) -> BaseAgent[EvidenceContext, EvidenceAssessment]:
    return BaseAgent(
        name=EVIDENCE_AGENT_NAME,
        description="Classifies traceable evidence for one candidate claim",
        model=model,
        temperature=0.0,
        input_schema=EvidenceContext,
        output_schema=EvidenceAssessment,
        prompt_version=EVIDENCE_PROMPT_VERSION,
        allowed_tools=(),
        timeout_seconds=30,
        max_retries=2,
    )

