"""Tests for FactCheckerAgent — check_claim_in_source, verify_claims."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from backend.app.agents.fact_checker import FactCheckerAgent
from backend.config import settings


@pytest.fixture
def agent() -> FactCheckerAgent:
    return FactCheckerAgent()


# ---------------------------------------------------------------------------
# check_claim_in_source
# ---------------------------------------------------------------------------


def test_check_claim_in_source_high_overlap(agent: FactCheckerAgent) -> None:
    """Claim keywords appear in source → score should be >= 0.5."""
    claim = "Python is a programming language"
    source = (
        "Python is widely used as a programming language for software development. "
        "It was created by Guido van Rossum and emphasizes code readability. "
        "Python supports object-oriented, functional, and procedural programming paradigms."
    )
    score = agent.check_claim_in_source(claim, source)
    assert score >= 0.5, f"Expected score >= 0.5 for overlapping content, got {score}"


def test_check_claim_in_source_no_overlap(agent: FactCheckerAgent) -> None:
    """Claim has no keyword overlap with source → score should be < 0.2."""
    claim = "The Eiffel Tower is in Paris"
    source = (
        "Quantum entanglement describes correlations between particles that cannot be "
        "explained classically. Wave functions collapse upon measurement. Heisenberg's "
        "uncertainty principle states that position and momentum cannot both be known."
    )
    score = agent.check_claim_in_source(claim, source)
    assert score < 0.2, f"Expected score < 0.2 for unrelated content, got {score}"


def test_check_claim_in_source_empty_source(agent: FactCheckerAgent) -> None:
    """Empty source text must return 0.0, not raise."""
    score = agent.check_claim_in_source("some claim here", "")
    assert score == 0.0


def test_check_claim_in_source_short_keywords_excluded(agent: FactCheckerAgent) -> None:
    """Keywords shorter than 4 chars are ignored by the scorer — result is 0.0 for claim with only short words."""
    # All words are <= 3 chars so keywords list will be empty
    score = agent.check_claim_in_source("a is an", "a is an")
    assert score == 0.0


# ---------------------------------------------------------------------------
# verify_claims
# ---------------------------------------------------------------------------


async def test_verify_claims_status_verified(agent: FactCheckerAgent) -> None:
    """A claim supported by MIN_SOURCES_FOR_FACT_CHECK+ sources must be 'verified'."""
    claim = "Python is a widely used programming language for data science and web development"

    # Two sources with clear keyword overlap
    sources = [
        {
            "url": "https://source1.com",
            "text": (
                "Python is a widely used programming language. It is popular in data science "
                "and web development. Many developers prefer Python for its readability."
            ),
            "quality_score": 0.8,
        },
        {
            "url": "https://source2.com",
            "text": (
                "Python programming language is used in web development frameworks like Django "
                "and Flask. Python is the top choice for data science and machine learning."
            ),
            "quality_score": 0.75,
        },
    ]

    results = await agent.verify_claims([claim], sources)

    assert len(results) == 1
    result = results[0]
    assert result["claim"] == claim
    assert result["status"] == "verified", (
        f"Expected 'verified', got '{result['status']}'. "
        f"Supporting urls: {result['source_urls']}"
    )


async def test_verify_claims_status_unverified(agent: FactCheckerAgent) -> None:
    """A claim that no source supports must be 'unverified'."""
    claim = "The Eiffel Tower has exactly 1,665 steps to the top"

    sources = [
        {
            "url": "https://quantum.example.com",
            "text": "Quantum computing uses qubits that can exist in superposition states.",
            "quality_score": 0.7,
        },
        {
            "url": "https://ocean.example.com",
            "text": "The Pacific Ocean covers more than 60 million square miles of Earth's surface.",
            "quality_score": 0.6,
        },
    ]

    results = await agent.verify_claims([claim], sources)

    assert len(results) == 1
    assert results[0]["status"] == "unverified", (
        f"Expected 'unverified', got '{results[0]['status']}'"
    )


async def test_verify_claims_returns_confidence_in_range(agent: FactCheckerAgent) -> None:
    """Confidence scores must always be in [0.0, 1.0]."""
    claims = [
        "Python is a programming language used widely",
        "Quantum computing leverages superposition",
    ]
    sources = [
        {"url": "https://a.com", "text": "Python is a programming language used widely in industry.", "quality_score": 0.8},
    ]

    results = await agent.verify_claims(claims, sources)
    for r in results:
        assert 0.0 <= r["confidence"] <= 1.0, (
            f"confidence out of range: {r['confidence']} for claim '{r['claim']}'"
        )


async def test_verify_claims_empty_inputs(agent: FactCheckerAgent) -> None:
    """Empty claims list should return empty results, not raise."""
    results = await agent.verify_claims([], [])
    assert results == []


async def test_verify_claims_result_has_required_keys(agent: FactCheckerAgent) -> None:
    """Each result dict must contain the mandatory schema keys."""
    results = await agent.verify_claims(
        ["Python is popular"],
        [{"url": "https://x.com", "text": "Python is very popular today.", "quality_score": 0.5}],
    )
    required_keys = {"claim", "status", "confidence", "source_urls", "contradiction_note"}
    for r in results:
        assert required_keys.issubset(r.keys()), f"Missing keys in result: {r.keys()}"
