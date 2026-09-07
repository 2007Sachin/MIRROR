from __future__ import annotations

from typing import Any, Protocol

import httpx

from .definitions import ProviderRequest, ProviderResponse, ToolCall
from .errors import AgentTimeoutError, ProviderFailureError


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
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client

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
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
                timeout=timeout_seconds,
            )
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
            raise ProviderFailureError("provider request failed") from exc
        finally:
            if owns_client:
                await client.aclose()

