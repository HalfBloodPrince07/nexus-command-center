from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from backend.mcp.server import create_app
from backend.mcp.tools import (
    AnalyzeImageOutput,
    JournalInsightsOutput,
    SaveMemoryOutput,
    SaveResearchReportOutput,
    SearchLocalFilesOutput,
    SearchWebOutput,
)


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    transport = httpx.ASGITransport(app=create_app(), client=("127.0.0.1", 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as ac:
        yield ac


async def test_tools_list_reflects_registered_tools(client: httpx.AsyncClient) -> None:
    resp = await client.get("/tools/list")
    assert resp.status_code == 200
    tool_names = {tool["name"] for tool in resp.json()["tools"]}
    assert {
        "search_local_files",
        "search_web",
        "save_memory",
        "get_journal_insights",
        "save_research_report",
        "analyze_image",
    }.issubset(tool_names)


async def test_search_local_files_happy_path(client: httpx.AsyncClient) -> None:
    async def fake_tool(query: str, top_k: int = 5):
        return SearchLocalFilesOutput(
            query=query,
            results=[{"id": "chunk-1", "text": "known indexed file", "metadata": {}}],
        )

    with patch("backend.mcp.tools.search_local_files", new=fake_tool):
        resp = await client.post(
            "/tools/search_local_files/invoke",
            json={"query": "known", "top_k": 1},
        )

    assert resp.status_code == 200
    assert resp.json()["result"]["results"][0]["text"] == "known indexed file"


async def test_search_web_happy_path(client: httpx.AsyncClient) -> None:
    async def fake_tool(query: str, max_results: int = 10):
        return SearchWebOutput(
            query=query,
            results=[{"url": "https://example.com", "title": "Example"}],
        )

    with patch("backend.mcp.tools.search_web", new=fake_tool):
        resp = await client.post(
            "/tools/search_web/invoke",
            json={"query": "nexus", "max_results": 1},
        )

    assert resp.status_code == 200
    assert resp.json()["result"]["results"][0]["url"] == "https://example.com"


async def test_save_memory_happy_path(client: httpx.AsyncClient) -> None:
    async def fake_tool(fact: str, category: str, importance: int):
        return SaveMemoryOutput(memory_id="mem-1", category=category, importance=0.8)

    with patch("backend.mcp.tools.save_memory", new=fake_tool):
        resp = await client.post(
            "/tools/save_memory/invoke",
            json={"fact": "I like quiet dashboards", "category": "preference", "importance": 8},
        )

    assert resp.status_code == 200
    assert resp.json()["result"]["memory_id"] == "mem-1"


async def test_get_journal_insights_happy_path(client: httpx.AsyncClient) -> None:
    async def fake_tool(date_range: str = "7d", topic: str | None = None):
        return JournalInsightsOutput(
            date_range=date_range,
            topic=topic,
            entry_count=0,
            entries=[],
            mood=None,
            insights=[],
        )

    with patch("backend.mcp.tools.get_journal_insights", new=fake_tool):
        resp = await client.post(
            "/tools/get_journal_insights/invoke",
            json={"date_range": "7d", "topic": "focus"},
        )

    assert resp.status_code == 200
    assert resp.json()["result"]["topic"] == "focus"


async def test_save_research_report_happy_path(client: httpx.AsyncClient) -> None:
    async def fake_tool(title: str, query: str):
        return SaveResearchReportOutput(
            session_id="session-1",
            slug="test-report",
            title=title,
            status="queued",
            message="started",
        )

    with patch("backend.mcp.tools.save_research_report", new=fake_tool):
        resp = await client.post(
            "/tools/save_research_report/invoke",
            json={"title": "Test Report", "query": "What changed?"},
        )

    assert resp.status_code == 200
    assert resp.json()["result"]["slug"] == "test-report"


async def test_analyze_image_happy_path(client: httpx.AsyncClient) -> None:
    async def fake_tool(image_path: str, question: str):
        return AnalyzeImageOutput(
            image_path=image_path,
            question=question,
            answer="A diagram.",
        )

    with patch("backend.mcp.tools.analyze_image", new=fake_tool):
        resp = await client.post(
            "/tools/analyze_image/invoke",
            json={"image_path": "C:/tmp/image.png", "question": "What is this?"},
        )

    assert resp.status_code == 200
    assert resp.json()["result"]["answer"] == "A diagram."


async def test_bearer_auth_required_when_token_set(monkeypatch) -> None:
    monkeypatch.setenv("MCP_AUTH_TOKEN", "secret")
    transport = httpx.ASGITransport(app=create_app(), client=("127.0.0.1", 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as ac:
        denied = await ac.get("/tools/list")
        allowed = await ac.get("/tools/list", headers={"Authorization": "Bearer secret"})

    assert denied.status_code == 401
    assert allowed.status_code == 200
