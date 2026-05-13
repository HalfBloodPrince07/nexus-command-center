"""Tests for research_graph conditional edge functions.

These functions are pure (no I/O) so no mocking is required.
"""
from __future__ import annotations

import sys
import types

# ---------------------------------------------------------------------------
# Stub langgraph so the module imports without the package installed.
# ---------------------------------------------------------------------------
if "langgraph" not in sys.modules:
    _lg = types.ModuleType("langgraph")
    _lg_graph = types.ModuleType("langgraph.graph")

    class _END:
        pass

    class _StateGraph:
        def __init__(self, *a, **kw): ...
        def add_node(self, *a, **kw): ...
        def set_entry_point(self, *a, **kw): ...
        def add_conditional_edges(self, *a, **kw): ...
        def add_edge(self, *a, **kw): ...
        def compile(self): return self

    _lg_graph.END = _END()
    _lg_graph.StateGraph = _StateGraph
    sys.modules["langgraph"] = _lg
    sys.modules["langgraph.graph"] = _lg_graph

import pytest

from backend.app.graph.research_graph import (
    should_proceed_to_scraper,
    should_proceed_to_fact_checker,
    ResearchState,
)


def _base_state(**overrides) -> dict:
    """Build a minimal ResearchState-compatible dict."""
    defaults: dict = {
        "topic": "test topic",
        "job_id": "job-1",
        "slug": "test-topic",
        "session_id": "sess-1",
        "queries": [],
        "urls": [],
        "sources": [],
        "claims": [],
        "report_md": "",
        "metadata": {},
        "errors": [],
        "status": "searching",
        "retry_count": 0,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# should_proceed_to_scraper
# ---------------------------------------------------------------------------


def test_should_proceed_to_scraper_no_urls() -> None:
    """Empty URL list → graph should route to 'failed'."""
    state = _base_state(urls=[])
    assert should_proceed_to_scraper(state) == "failed"


def test_should_proceed_to_scraper_with_urls() -> None:
    """Non-empty URL list → graph should route to 'proceed'."""
    state = _base_state(
        urls=[{"url": "https://example.com", "title": "Test Page", "score": 0.9}]
    )
    assert should_proceed_to_scraper(state) == "proceed"


def test_should_proceed_to_scraper_multiple_urls() -> None:
    state = _base_state(
        urls=[
            {"url": "https://a.com", "title": "A"},
            {"url": "https://b.com", "title": "B"},
        ]
    )
    assert should_proceed_to_scraper(state) == "proceed"


# ---------------------------------------------------------------------------
# should_proceed_to_fact_checker
# ---------------------------------------------------------------------------


def test_should_proceed_to_fact_checker_enough_sources() -> None:
    """3 sources with retry_count=0 → should 'proceed'."""
    state = _base_state(
        sources=[{"text": "a"}, {"text": "b"}, {"text": "c"}],
        retry_count=0,
    )
    assert should_proceed_to_fact_checker(state) == "proceed"


def test_should_proceed_to_fact_checker_too_few_retry() -> None:
    """Only 1 source with retry_count=0 → should 'retry'."""
    state = _base_state(
        sources=[{"text": "only one source"}],
        retry_count=0,
    )
    assert should_proceed_to_fact_checker(state) == "retry"


def test_should_proceed_to_fact_checker_too_few_exhausted() -> None:
    """Only 1 source but retry_count=1 (exhausted) → proceed anyway."""
    state = _base_state(
        sources=[{"text": "only one source after retry"}],
        retry_count=1,
    )
    assert should_proceed_to_fact_checker(state) == "proceed"


def test_should_proceed_to_fact_checker_no_sources_exhausted() -> None:
    """Zero sources with retry_count=1 → 'failed'."""
    state = _base_state(sources=[], retry_count=1)
    assert should_proceed_to_fact_checker(state) == "failed"


def test_should_proceed_to_fact_checker_no_sources_first_try() -> None:
    """Zero sources with retry_count=0 → 'retry' (not 'failed')."""
    state = _base_state(sources=[], retry_count=0)
    assert should_proceed_to_fact_checker(state) == "retry"


def test_should_proceed_to_fact_checker_exactly_three_sources() -> None:
    """Exactly MIN_SOURCES (3) is sufficient to proceed."""
    sources = [{"text": f"source {i}"} for i in range(3)]
    state = _base_state(sources=sources, retry_count=0)
    assert should_proceed_to_fact_checker(state) == "proceed"
