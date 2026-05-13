"""Integration tests for the /api/research router using FastAPI TestClient.

The database and vector store are fully mocked so no real SQLite/ChromaDB
connections are made during these tests.
"""
from __future__ import annotations

import sys
import types
import uuid

import pytest

# ---------------------------------------------------------------------------
# Stub heavy optional dependencies before any app imports
# ---------------------------------------------------------------------------

# langgraph stub
if "langgraph" not in sys.modules:
    _lg = types.ModuleType("langgraph")
    _lg_graph = types.ModuleType("langgraph.graph")

    class _StateGraph:
        def __init__(self, *a, **kw): ...
        def add_node(self, *a, **kw): ...
        def set_entry_point(self, *a, **kw): ...
        def add_conditional_edges(self, *a, **kw): ...
        def add_edge(self, *a, **kw): ...
        def compile(self): return self

    _lg_graph.END = object()
    _lg_graph.StateGraph = _StateGraph
    sys.modules["langgraph"] = _lg
    sys.modules["langgraph.graph"] = _lg_graph

# duckduckgo_search stub
if "duckduckgo_search" not in sys.modules:
    _ddgs_mod = types.ModuleType("duckduckgo_search")

    class _DDGS:
        def text(self, *a, **kw): return []

    _ddgs_mod.DDGS = _DDGS
    sys.modules["duckduckgo_search"] = _ddgs_mod

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Return a TestClient with DB and vector store mocked away."""

    # Patch database calls used by the research router
    with (
        patch("backend.core.database.init_db", new=AsyncMock()),
        patch("backend.db.vector_store.init_vector_store", new=AsyncMock(return_value=MagicMock())),
        patch("backend.core.database.create_research_session", new=AsyncMock()),
        patch("backend.core.database.get_research_session", new=AsyncMock(return_value=None)),
        patch("backend.core.database.delete_research_session_by_slug", new=AsyncMock()),
    ):
        # Import app after stubs are installed
        from backend.app.main import app
        # Use TestClient in a sync context (no lifespan for unit tests)
        with TestClient(app, raise_server_exceptions=True) as tc:
            yield tc


# ---------------------------------------------------------------------------
# GET /api/research  — list reports
# ---------------------------------------------------------------------------


def test_list_reports_empty(client: TestClient, tmp_path, monkeypatch) -> None:
    """When no deep_research dir exists the endpoint returns 200 and an empty list."""
    from backend import config as cfg
    monkeypatch.setattr(cfg.settings, "DEEP_RESEARCH_DIR", tmp_path / "nonexistent")

    resp = client.get("/api/research")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_reports_returns_list(client: TestClient, tmp_path, monkeypatch) -> None:
    """Endpoint returns 200 with a list type even when the dir exists but is empty."""
    research_dir = tmp_path / "deep_research"
    research_dir.mkdir()
    from backend import config as cfg
    monkeypatch.setattr(cfg.settings, "DEEP_RESEARCH_DIR", research_dir)

    resp = client.get("/api/research")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# GET /api/research/{slug}  — single report
# ---------------------------------------------------------------------------


def test_get_report_not_found(client: TestClient, tmp_path, monkeypatch) -> None:
    """Non-existent slug → 404."""
    research_dir = tmp_path / "deep_research"
    research_dir.mkdir()
    from backend import config as cfg
    monkeypatch.setattr(cfg.settings, "DEEP_RESEARCH_DIR", research_dir)

    resp = client.get("/api/research/nonexistent-slug")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/research/start
# ---------------------------------------------------------------------------


def test_start_research_returns_job_id(client: TestClient) -> None:
    """Starting a research job returns a response with job_id and slug."""
    resp = client.post(
        "/api/research/start",
        json={"topic": "AI trends", "session_id": "test-123"},
    )
    assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "job_id" in data, f"Missing 'job_id' in response: {data}"
    assert "slug" in data, f"Missing 'slug' in response: {data}"


def test_start_research_slug_derived_from_topic(client: TestClient) -> None:
    """Slug in the response must be derived from the topic string."""
    resp = client.post(
        "/api/research/start",
        json={"topic": "Quantum Computing", "session_id": "s-1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "quantum" in data["slug"].lower()


def test_start_research_empty_topic_rejected(client: TestClient) -> None:
    """An empty topic string must be rejected with 422."""
    resp = client.post(
        "/api/research/start",
        json={"topic": "   ", "session_id": "s-1"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/research/{slug}
# ---------------------------------------------------------------------------


def test_delete_report_not_found(client: TestClient, tmp_path, monkeypatch) -> None:
    """Deleting a non-existent slug → 404."""
    research_dir = tmp_path / "deep_research"
    research_dir.mkdir()
    from backend import config as cfg
    monkeypatch.setattr(cfg.settings, "DEEP_RESEARCH_DIR", research_dir)

    resp = client.delete("/api/research/nonexistent-slug")
    assert resp.status_code == 404


def test_delete_report_existing(client: TestClient, tmp_path, monkeypatch) -> None:
    """Deleting an existing report directory returns 200."""
    import json as _json

    research_dir = tmp_path / "deep_research"
    slug_dir = research_dir / "my-report"
    slug_dir.mkdir(parents=True)
    (slug_dir / "metadata.json").write_text(
        _json.dumps({"slug": "my-report", "topic": "Test"}), encoding="utf-8"
    )
    (slug_dir / "report.md").write_text("# Report", encoding="utf-8")

    from backend import config as cfg
    monkeypatch.setattr(cfg.settings, "DEEP_RESEARCH_DIR", research_dir)

    with patch("backend.app.api.research._delete_chroma_entries", new=AsyncMock()):
        resp = client.delete("/api/research/my-report")

    assert resp.status_code == 200
