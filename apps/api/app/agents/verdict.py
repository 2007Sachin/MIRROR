from .base import BaseAgent
from ..verdict_models import VerdictLanguageInput, VerdictLanguageOutput
VERDICT_AGENT_NAME="verdict"
def create_verdict_agent(model: str) -> BaseAgent[VerdictLanguageInput,VerdictLanguageOutput]:
 return BaseAgent(name=VERDICT_AGENT_NAME,description="Writes constrained assessment language",model=model,temperature=.1,input_schema=VerdictLanguageInput,output_schema=VerdictLanguageOutput,prompt_version="v1",allowed_tools=(),timeout_seconds=30,max_retries=2)

