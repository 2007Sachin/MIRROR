from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .base import BaseAgent
from .errors import DuplicateAgentError, UnknownAgentError


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if agent.name in self._agents:
            raise DuplicateAgentError(f"agent already registered: {agent.name}")
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise UnknownAgentError(f"unknown agent: {name}") from exc

    def snapshot(self) -> Mapping[str, BaseAgent]:
        return MappingProxyType(self._agents.copy())

