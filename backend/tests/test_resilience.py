from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import importlib

import httpx
import pytest

from backend.core.resilience import (
    EmbeddingUnavailable,
    degraded_event,
    emit_degraded,
    with_retry,
)


async def test_emit_degraded_with_async_callable() -> None:
    received: list[dict] = []

    async def sink(event: dict) -> None:
        received.append(event)

    event = await emit_degraded(sink, "Echo", "embedding_unavailable", {"detail": "down"})

    assert event["type"] == "degraded"
    assert received == [event]
    assert received[0]["agent"] == "Echo"
    assert received[0]["detail"] == "down"


async def test_emit_degraded_with_sync_callable_and_extras() -> None:
    received: list[dict] = []
    event = await emit_degraded(
        received.append,
        "Fetch",
        "scrape_blocked",
        {"detail": "403", "url": "https://x"},
    )
    assert received[0]["url"] == "https://x"
    assert received[0]["detail"] == "403"
    assert event["reason"] == "scrape_blocked"


async def test_emit_degraded_swallow_sink_errors() -> None:
    def boom(_event: dict) -> None:
        raise RuntimeError("sink died")

    # Must not raise — callers cannot afford emission failures.
    event = await emit_degraded(boom, "Nexus", "llm_unavailable", None)
    assert event["type"] == "degraded"


def test_degraded_event_shape() -> None:
    event = degraded_event("Echo", "reason", "detail", url="u")
    assert event == {
        "type": "degraded",
        "agent": "Echo",
        "reason": "reason",
        "detail": "detail",
        "url": "u",
    }


async def test_with_retry_retries_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("backend.core.resilience.asyncio.sleep", no_sleep)

    @with_retry(max_attempts=3, retry_on=(httpx.TimeoutException,), base_delay=0.01)
    async def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise httpx.TimeoutException("timeout")
        return "ok"

    assert await flaky() == "ok"
    assert calls["count"] == 3


async def test_supervisor_lm_studio_down_returns_fixed_message(monkeypatch: pytest.MonkeyPatch) -> None:
    supervisor_module = importlib.import_module("backend.app.agents.supervisor")
    from backend.app.agents.supervisor import Supervisor

    async def failing_stream(*args, **kwargs):
        raise httpx.ConnectError("connection refused")
        yield ""

    monkeypatch.setattr(supervisor_module, "stream_chat_completion", failing_stream)
    sup = Supervisor()
    monkeypatch.setattr(sup, "_get_mood_context", AsyncMock(return_value={"mood": "neutral", "confidence": 1.0}))

    events = [item async for item in sup.stream_response("hello", "session-1")]

    assert any(isinstance(item, dict) and item["type"] == "degraded" for item in events)
    assert "I can't reach the local model right now" in "".join(str(item) for item in events if not isinstance(item, dict))


async def test_rag_embedding_unavailable_falls_back_to_bm25(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.agents.rag_retriever import RAGRetriever

    retriever = RAGRetriever()

    async def vector_failure(*args, **kwargs):
        raise EmbeddingUnavailable("embedding model missing")

    async def answer(*args, **kwargs):
        yield "bm25 answer"

    monkeypatch.setattr(retriever, "_vector_search", vector_failure)
    monkeypatch.setattr(
        retriever,
        "_bm25_search",
        lambda *args, **kwargs: [{"id": "doc-1", "text": "keyword hit", "metadata": {}, "score": 1.0}],
    )
    monkeypatch.setattr(retriever, "_rerank", AsyncMock(return_value=[{"id": "doc-1", "text": "keyword hit", "metadata": {}}]))
    monkeypatch.setattr(retriever, "stream_answer", answer)

    events = [item async for item in retriever.search("keyword", n_results=1)]

    assert events[0]["type"] == "degraded"
    assert events[0]["reason"] == "embedding_unavailable"
    assert events[-1] == "bm25 answer"


async def test_duckduckgo_rate_limit_emits_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.agents import web_scout
    from backend.app.agents.web_scout import WebSearchAgent

    class RateLimitedDDGS:
        def text(self, *args, **kwargs):
            raise RuntimeError("429 rate limit")

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setitem(__import__("sys").modules, "duckduckgo_search", MagicMock(DDGS=RateLimitedDDGS))
    monkeypatch.setattr(web_scout.asyncio, "sleep", no_sleep)

    events = [
        event
        async for event in WebSearchAgent().run(
            [{"id": "q1", "query": "nexus", "expected_source_type": "web"}]
        )
    ]

    assert any(event.get("type") == "degraded" and event.get("reason") == "search_rate_limited" for event in events)


async def test_scraper_blocked_uses_archive_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.agents import scraper_agent as scraper_module
    from backend.app.agents.scraper_agent import HybridScraper

    request = httpx.Request("GET", "https://blocked.example")
    response = httpx.Response(403, request=request)

    async def blocked(*args, **kwargs):
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    words = " ".join(["archived"] * 200)

    async def archive(*args, **kwargs):
        return "<html></html>", words, False, None

    monkeypatch.setattr(scraper_module, "_scrape_trafilatura", blocked)
    monkeypatch.setattr(scraper_module, "_scrape_archive", archive)
    monkeypatch.setattr(scraper_module, "_save_files", lambda *args, **kwargs: ("raw.html", "clean.txt"))
    monkeypatch.setattr(scraper_module.db_module, "insert_scraped_source", AsyncMock())
    monkeypatch.setattr(scraper_module, "_ingest_to_chroma", AsyncMock(return_value=[]))

    result = await HybridScraper().scrape_one(
        {"url": "https://blocked.example", "domain": "blocked.example"},
        "slug",
        "session",
        httpx.AsyncClient(),
    )

    assert result["scrape_method"] == "archive.org"
    assert result["scrape_status"] == "success"


async def test_chromadb_locked_returns_degraded_via_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.agents.rag_retriever import RAGRetriever

    retriever = RAGRetriever()

    async def locked(*args, **kwargs):
        raise EmbeddingUnavailable("database is locked")

    async def answer(*args, **kwargs):
        yield "no context"

    monkeypatch.setattr(retriever, "_vector_search", locked)
    monkeypatch.setattr(retriever, "_bm25_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(retriever, "_rerank", AsyncMock(return_value=[]))
    monkeypatch.setattr(retriever, "stream_answer", answer)

    events = [item async for item in retriever.search("anything")]

    assert events[0]["type"] == "degraded"
    assert events[0]["reason"] == "embedding_unavailable"


async def test_disk_write_failure_emits_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.agents.report_builder import ReportBuilderAgent

    agent = ReportBuilderAgent()
    monkeypatch.setattr(agent, "save_to_disk", MagicMock(side_effect=OSError("No space left on device")))

    events = [
        event
        async for event in agent.save_and_index(
            "slug",
            "topic",
            "report",
            [],
        )
    ]

    assert any(event.get("type") == "degraded" and event.get("reason") == "disk_write_failed" for event in events)
