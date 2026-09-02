from __future__ import annotations
from .agents import AgentRunner
from .agents.definitions import AgentExecutionContext
from .agents.verdict import VERDICT_AGENT_NAME
from .verdict_models import VerdictLanguageInput, VerdictLanguageOutput

class VerdictLanguageService:
 def __init__(self, runner:AgentRunner): self._runner=runner
 async def write(self, context:VerdictLanguageInput, *, session_id, user_id)->VerdictLanguageOutput|None:
  result=await self._runner.run(VERDICT_AGENT_NAME,context,context=AgentExecutionContext(session_id=session_id,user_id=user_id))
  if not result.success or result.output is None:return None
  return VerdictLanguageOutput.model_validate(result.output)

