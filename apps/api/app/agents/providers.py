from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx

from .definitions import ProviderRequest, ProviderResponse, ToolCall
from .errors import AgentTimeoutError, ProviderFailureError

logger = logging.getLogger("mirror.agents.provider")


def _strict_json_schema(value: Any) -> Any:
    """Adapt Pydantic schemas to Groq's strict structured-output subset."""
    if isinstance(value, list):
        return [_strict_json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    result = {
        key: _strict_json_schema(item)
        for key, item in value.items()
        if key != "default"
    }
    properties = result.get("properties")
    if isinstance(properties, dict):
        result["required"] = list(properties)
        result["additionalProperties"] = False
    return result


class AgentProvider(Protocol):
    async def complete(
        self, request: ProviderRequest, *, timeout_seconds: float
    ) -> ProviderResponse: ...


class GroqProvider:
    """Small OpenAI-compatible Groq transport with no application responsibilities."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.groq.com/openai/v1",
        client: httpx.AsyncClient | None = None,
        max_rate_limit_retries: int = 3,
        max_rate_limit_wait_seconds: float = 30.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._max_rate_limit_retries = max_rate_limit_retries
        self._max_rate_limit_wait_seconds = max_rate_limit_wait_seconds
        self._sleep = sleep

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        """Groq reports the exact wait for a token-bucket refill; honour it."""
        header = response.headers.get("retry-after")
        if header:
            try:
                return max(0.0, float(header))
            except ValueError:
                return None
        return None

    async def complete(
        self, request: ProviderRequest, *, timeout_seconds: float
    ) -> ProviderResponse:
        if not self._api_key:
            raise ProviderFailureError("Groq is not configured")

        body: dict[str, Any] = {
            "model": request.model,
            "temperature": request.temperature,
            "messages": request.messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.output_schema_name,
                    "strict": True,
                    "schema": _strict_json_schema(request.output_json_schema),
                },
            },
        }
        if request.tools:
            body["tools"] = request.tools

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            waited = 0.0
            for attempt in range(self._max_rate_limit_retries + 1):
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                    timeout=timeout_seconds,
                )
                if response.status_code != 429 or attempt == self._max_rate_limit_retries:
                    break
                # A token-per-minute bucket refills on a known schedule, so the
                # request is worth repeating once the provider says it may be.
                delay = self._retry_after_seconds(response) or 1.0
                if waited + delay > self._max_rate_limit_wait_seconds:
                    break
                logger.warning(
                    "Groq rate limited model %s; retrying in %.1fs (attempt %d)",
                    request.model,
                    delay,
                    attempt + 1,
                )
                await self._sleep(delay)
                waited += delay
            if response.status_code == 400:
                error_payload = response.json().get("error", {})
                failed_generation = error_payload.get("failed_generation")
                if (
                    error_payload.get("code") == "json_validate_failed"
                    and isinstance(failed_generation, (str, dict))
                ):
                    # Groq can reject an otherwise useful generation when an
                    # optional Pydantic field is absent. Treat it as untrusted
                    # provider output; AgentRunner still performs full parsing
                    # and Pydantic validation before application code sees it.
                    return ProviderResponse(content=failed_generation)
            response.raise_for_status()
            payload = response.json()
            message = payload["choices"][0]["message"]
            tool_calls = tuple(
                ToolCall(
                    id=call["id"],
                    name=call["function"]["name"],
                    arguments=call["function"]["arguments"],
                )
                for call in message.get("tool_calls", [])
            )
            usage = payload.get("usage", {})
            return ProviderResponse(
                content=message.get("content"),
                tool_calls=tool_calls,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
        except httpx.TimeoutException as exc:
            raise AgentTimeoutError("provider request timed out") from exc
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            # Without this the provider's own explanation is lost and every
            # failure reaches operators as an opaque "provider_failure".
            detail = ""
            if isinstance(exc, httpx.HTTPStatusError):
                detail = f" status={exc.response.status_code} body={exc.response.text[:500]}"
            logger.warning(
                "Groq request failed for model %s (%s): %s%s",
                request.model,
                request.output_schema_name,
                type(exc).__name__,
                detail,
            )
            raise ProviderFailureError("provider request failed") from exc
        finally:
            if owns_client:
                await client.aclose()

