from __future__ import annotations

import logging

from .agents import AgentRunner
from .agents.definitions import AgentExecutionContext
from .agents.verdict import VERDICT_AGENT_NAME
from .copy_guard import find_banned
from .verdict_models import VerdictLanguageInput, VerdictLanguageOutput

logger = logging.getLogger("mirror.verdict")

# Used only when generated text still contains a banned word after one more attempt.
SAFE_SUMMARY = (
    "Thank you for the time you gave this conversation. Your reflection shows what came through "
    "in this session, and where a little more detail could help next time."
)
SAFE_ROOT_CAUSE = (
    "One area stood out as a good place to start. A little more detail about what you did, "
    "and how you knew it worked, would help your story land."
)
SAFE_CONFIDENCE_NOTE = "This reflection comes from one conversation, so it can only show so much."


class VerdictLanguageService:
 def __init__(self, runner:AgentRunner): self._runner=runner

 async def _generate(self, context:VerdictLanguageInput, *, session_id, user_id)->VerdictLanguageOutput|None:
  result=await self._runner.run(VERDICT_AGENT_NAME,context,context=AgentExecutionContext(session_id=session_id,user_id=user_id))
  if not result.success or result.output is None:return None
  return VerdictLanguageOutput.model_validate(result.output)

 async def write(self, context:VerdictLanguageInput, *, session_id, user_id)->VerdictLanguageOutput|None:
  """Generate reflection text, regenerate once if a banned word slips in, then fall back per field."""
  language=await self._generate(context,session_id=session_id,user_id=user_id)
  if language is None:return None
  if not self._banned(language):return language
  logger.warning("verdict_language_banned_words session_id=%s attempt=1 fields=%s",session_id,self._banned(language))
  retry=await self._generate(context,session_id=session_id,user_id=user_id)
  if retry is not None:language=retry
  banned=self._banned(language)
  if not banned:return language
  logger.warning("verdict_language_fallback session_id=%s fields=%s",session_id,banned)
  return VerdictLanguageOutput(
   verdict_summary=SAFE_SUMMARY if "verdict_summary" in banned else language.verdict_summary,
   root_cause_explanation=SAFE_ROOT_CAUSE if "root_cause_explanation" in banned else language.root_cause_explanation,
   confidence_note=SAFE_CONFIDENCE_NOTE if "confidence_note" in banned else language.confidence_note,
  )

 @staticmethod
 def _banned(language:VerdictLanguageOutput)->list[str]:
  return [name for name in ("verdict_summary","root_cause_explanation","confidence_note") if find_banned(getattr(language,name))]
