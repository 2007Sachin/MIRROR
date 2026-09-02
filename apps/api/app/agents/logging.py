from __future__ import annotations

import json
import logging
from typing import Any, Protocol


class AgentExecutionLogger(Protocol):
    def emit(self, fields: dict[str, Any]) -> None: ...


class StructuredAgentLogger:
    """Emits execution metadata only; prompt inputs and outputs are excluded."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("mirror.agents")

    def emit(self, fields: dict[str, Any]) -> None:
        serializable = {
            key: str(value) if value is not None else None
            for key, value in fields.items()
        }
        self._logger.info(
            json.dumps(serializable, separators=(",", ":"), sort_keys=True)
        )

