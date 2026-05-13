"""Phase 1 — QueryArchitect: expand raw query into an optimized multi-dimensional search plan."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import AsyncGenerator

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are QueryArchitect, an elite search intelligence agent. Your sole function is to
decompose a research topic into a comprehensive, non-redundant set of search queries
that will yield maximum knowledge coverage when executed against web search engines.

You operate with these constraints:
- Output ONLY valid JSON. No preamble, no explanation, no markdown fences.
- Every query must target a DISTINCT angle of the topic. No duplicates.
- Queries must be production-ready for a search engine. No placeholders.
- Balance breadth (overview) with depth (technical specifics).

Output schema:
{
  "research_title": "<concise professional title for this research>",
  "research_scope": "<2-sentence description of what this research will cover>",
  "queries": [
    {
      "query": "<exact search string>",
      "type": "boolean|semantic|temporal|domain_specific|adversarial|comparative",
      "intent": "<what specific gap this query fills>",
      "target_engine": "duckduckgo|brave|bing",
      "expected_source_type": "academic|news|technical_doc|forum|government|industry"
    }
  ]
}

Query type definitions:
- boolean: Uses AND/OR/NOT operators, quotes for exact phrases
- semantic: Natural language, targets meaning over keywords
- temporal: Explicitly anchors to time period (e.g., "2024 2025 latest")
- domain_specific: Prefixed with site: or targets a specific corpus
- adversarial: Explicitly searches for criticisms, failures, counterarguments
- comparative: Positions topic against alternatives or competing approaches\
"""

_USER_PROMPT_TEMPLATE = """\
Research Topic: {raw_query}

Generate a comprehensive query set. Requirements:
1. Minimum 15 queries, maximum 25
2. Must include at least: 3 boolean queries, 3 temporal queries (anchor to 2024-2025),
   2 adversarial queries (criticisms/failures), 2 comparative queries
3. Cover these angles: fundamentals, current state, technical depth, real-world
   applications, limitations/risks, future trajectory, expert opinions
4. For domain_specific queries, target high-authority sources:
   arxiv.org, nature.com, ieee.org, acm.org, hbr.org, mckinsey.com,
   gov sites (.gov, .edu), major newspapers (ft.com, wsj.com, reuters.com)

Produce the JSON now.\
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def _validate_queries(result: dict) -> dict:
    queries = result.get("queries", [])
    type_counts = Counter(q.get("type", "") for q in queries)

    for q_type, minimum in [("boolean", 3), ("temporal", 3), ("adversarial", 2)]:
        if type_counts.get(q_type, 0) < minimum:
            logger.warning(
                "QueryArchitect: %d %s queries (need %d+)",
                type_counts.get(q_type, 0), q_type, minimum,
            )

    # Deduplicate by first-5-sorted-words fingerprint
    seen: set[str] = set()
    clean: list[dict] = []
    for q in queries:
        core = " ".join(sorted(q.get("query", "").lower().split())[:5])
        if core not in seen:
            seen.add(core)
            clean.append(q)

    result["queries"] = clean[:25]
    if not result.get("research_title"):
        result["research_title"] = "Research Report"
    if not result.get("research_scope"):
        result["research_scope"] = "Comprehensive research coverage."
    return result


def _fallback_queries(raw_query: str) -> dict:
    """Deterministic fallback when LLM call or JSON parse fails."""
    q = raw_query
    return {
        "research_title": raw_query,
        "research_scope": (
            f"This research covers the current state, key applications, limitations, "
            f"and future trajectory of: {raw_query}."
        ),
        "queries": [
            {"query": q, "type": "semantic", "intent": "primary overview",
             "target_engine": "duckduckgo", "expected_source_type": "news"},
            {"query": f"{q} explained overview fundamentals", "type": "semantic",
             "intent": "fundamentals", "target_engine": "duckduckgo", "expected_source_type": "technical_doc"},
            {"query": f"{q} technical deep dive how it works", "type": "semantic",
             "intent": "technical depth", "target_engine": "duckduckgo", "expected_source_type": "technical_doc"},
            {"query": f"{q} real world applications use cases examples", "type": "semantic",
             "intent": "applications", "target_engine": "duckduckgo", "expected_source_type": "industry"},
            {"query": f"{q} expert analysis report", "type": "semantic",
             "intent": "expert opinions", "target_engine": "duckduckgo", "expected_source_type": "industry"},
            # Boolean
            {"query": f'"{q}" AND (applications OR "use cases" OR implementation)', "type": "boolean",
             "intent": "concrete applications", "target_engine": "duckduckgo", "expected_source_type": "technical_doc"},
            {"query": f'"{q}" AND (challenges OR limitations OR "pain points")', "type": "boolean",
             "intent": "limitations", "target_engine": "duckduckgo", "expected_source_type": "news"},
            {"query": f'"{q}" AND (research OR study OR "white paper") NOT beginner', "type": "boolean",
             "intent": "research literature", "target_engine": "duckduckgo", "expected_source_type": "academic"},
            # Temporal
            {"query": f"{q} 2024 2025 latest developments", "type": "temporal",
             "intent": "current state", "target_engine": "duckduckgo", "expected_source_type": "news"},
            {"query": f"{q} 2025 trends forecast future", "type": "temporal",
             "intent": "future trajectory", "target_engine": "duckduckgo", "expected_source_type": "industry"},
            {"query": f"{q} recent breakthroughs 2024 update", "type": "temporal",
             "intent": "recent advances", "target_engine": "duckduckgo", "expected_source_type": "academic"},
            # Domain-specific
            {"query": f"{q} site:arxiv.org OR site:nature.com OR site:ieee.org", "type": "domain_specific",
             "intent": "academic research", "target_engine": "duckduckgo", "expected_source_type": "academic"},
            {"query": f"{q} site:mckinsey.com OR site:hbr.org OR site:ft.com", "type": "domain_specific",
             "intent": "industry insights", "target_engine": "duckduckgo", "expected_source_type": "industry"},
            # Adversarial
            {"query": f"{q} criticism problems failures risks", "type": "adversarial",
             "intent": "criticisms and risks", "target_engine": "duckduckgo", "expected_source_type": "news"},
            {"query": f"{q} controversy debate concerns expert warning", "type": "adversarial",
             "intent": "expert concerns", "target_engine": "duckduckgo", "expected_source_type": "news"},
            # Comparative
            {"query": f"{q} vs alternatives comparison which is better", "type": "comparative",
             "intent": "competitive landscape", "target_engine": "duckduckgo", "expected_source_type": "industry"},
            {"query": f"{q} compared similar approaches trade-offs", "type": "comparative",
             "intent": "trade-offs", "target_engine": "duckduckgo", "expected_source_type": "technical_doc"},
        ],
    }


class QueryArchitect:
    async def run(self, raw_query: str) -> AsyncGenerator[dict, None]:
        yield {
            "type": "thinking", "agent": "QueryArchitect",
            "detail": f"Expanding '{raw_query[:70]}' into a multi-dimensional search plan...",
        }

        result: dict = {}
        try:
            raw_response = await complete_chat(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(raw_query=raw_query)},
                ],
                model=settings.lm_studio_model,
                temperature=0.4,
                max_tokens=4096,
            )
            cleaned = _strip_fences(raw_response)
            result = json.loads(cleaned)
            result = _validate_queries(result)

        except json.JSONDecodeError as exc:
            logger.warning("QueryArchitect: JSON parse failed (%s) — using fallback queries", exc)
            result = _fallback_queries(raw_query)
        except Exception as exc:
            logger.error("QueryArchitect: LM Studio unavailable (%s) — using fallback queries", exc)
            result = _fallback_queries(raw_query)

        queries = result["queries"]
        type_counts = Counter(q.get("type") for q in queries)
        yield {
            "type": "progress", "agent": "QueryArchitect", "stage": "planning",
            "detail": (
                f"Generated {len(queries)} queries — "
                + ", ".join(f"{v}× {k}" for k, v in sorted(type_counts.items()))
            ),
        }
        yield {
            "type": "result", "agent": "QueryArchitect",
            "data": {
                "research_title": result["research_title"],
                "research_scope": result["research_scope"],
                "queries": queries,
            },
        }


query_architect = QueryArchitect()
