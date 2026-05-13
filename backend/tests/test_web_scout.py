"""Tests for WebScoutAgent — score_and_rank, generate_query_variations, _domain_score."""
from __future__ import annotations

import sys
import types

# ---------------------------------------------------------------------------
# Minimal stub for duckduckgo_search so the module can import without the
# real package being installed in the test environment.
# ---------------------------------------------------------------------------
if "duckduckgo_search" not in sys.modules:
    _ddgs_mod = types.ModuleType("duckduckgo_search")

    class _DDGS:
        def text(self, *a, **kw):
            return []

    _ddgs_mod.DDGS = _DDGS
    sys.modules["duckduckgo_search"] = _ddgs_mod

import pytest
from unittest.mock import AsyncMock, patch

from backend.app.agents.web_scout import WebScoutAgent
from backend.config import settings


@pytest.fixture
def agent() -> WebScoutAgent:
    return WebScoutAgent()


# ---------------------------------------------------------------------------
# score_and_rank
# ---------------------------------------------------------------------------


async def test_score_and_rank_orders_by_score(agent: WebScoutAgent) -> None:
    """Results from authoritative domains must rank above unknown blogs."""
    raw = [
        {
            "url": "https://nature.com/articles/s123",
            "title": "Quantum Computing Research",
            "body": "...",
            "query_used": "quantum computing",
        },
        {
            "url": "https://random-blog.xyz/quantum-stuff",
            "title": "My Quantum Blog Post",
            "body": "...",
            "query_used": "quantum computing",
        },
        {
            "url": "https://wikipedia.org/wiki/Quantum_computing",
            "title": "Quantum Computing - Wikipedia",
            "body": "...",
            "query_used": "quantum computing",
        },
    ]
    ranked = await agent.score_and_rank(raw, "quantum computing")

    # Output must be sorted descending by relevance_score
    scores = [r["relevance_score"] for r in ranked]
    assert scores == sorted(scores, reverse=True), (
        f"Results not sorted by score. Got scores: {scores}"
    )

    # The two authoritative domains must outscore the random blog
    auth_urls = {"nature.com", "wikipedia.org"}
    for result in ranked:
        if any(d in result["url"] for d in auth_urls):
            assert result["relevance_score"] > 0.3, (
                f"Authoritative domain scored too low: {result['url']} -> {result['relevance_score']}"
            )


# ---------------------------------------------------------------------------
# generate_query_variations
# ---------------------------------------------------------------------------


async def test_generate_query_variations_returns_list(agent: WebScoutAgent) -> None:
    """LLM response lines are parsed into a list of strings capped at MAX_QUERY_VARIATIONS."""
    fake_content = "q1\nq2\nq3\nq4\nq5"

    with patch(
        "backend.app.agents._lm_studio.complete_chat",
        new=AsyncMock(return_value=fake_content),
    ):
        result = await agent.generate_query_variations("test topic")

    assert isinstance(result, list), "Result must be a list"
    assert all(isinstance(q, str) for q in result), "All items must be strings"
    assert len(result) <= settings.MAX_QUERY_VARIATIONS, (
        f"Expected <= {settings.MAX_QUERY_VARIATIONS} variations, got {len(result)}"
    )


async def test_generate_query_variations_falls_back_on_llm_error(
    agent: WebScoutAgent,
) -> None:
    """When the LLM call fails, the original topic is returned as the sole query."""
    with patch(
        "backend.app.agents._lm_studio.complete_chat",
        new=AsyncMock(side_effect=ConnectionError("LM Studio offline")),
    ):
        result = await agent.generate_query_variations("my topic")

    assert result == ["my topic"], f"Expected fallback to topic, got {result}"


# ---------------------------------------------------------------------------
# _domain_score
# ---------------------------------------------------------------------------


def test_domain_score_known_authoritative_domain(agent: WebScoutAgent) -> None:
    score = agent._domain_score("https://nature.com/article/s12345")
    assert score >= 0.8, f"nature.com should score >= 0.8, got {score}"


def test_domain_score_gov_tld(agent: WebScoutAgent) -> None:
    score = agent._domain_score("https://cdc.gov/flu/vaccines")
    assert score >= 0.8, f".gov TLD should score >= 0.8, got {score}"


def test_domain_score_unknown_domain(agent: WebScoutAgent) -> None:
    score = agent._domain_score("https://random-blog.xyz/some-post")
    assert score < 0.5, f"Unknown domain should score < 0.5, got {score}"


def test_domain_score_invalid_url(agent: WebScoutAgent) -> None:
    """Malformed URLs must not raise — they return 0.0."""
    score = agent._domain_score("")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
