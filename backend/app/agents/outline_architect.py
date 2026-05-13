"""Phase 3a — OutlineArchitect: analyze scraped sources and generate a hierarchical report outline."""
from __future__ import annotations

import json
import logging
import re
from typing import AsyncGenerator

from backend.app.agents._lm_studio import complete_chat
from backend.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are OutlineArchitect, a research structure specialist. Your function is to analyze
a corpus of source material and generate the optimal hierarchical outline for a
comprehensive research report.

Rules:
- Output ONLY valid JSON. No explanation, no markdown fences.
- Sections must be MUTUALLY EXCLUSIVE in coverage.
- Each section must be grounded in the provided source material.
- Include an executive summary section first and a conclusion section last.
- Between 6 and 10 main sections (including intro/conclusion).

Output schema:
{
  "report_title": "<Professional, specific title>",
  "estimated_word_count": <integer>,
  "sections": [
    {
      "number": 1,
      "title": "<Section Title>",
      "brief": "<2-3 sentences: exactly what this section must cover>",
      "key_questions": ["<Question this section answers>"],
      "recommended_sources": ["<url1>", "<url2>"],
      "estimated_words": <integer>
    }
  ]
}\
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def _build_source_summaries(sources: list[dict]) -> str:
    lines: list[str] = []
    for s in sources[:30]:
        domain = s.get("domain", "")
        title = s.get("title", s.get("url", ""))[:80]
        snippet = (s.get("clean_text") or s.get("text") or "")[:100].replace("\n", " ")
        lines.append(f"- [{domain}] {title} | {snippet}")
    return "\n".join(lines)


def _build_user_prompt(
    research_title: str,
    research_scope: str,
    sources: list[dict],
    queries: list[str],
) -> str:
    source_summaries = _build_source_summaries(sources)
    query_list = "\n".join(f"- {q}" for q in queries)
    return (
        f"Research Topic: {research_title}\n"
        f"Scope: {research_scope}\n\n"
        f"Available Sources Summary:\n{source_summaries}\n\n"
        f"Queries Used:\n{query_list}\n\n"
        "Generate the optimal report outline. Ensure every major angle from the queries "
        "is addressed in at least one section. Distribute sources evenly across sections."
    )


def _fallback_outline(research_title: str, sources: list[dict]) -> dict:
    urls = [s.get("url", "") for s in sources[:6]]
    return {
        "report_title": research_title,
        "estimated_word_count": 3500,
        "sections": [
            {
                "number": 1,
                "title": "Executive Summary",
                "brief": "High-level overview of the research topic and key findings.",
                "key_questions": ["What are the most important takeaways?"],
                "recommended_sources": urls[:2],
                "estimated_words": 300,
            },
            {
                "number": 2,
                "title": "Background and Context",
                "brief": "Historical context, definitions, and foundational concepts.",
                "key_questions": ["What is the background?", "How did we get here?"],
                "recommended_sources": urls[:3],
                "estimated_words": 600,
            },
            {
                "number": 3,
                "title": "Current State and Key Developments",
                "brief": "Latest trends, recent developments, and current landscape.",
                "key_questions": ["What is the current state?", "What are the latest developments?"],
                "recommended_sources": urls[1:4],
                "estimated_words": 700,
            },
            {
                "number": 4,
                "title": "Technical Analysis",
                "brief": "In-depth technical breakdown of mechanisms and methodologies.",
                "key_questions": ["How does it work technically?", "What are the key mechanisms?"],
                "recommended_sources": urls[2:5],
                "estimated_words": 700,
            },
            {
                "number": 5,
                "title": "Challenges and Limitations",
                "brief": "Risks, drawbacks, criticisms, and open problems.",
                "key_questions": ["What are the main challenges?", "What are the known limitations?"],
                "recommended_sources": urls[3:6],
                "estimated_words": 500,
            },
            {
                "number": 6,
                "title": "Future Outlook and Conclusions",
                "brief": "Forward-looking analysis, predictions, and closing synthesis.",
                "key_questions": ["Where is this heading?", "What are the key conclusions?"],
                "recommended_sources": urls[:3],
                "estimated_words": 400,
            },
        ],
    }


class OutlineArchitectAgent:
    async def run(
        self,
        research_title: str,
        research_scope: str,
        sources: list[dict],
        queries: list[str],
    ) -> AsyncGenerator[dict, None]:
        yield {
            "type": "thinking",
            "agent": "OutlineArchitect",
            "detail": f"Structuring outline for '{research_title[:60]}'...",
        }

        outline: dict = {}
        try:
            raw = await complete_chat(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": _build_user_prompt(research_title, research_scope, sources, queries),
                    },
                ],
                model=settings.lm_studio_model,
                temperature=0.3,
                max_tokens=2048,
            )
            outline = json.loads(_strip_fences(raw))
        except json.JSONDecodeError as exc:
            logger.warning("OutlineArchitect: JSON parse failed (%s) — using fallback outline", exc)
            outline = _fallback_outline(research_title, sources)
        except Exception as exc:
            logger.error("OutlineArchitect: LM Studio error (%s) — using fallback outline", exc)
            outline = _fallback_outline(research_title, sources)

        sections = outline.get("sections", [])
        yield {
            "type": "progress",
            "agent": "OutlineArchitect",
            "stage": "outline_ready",
            "detail": f"Outline ready: {len(sections)} sections, ~{outline.get('estimated_word_count', 0):,} words",
        }
        yield {
            "type": "result",
            "agent": "OutlineArchitect",
            "data": outline,
        }


outline_architect = OutlineArchitectAgent()
