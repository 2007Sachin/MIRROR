from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx

from .definitions import ProviderRequest, ProviderResponse, ToolCall
from .errors import AgentTimeoutError, ProviderFailureError

logger = logging.getLogger("mirror.agents.provider")


def _inline_nullable(value: Any, defs: dict[str, Any]) -> Any:
    """Strict structured output rejects `anyOf: [X, null]` where X is a $ref. Fold nullable fields into
    `type: [.., "null"]` (or an enum that includes null) so Optional fields are accepted."""
    if isinstance(value, list):
        return [_inline_nullable(item, defs) for item in value]
    if not isinstance(value, dict):
        return value
    value = {k: _inline_nullable(v, defs) for k, v in value.items() if k != "$defs"}
    if "$ref" in value and isinstance(value["$ref"], str):
        target = defs.get(value["$ref"].rsplit("/", 1)[-1])
        if isinstance(target, dict):
            return {**_inline_nullable(target, defs), **{k: v for k, v in value.items() if k != "$ref"}}
    options = value.get("anyOf")
    if isinstance(options, list) and len(options) == 2:
        nulls = [o for o in options if isinstance(o, dict) and o.get("type") == "null"]
        rest = [o for o in options if o not in nulls]
        if len(nulls) == 1 and len(rest) == 1 and isinstance(rest[0], dict):
            base = dict(rest[0])
            if "enum" in base:
                base["enum"] = [*base["enum"], None]
            kind = base.get("type")
            if isinstance(kind, str):
                base["type"] = [kind, "null"]
            merged = {k: v for k, v in value.items() if k != "anyOf"}
            return {**base, **merged}
    return value


def _strict_json_schema(value: Any) -> Any:
    """Adapt Pydantic schemas to the strict structured-output subset."""
    if isinstance(value, dict) and "$defs" in value:
        value = _inline_nullable(value, value["$defs"])
    elif isinstance(value, dict):
        value = _inline_nullable(value, {})
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


class ChatCompletionsProvider:
    """Small OpenAI-style chat transport (Sarvam) with no application responsibilities."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.sarvam.ai/v1",
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
        """Providers report the exact wait for a rate-limit refill; honour it."""
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
            raise ProviderFailureError("The language model is not configured")

        body: dict[str, Any] = {
            "model": request.model,
            "temperature": request.temperature,
            "messages": request.messages,
            "max_tokens": 8192,
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
                    "Language model rate limited (%s); retrying in %.1fs (attempt %d)",
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
                    # A provider can reject an otherwise useful generation when an
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
                for call in (message.get("tool_calls") or [])
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
                "Language model request failed for %s (%s): %s%s",
                request.model,
                request.output_schema_name,
                type(exc).__name__,
                detail,
            )
            raise ProviderFailureError("provider request failed") from exc
        finally:
            if owns_client:
                await client.aclose()
