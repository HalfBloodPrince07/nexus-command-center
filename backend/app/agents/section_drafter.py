"""Phase 3b — SectionDrafter: draft individual report sections with source-grounded content."""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from backend.app.agents._lm_studio import stream_chat_completion
from backend.config import settings

logger = logging.getLogger(__name__)

_SECTION_SYSTEM_PROMPT = """\
You are SectionDrafter-{section_number}, an expert research writer. Your SOLE task is
to write ONE specific section of a larger research report.

You must:
1. Write ONLY the content for your assigned section. Do not write other sections.
2. Ground every factual claim in the provided source material. Never invent facts.
3. Use inline citations in the format [Source: {domain}] immediately after each claim.
4. Write in a professional, authoritative, academic-adjacent tone.
5. Use markdown formatting: ## for section heading, ### for subsections.
6. Target the specified word count ± 10%.
7. End with a [SECTION_SOURCES] block listing all URLs you drew from.

CRITICAL: If a fact is not supported by the provided sources, write "[NEEDS_VERIFICATION: <claim>]"
Do NOT hallucinate statistics, quotes, or specific data points.\
"""

_SECTION_USER_PROMPT = """\
REPORT CONTEXT:
Title: {report_title}
Your Section: {section_number} — "{section_title}"
Target Word Count: {estimated_words}

SECTION BRIEF:
{section_brief}

KEY QUESTIONS TO ANSWER:
{key_questions}

SOURCE MATERIAL:
The following are excerpts from {source_count} relevant web sources.
Use ONLY this material for factual claims.

---SOURCE MATERIAL START---
{formatted_sources}
---SOURCE MATERIAL END---

Write section {section_number}: "{section_title}" now.
Start directly with "## {section_title}" — no preamble.\
"""

# Rough chars-to-tokens ratio for budget estimation
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _format_sources_for_section(
    sources: list[dict],
    section: dict,
    max_tokens: int = 10_000,
) -> str:
    rec_urls: set[str] = set(section.get("recommended_sources") or [])
    primary = [s for s in sources if s.get("url") in rec_urls and s.get("quality_score", 0) > 0.3]
    secondary = [s for s in sources if s.get("url") not in rec_urls]

    # Score secondary sources by keyword overlap with key questions
    kw_text = " ".join(section.get("key_questions") or []).lower()
    keywords = set(kw_text.split())

    def _relevance(src: dict) -> float:
        text = (src.get("clean_text") or src.get("text") or "").lower()
        if not keywords:
            return 0.0
        hits = sum(1 for kw in keywords if kw in text)
        return hits / len(keywords)

    secondary.sort(key=_relevance, reverse=True)
    candidates = (primary + secondary)[:15]

    output: list[str] = []
    budget = max_tokens
    for src in candidates:
        excerpt = (src.get("clean_text") or src.get("text") or "")[:2000]
        entry = (
            f"\nSOURCE [{src.get('domain', 'unknown')}] — {(src.get('title') or src.get('url', ''))[:80]}\n"
            f"URL: {src.get('url', '')}\n"
            f"---\n{excerpt}\n"
        )
        cost = _estimate_tokens(entry)
        if cost > budget:
            break
        output.append(entry)
        budget -= cost

    return "\n".join(output)


class SectionDrafterAgent:
    async def draft_section(
        self,
        report_title: str,
        section: dict,
        sources: list[dict],
    ) -> AsyncGenerator[dict, None]:
        section_number = section.get("number", 1)
        section_title = section.get("title", f"Section {section_number}")
        estimated_words = section.get("estimated_words", 500)
        section_brief = section.get("brief", "")
        key_questions = "\n".join(
            f"- {q}" for q in (section.get("key_questions") or [])
        )

        formatted_sources = _format_sources_for_section(sources, section)
        source_count = formatted_sources.count("SOURCE [")

        system_prompt = _SECTION_SYSTEM_PROMPT.format(section_number=section_number)
        user_prompt = _SECTION_USER_PROMPT.format(
            report_title=report_title,
            section_number=section_number,
            section_title=section_title,
            estimated_words=estimated_words,
            section_brief=section_brief,
            key_questions=key_questions,
            source_count=source_count,
            formatted_sources=formatted_sources,
        )

        yield {
            "type": "progress",
            "agent": "SectionDrafter",
            "stage": f"drafting_section_{section_number}",
            "detail": f"Drafting section {section_number}: '{section_title}'...",
        }

        section_text = ""
        try:
            async for token in stream_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=settings.lm_studio_model,
                temperature=0.35,
                max_tokens=max(estimated_words * 2, 1024),
            ):
                section_text += token
                yield {"type": "chunk", "agent": "SectionDrafter", "section": section_number, "content": token}
        except Exception as exc:
            logger.error("SectionDrafter-%d failed: %s", section_number, exc)
            section_text = (
                f"## {section_title}\n\n"
                f"[NEEDS_VERIFICATION: Section generation failed — {exc}]\n"
            )
            yield {
                "type": "error",
                "agent": "SectionDrafter",
                "detail": f"Section {section_number} failed: {exc}",
            }

        yield {
            "type": "section_complete",
            "agent": "SectionDrafter",
            "section_number": section_number,
            "section_title": section_title,
            "text": section_text,
            "word_count": len(section_text.split()),
        }

    async def draft_all_sections(
        self,
        report_title: str,
        sections: list[dict],
        sources: list[dict],
    ) -> AsyncGenerator[dict, None]:
        """Draft sections sequentially (single-GPU constraint), collecting results."""
        drafted: list[dict] = []

        yield {
            "type": "thinking",
            "agent": "SectionDrafter",
            "detail": f"Drafting {len(sections)} sections sequentially...",
        }

        for section in sections:
            async for event in self.draft_section(report_title, section, sources):
                yield event
                if event.get("type") == "section_complete":
                    drafted.append({
                        "number": event["section_number"],
                        "title": event["section_title"],
                        "text": event["text"],
                    })

        yield {
            "type": "result",
            "agent": "SectionDrafter",
            "data": drafted,
            "section_count": len(drafted),
        }


section_drafter = SectionDrafterAgent()
