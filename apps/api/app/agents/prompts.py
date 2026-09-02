from __future__ import annotations

import re
from pathlib import Path

from .errors import PromptNotFoundError


_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_PATTERN = re.compile(r"^v[1-9][0-9]*$")


class PromptLoader:
    """Loads immutable, repository-versioned prompt assets."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or Path(__file__).parents[1] / "prompts").resolve()

    def load(self, agent_name: str, version: str) -> str:
        if not _NAME_PATTERN.fullmatch(agent_name) or not _VERSION_PATTERN.fullmatch(
            version
        ):
            raise PromptNotFoundError("invalid prompt identifier")

        path = (self._root / agent_name / f"{version}.md").resolve()
        if self._root not in path.parents or not path.is_file():
            raise PromptNotFoundError(
                f"prompt not found for agent '{agent_name}' at version '{version}'"
            )

        prompt = path.read_text(encoding="utf-8").strip()
        if not prompt:
            raise PromptNotFoundError(
                f"prompt is empty for agent '{agent_name}' at version '{version}'"
            )
        return prompt

