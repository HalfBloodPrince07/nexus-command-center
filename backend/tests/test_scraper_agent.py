"""Tests for ScraperAgent — extract_text, _detect_paywall, fetch_url, _url_hash."""
from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.agents.scraper_agent import ScraperAgent


@pytest.fixture
def agent() -> ScraperAgent:
    return ScraperAgent()


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------

_REAL_ARTICLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Python Programming Language</title></head>
<body>
<article>
  <h1>Python Programming Language</h1>
  <p>Python is a high-level, general-purpose programming language that emphasizes code
  readability. Created by Guido van Rossum and first released in 1991, Python has become
  one of the most popular programming languages in the world. Its design philosophy
  prioritizes developer productivity and code clarity.</p>
  <p>Python supports multiple programming paradigms, including structured,
  object-oriented, and functional programming. It has a large standard library,
  often described as "batteries included", and a thriving ecosystem of third-party packages.
  As of 2024, Python ranks among the top three most widely used languages globally.
  Over 10 million developers use Python for web development, data science, AI, and automation.</p>
  <p>The language is dynamically typed and garbage-collected, making it easier to write
  flexible code. Python's package manager pip provides access to over 400,000 packages
  on PyPI (Python Package Index), the official repository for Python software.</p>
</article>
</body>
</html>"""


def test_extract_text_with_real_html(agent: ScraperAgent) -> None:
    """Realistic article HTML should yield non-empty text and a positive quality score."""
    result = agent.extract_text(_REAL_ARTICLE_HTML, "https://example.com/python")

    assert "text" in result, "Result dict must contain 'text' key"
    assert result["text"], "Extracted text must be non-empty"
    assert result["quality_score"] > 0, (
        f"Quality score must be positive, got {result['quality_score']}"
    )


def test_extract_text_returns_quality_score_key(agent: ScraperAgent) -> None:
    result = agent.extract_text(_REAL_ARTICLE_HTML, "https://example.com")
    assert "quality_score" in result


# ---------------------------------------------------------------------------
# _detect_paywall
# ---------------------------------------------------------------------------

_PAYWALL_HTML = """
<html><body>
<h1>Premium Article</h1>
<p>Subscribe to read more of this article and gain full access to our content.</p>
<p>This content is for subscribers only. Sign up today.</p>
<p>Short text.</p>
</body></html>
"""

_CLEAN_HTML = """
<html><body>
<article>
<h1>Freely Available Article</h1>
<p>This is a long open-access article with plenty of content freely available.
It has many paragraphs of text without any subscription prompts. The content
covers technology, science, and culture in depth across multiple sections.
Here is the full body of the article with no restrictions or sign-in gates.
You can read everything here without any subscription or payment required.
The article continues with detailed analysis and expert commentary throughout.</p>
</article>
</body></html>
"""


def test_detect_paywall_known_phrases(agent: ScraperAgent) -> None:
    """HTML with common paywall phrases and short extracted text should be detected."""
    # Short text triggers paywall detection for keyword matching
    assert agent._detect_paywall(_PAYWALL_HTML, "Short text.") is True


def test_detect_paywall_clean_content(agent: ScraperAgent) -> None:
    """Clean article HTML with no paywall phrases should return False."""
    long_text = "This is a long open-access article. " * 20
    assert agent._detect_paywall(_CLEAN_HTML, long_text) is False


def test_detect_paywall_schema_org_false(agent: ScraperAgent) -> None:
    """schema.org isAccessibleForFree:false markup signals a paywall regardless of text length."""
    html = '<html><body><script type="application/ld+json">{"isAccessibleForFree": "False"}</script></html>'
    assert agent._detect_paywall(html, "A" * 500) is True


# ---------------------------------------------------------------------------
# fetch_url
# ---------------------------------------------------------------------------


async def test_fetch_url_timeout_returns_error_dict(
    agent: ScraperAgent, mocker
) -> None:
    """A TimeoutException from httpx must map to extraction_status 'timeout'."""
    mock_get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client = MagicMock()
    mock_client.get = mock_get

    result = await agent.fetch_url(mock_client, "https://slow-site.example.com")

    assert result["error"] == "timeout", (
        f"Expected error='timeout', got error='{result['error']}'"
    )
    assert result["html"] is None
    assert result["status_code"] is None


async def test_fetch_url_http_error_returns_status_code(
    agent: ScraperAgent, mocker
) -> None:
    """A 404 response must surface in the returned dict."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = ""

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await agent.fetch_url(mock_client, "https://example.com/missing")

    assert result["status_code"] == 404
    assert result["error"] == "http_404"


# ---------------------------------------------------------------------------
# _url_hash
# ---------------------------------------------------------------------------


def test_url_hash_is_deterministic(agent: ScraperAgent) -> None:
    url = "https://example.com/some/path?q=test"
    assert agent._url_hash(url) == agent._url_hash(url)


def test_url_hash_length_is_12(agent: ScraperAgent) -> None:
    assert len(agent._url_hash("https://example.com")) == 12


def test_url_hash_differs_for_different_urls(agent: ScraperAgent) -> None:
    assert agent._url_hash("https://a.com") != agent._url_hash("https://b.com")
