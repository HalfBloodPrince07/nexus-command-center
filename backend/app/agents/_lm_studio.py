from __future__ import annotations

import json
from typing import Any, AsyncGenerator

import httpx

from backend.config import settings
from backend.core.resilience import LLMUnavailable, with_retry


def _chat_url() -> str:
    return f"{settings.LM_STUDIO_BASE_URL.rstrip('/')}/chat/completions"


@with_retry(
    max_attempts=3,
    backoff="exponential",
    retry_on=(httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError),
    base_delay=0.2,
)
async def complete_chat(
    messages: list[dict[str, Any]],
    model: str,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
        "store": False,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.SUPERVISOR_TIMEOUT_SECONDS) as client:
            response = await client.post(_chat_url(), json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return ""
            message = choices[0].get("message") or {}
            return str(message.get("content") or "")
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError):
        raise
    except Exception as exc:
        raise LLMUnavailable(f"LM Studio response could not be processed: {exc}") from exc


@with_retry(
    max_attempts=3,
    backoff="exponential",
    retry_on=(httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError),
    base_delay=0.2,
)
async def stream_chat_completion(
    messages: list[dict[str, Any]],
    model: str,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "store": False,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {settings.LM_STUDIO_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.SUPERVISOR_TIMEOUT_SECONDS) as client:
            async with client.stream("POST", _chat_url(), json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue

                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break

                    try:
                        payload_data = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choices = payload_data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    token = delta.get("content")
                    if token:
                        yield str(token)
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError):
        raise
    except Exception as exc:
        raise LLMUnavailable(f"LM Studio stream could not be processed: {exc}") from exc

