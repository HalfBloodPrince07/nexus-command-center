"""Shared retry, fallback, and degradation helpers for Nexus OS agents."""
from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class AgentError(Exception):
    """Base class for recoverable agent-layer failures."""


class LLMUnavailable(AgentError):
    """The local LLM endpoint is unavailable or returned an unusable response."""


class EmbeddingUnavailable(AgentError):
    """The embedding model or vector search backend is unavailable."""


class ScrapeBlocked(AgentError):
    """A source blocked scraping via status code, paywall, or anti-bot controls."""


class RateLimited(AgentError):
    """An upstream service is rate-limiting requests."""


class InvalidInput(AgentError):
    """Input cannot be safely processed by the target agent."""


def degraded_event(agent: str, reason: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    """Return a standard degraded-mode event for WebSocket/UI consumers."""
    return {
        "type": "degraded",
        "agent": agent,
        "reason": reason,
        "detail": detail,
        **extra,
    }


async def emit_degraded(
    event_yielder: Callable[[dict[str, Any]], Any] | Any,
    agent: str,
    reason: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Uniformly emit a `degraded` event through any sink (callback, queue, ws manager).

    Accepts:
      - an awaitable callable (async fn(dict)),
      - a sync callable (e.g. list.append, queue.put_nowait),
      - any object exposing `.put` / `.send_json` / `.send` methods,
      - or `None` (returns the event without emitting).

    The caller may also use `degraded_event(...)` directly and `yield` it from
    an async generator — that is the preferred pattern inside agents. This
    helper exists for non-generator code paths that need a single uniform call.
    """
    detail = ""
    extras: dict[str, Any] = {}
    if context:
        detail = str(context.get("detail", "")) or ""
        extras = {k: v for k, v in context.items() if k != "detail"}
    event = degraded_event(agent, reason, detail, **extras)

    logger.warning(
        "Emitting degraded event",
        extra={"agent": agent, "reason": reason, "context": context or {}},
    )

    if event_yielder is None:
        return event

    try:
        if inspect.iscoroutinefunction(event_yielder):
            await event_yielder(event)
        elif callable(event_yielder):
            result = event_yielder(event)
            if inspect.isawaitable(result):
                await result
        elif hasattr(event_yielder, "send_json"):
            result = event_yielder.send_json(event)
            if inspect.isawaitable(result):
                await result
        elif hasattr(event_yielder, "put"):
            result = event_yielder.put(event)
            if inspect.isawaitable(result):
                await result
        elif hasattr(event_yielder, "send"):
            result = event_yielder.send(event)
            if inspect.isawaitable(result):
                await result
    except Exception as exc:  # noqa: BLE001 — emission must never crash callers
        logger.warning(
            "Failed to deliver degraded event to sink",
            extra={"agent": agent, "reason": reason, "error": str(exc)},
        )

    return event


def _delay(attempt: int, backoff: str, base_delay: float, max_delay: float) -> float:
    if backoff == "exponential":
        return min(base_delay * (2 ** max(attempt - 1, 0)), max_delay)
    return min(base_delay, max_delay)


def _log_retry(fn_name: str, exc: BaseException, attempt: int, max_attempts: int, delay: float) -> None:
    logger.warning(
        "Retrying resilient operation",
        extra={
            "operation": fn_name,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "delay_seconds": delay,
            "error_type": type(exc).__name__,
            "error": str(exc),
        },
    )


def with_retry(
    max_attempts: int = 3,
    backoff: str = "exponential",
    retry_on: tuple[type[BaseException], ...] = (httpx.TimeoutException, httpx.HTTPStatusError),
    base_delay: float = 0.2,
    max_delay: float = 60.0,
) -> Callable[[F], F]:
    """Retry async/sync callables and async generators on selected exceptions."""

    def decorator(fn: F) -> F:
        if inspect.isasyncgenfunction(fn):

            @functools.wraps(fn)
            async def async_gen_wrapper(*args: Any, **kwargs: Any):
                for attempt in range(1, max_attempts + 1):
                    try:
                        async for item in fn(*args, **kwargs):
                            yield item
                        return
                    except retry_on as exc:
                        if attempt >= max_attempts:
                            raise
                        delay = _delay(attempt, backoff, base_delay, max_delay)
                        _log_retry(fn.__name__, exc, attempt, max_attempts, delay)
                        await asyncio.sleep(delay)

            return async_gen_wrapper  # type: ignore[return-value]

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any):
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await fn(*args, **kwargs)
                    except retry_on as exc:
                        if attempt >= max_attempts:
                            raise
                        delay = _delay(attempt, backoff, base_delay, max_delay)
                        _log_retry(fn.__name__, exc, attempt, max_attempts, delay)
                        await asyncio.sleep(delay)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any):
            import time

            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on as exc:
                    if attempt >= max_attempts:
                        raise
                    delay = _delay(attempt, backoff, base_delay, max_delay)
                    _log_retry(fn.__name__, exc, attempt, max_attempts, delay)
                    time.sleep(delay)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def with_fallback(fallback_fn: Callable[..., Any]) -> Callable[[F], F]:
    """Run fallback_fn if the decorated callable fails after its retries."""

    def decorator(fn: F) -> F:
        if inspect.isasyncgenfunction(fn):

            @functools.wraps(fn)
            async def async_gen_wrapper(*args: Any, **kwargs: Any):
                try:
                    async for item in fn(*args, **kwargs):
                        yield item
                except Exception as exc:
                    logger.warning(
                        "Using fallback for async generator",
                        extra={"operation": fn.__name__, "error_type": type(exc).__name__, "error": str(exc)},
                    )
                    result = fallback_fn(*args, exc=exc, **kwargs)
                    if inspect.isawaitable(result):
                        result = await result
                    if inspect.isasyncgen(result):
                        async for item in result:
                            yield item
                    elif inspect.isgenerator(result):
                        for item in result:
                            yield item
                    elif result is not None:
                        yield result

            return async_gen_wrapper  # type: ignore[return-value]

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    logger.warning(
                        "Using fallback for async operation",
                        extra={"operation": fn.__name__, "error_type": type(exc).__name__, "error": str(exc)},
                    )
                    result = fallback_fn(*args, exc=exc, **kwargs)
                    if inspect.isawaitable(result):
                        return await result
                    return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                logger.warning(
                    "Using fallback for sync operation",
                    extra={"operation": fn.__name__, "error_type": type(exc).__name__, "error": str(exc)},
                )
                return fallback_fn(*args, exc=exc, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def is_chromadb_locked(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "locked" in text or "database is locked" in text or "sqlite_busy" in text
