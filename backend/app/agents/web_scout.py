"""Phase 2a — Web Search Agent: execute optimized queries, deduplicate, score and rank URLs."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncGenerator
from urllib.parse import urlparse

import httpx

from backend.core.resilience import RateLimited, degraded_event, with_retry

logger = logging.getLogger(__name__)

# Domain authority scores (0.0–1.0). Unlisted domains default to 0.3.
AUTHORITATIVE_DOMAINS: dict[str, float] = {
    "arxiv.org": 1.0, "nature.com": 1.0, "science.org": 1.0,
    "ieee.org": 0.95, "acm.org": 0.95, "nih.gov": 0.95,
    "mckinsey.com": 0.85, "hbr.org": 0.85, "mit.edu": 0.9,
    "stanford.edu": 0.9, "reuters.com": 0.8, "ft.com": 0.8,
    "wsj.com": 0.75, "economist.com": 0.8, "wired.com": 0.65,
    "techcrunch.com": 0.55, "medium.com": 0.35, "reddit.com": 0.25,
}

_STOPWORDS = {"and", "or", "not", "the", "a", "an", "in", "of", "to", "for", "is", "are", "on"}


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def _normalize_url(url: str) -> str:
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
    except Exception:
        return url


def _authority_score(domain: str) -> float:
    score = AUTHORITATIVE_DOMAINS.get(domain, 0.3)
    if domain.endswith(".gov") or domain.endswith(".edu"):
        score = max(score, 0.9)
    return score


def _relevance_score(title: str, query: str) -> float:
    q_words = set(re.sub(r"[^\w\s]", "", query.lower()).split()) - _STOPWORDS
    t_words = set(re.sub(r"[^\w\s]", "", title.lower()).split())
    return len(q_words & t_words) / len(q_words) if q_words else 0.0


@with_retry(
    max_attempts=3,
    backoff="exponential",
    retry_on=(RateLimited, httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError),
    base_delay=1.0,
    max_delay=60.0,
)
async def _search_one(query_obj: dict) -> list[dict]:
    from duckduckgo_search import DDGS

    query_str = query_obj.get("query", "")

    def _run() -> list[dict]:
        return list(DDGS().text(query_str, max_results=15, region="wt-wt", safesearch="off"))

    try:
        raw = await asyncio.to_thread(_run)
    except Exception as exc:
        message = str(exc).lower()
        if "429" in message or "rate" in message or "ratelimit" in message:
            raise RateLimited(f"DuckDuckGo rate-limited query '{query_str[:60]}': {exc}") from exc
        logger.warning(
            "DDG search failed",
            extra={"query": query_str[:120], "error_type": type(exc).__name__, "error": str(exc)},
        )
        return []

    results: list[dict] = []
    for r in raw:
        url = r.get("href", "")
        if not url:
            continue
        domain = _extract_domain(url)
        auth = _authority_score(domain)
        rel = _relevance_score(r.get("title", ""), query_str)
        results.append({
            "url": url,
            "title": r.get("title", ""),
            "snippet": r.get("body", ""),
            "domain": domain,
            "authority_score": round(auth, 3),
            "relevance_score": round(rel, 3),
            "composite_score": round(auth * 0.5 + rel * 0.5, 3),
            "query_id": query_obj.get("id"),
            "source_type": query_obj.get("expected_source_type", "unknown"),
        })
    return results


def _dedup_and_rank(all_results: list[dict], top_n: int = 100) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in all_results:
        key = _normalize_url(item["url"])
        if key not in seen or item["composite_score"] > seen[key]["composite_score"]:
            seen[key] = item
    return sorted(seen.values(), key=lambda x: x["composite_score"], reverse=True)[:top_n]


class WebSearchAgent:
    async def run(self, queries: list[dict]) -> AsyncGenerator[dict, None]:
        total = len(queries)
        yield {
            "type": "thinking", "agent": "Vector",
            "detail": f"Executing {total} optimized queries across search engines...",
        }

        all_results: list[dict] = []
        batch_size = 5

        for i in range(0, total, batch_size):
            batch = queries[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size
            yield {
                "type": "progress", "agent": "Vector", "stage": "searching",
                "detail": (
                    f"Batch {batch_num}/{total_batches} "
                    f"(queries {i+1}–{min(i+batch_size, total)})"
                ),
            }

            batch_results = await asyncio.gather(
                *[_search_one(q) for q in batch], return_exceptions=True
            )
            for r in batch_results:
                if isinstance(r, list):
                    all_results.extend(r)
                elif isinstance(r, RateLimited):
                    logger.warning("DDG rate limit persisted after retries", extra={"error": str(r)})
                    yield degraded_event(
                        "Vector",
                        "search_rate_limited",
                        "DuckDuckGo is rate-limiting searches. Try again in a minute.",
                    )
                elif isinstance(r, Exception):
                    logger.warning("Search query failed", extra={"error_type": type(r).__name__, "error": str(r)})

            if i + batch_size < total:
                await asyncio.sleep(2)

        ranked = _dedup_and_rank(all_results, top_n=100)
        yield {
            "type": "progress", "agent": "Vector", "stage": "ranking",
            "detail": (
                f"Discovered {len(all_results)} raw URLs → "
                f"{len(ranked)} unique after dedup/ranking"
            ),
        }
        yield {"type": "result", "agent": "Vector", "data": ranked}


class WebScoutAgent(WebSearchAgent):
    def _domain_score(self, url: str) -> float:
        return _authority_score(_extract_domain(url))

    async def score_and_rank(self, raw_results: list[dict], query: str) -> list[dict]:
        normalized: list[dict] = []
        for item in raw_results:
            url = item.get("url") or item.get("href") or ""
            title = item.get("title", "")
            domain = _extract_domain(url)
            auth = _authority_score(domain)
            rel = _relevance_score(title, query)
            normalized.append(
                {
                    "url": url,
                    "title": title,
                    "snippet": item.get("body") or item.get("snippet", ""),
                    "domain": domain,
                    "authority_score": round(auth, 3),
                    "relevance_score": round(auth * 0.6 + rel * 0.4, 3),
                    "composite_score": round(auth * 0.5 + rel * 0.5, 3),
                }
            )
        return sorted(normalized, key=lambda item: item["relevance_score"], reverse=True)

    async def generate_query_variations(self, topic: str) -> list[str]:
        try:
            from backend.app.agents._lm_studio import complete_chat
            from backend.config import settings

            raw = await complete_chat(
                messages=[
                    {"role": "system", "content": "Generate concise web search query variations, one per line."},
                    {"role": "user", "content": topic},
                ],
                model=settings.lm_studio_model,
                temperature=0.3,
                max_tokens=256,
            )
            queries = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]
            return queries[: settings.MAX_QUERY_VARIATIONS] or [topic]
        except Exception as exc:
            logger.warning("Query variation fallback", extra={"topic": topic[:120], "error": str(exc)})
            return [topic]


web_scout = WebSearchAgent()
